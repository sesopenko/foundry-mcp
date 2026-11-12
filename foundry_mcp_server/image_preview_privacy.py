"""Narrow capability/credential-URL redaction for diagnostics and trace records."""
import hashlib
import logging
import re
import traceback
from urllib.parse import unquote,urlsplit

CAPABILITY = re.compile(r'''(?:https?://[^\s"'<>]*?)?/image-previews(?=$|[/\s?\#"'<>])(?:[/\?#][^\s"'<>]*)?''',re.I)
URL = re.compile(r'''https?://[^\s"'<>]+''',re.I)
SIGNED = re.compile(r'(?:^|&)(?:x-amz-[^=&]+|signature|sig|token|credential|policy|key-pair-id|awsaccesskeyid)=',re.I)


def sensitive_url(value):
    try:
        parsed = urlsplit(value)
        return parsed.username is not None or bool(SIGNED.search(parsed.query))
    except ValueError:return True


def scrub_text(value):
    """Keep ordinary diagnostic text; erase bearer path and its entire query."""
    cleaned = CAPABILITY.sub('/image-previews/[redacted]',value)
    def url(match):
        if sensitive_url(match[0]):return '[credential URL redacted]'
        return match[0]
    cleaned = URL.sub(url,cleaned)
    # Encoded selector/diagnostic strings may spell the prefix indirectly.
    # Classification only; never decode/rewrite source asset selectors.
    decoded = value
    for _ in range(2):
        decoded = unquote(decoded)
        if decoded!=value and (CAPABILITY.search(decoded) or any(
                sensitive_url(m[0]) for m in URL.finditer(decoded))):
            return '[preview or credential URL redacted]'
    return cleaned


def scrub_log_value(value):
    if isinstance(value,str):return scrub_text(value)
    if isinstance(value,tuple):return tuple(scrub_log_value(v) for v in value)
    if isinstance(value,list):return [scrub_log_value(v) for v in value]
    if isinstance(value,dict):return {scrub_log_value(k):scrub_log_value(v) for k,v in value.items()}
    if value is not None and not isinstance(value,(int,float,bool)):
        # HTTP clients pass URL objects to %s. Their bearer path only becomes
        # text at formatting time, after a string-only filter has already run.
        text = str(value)
        cleaned = scrub_text(text)
        if cleaned!=text:return cleaned
    return value


def private_record(value):
    """Sensitive trace strings become fingerprints, never bearer substrings."""
    if isinstance(value,str) and scrub_text(value)!=value:
        return {'redacted':True,'sha256':hashlib.sha256(value.encode(errors='surrogatepass')).hexdigest()}
    if isinstance(value,dict):
        return {(key if not isinstance(key,str) or scrub_text(key)==key else
            '[redacted field '+hashlib.sha256(key.encode(errors='surrogatepass')).hexdigest()[:16]+']'):private_record(v) for key,v in value.items()}
    if isinstance(value,(list,tuple)):return [private_record(v) for v in value]
    return value


class CapabilityFilter(logging.Filter):
    def filter(self,record):
        # Preserve Uvicorn's five access arguments for its real AccessFormatter.
        # Formatting the whole message and clearing args would break it.
        for key,value in list(record.__dict__.items()):
            if key!='exc_info':setattr(record,key,scrub_log_value(value))
        if record.exc_info:
            record.exc_text = scrub_text(''.join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        return True


def install_capability_filters():
    """Install after Uvicorn configuration too; retain unrelated logging/status."""
    names = ('uvicorn','uvicorn.access','uvicorn.error','foundry_mcp','foundry_mcp.image_previews',
        'foundry_mcp.evaluation','foundry_mcp.execution','httpx2')
    loggers = [logging.getLogger(name) for name in names]+[logging.getLogger()]
    for logger in loggers:
        if not any(isinstance(f,CapabilityFilter) for f in logger.filters):logger.addFilter(CapabilityFilter())
        for handler in logger.handlers:
            if not any(isinstance(f,CapabilityFilter) for f in handler.filters):handler.addFilter(CapabilityFilter())
