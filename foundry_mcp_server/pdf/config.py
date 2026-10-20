"""Opt-in GM-private library configuration, separate from browser bridge auth."""
from dataclasses import dataclass
from pathlib import Path
import os
from foundry_mcp_server.config import settings

@dataclass(frozen=True)
class PDFConfig:
    enabled: bool = False
    library: Path | None = None
    state: Path | None = None
    uploads: bool = False
    token: str = ''
    max_bytes: int = 134217728
    quota: int = 2147483648
    concurrent: int = 2
    idle: int = 120
    proxy_tls: bool = False

    @classmethod
    def from_env(cls):
        def flag(name):
            value = os.getenv('FOUNDRY_MCP_PDF_' + name, 'false')
            if value not in {'true', 'false'}: raise ValueError('PDF flags must be true or false')
            return value == 'true'
        enabled, uploads = flag('ENABLED'), flag('UPLOAD_ENABLED')
        if uploads and not enabled: raise ValueError('PDF uploads require the PDF library')
        if not enabled: return cls()
        if not (settings.auth_mode == 'basic' or settings.development) or not flag('TRUSTED_GM_MCP'):
            raise ValueError('PDF library requires authenticated, exclusively GM-trusted MCP clients')
        roots = [Path(os.environ['FOUNDRY_MCP_PDF_' + key]) for key in ('LIBRARY_DIR', 'INDEX_DIR')]
        if any(not p.is_absolute() or p.is_symlink() or p.resolve()!=p for p in roots): raise ValueError('PDF roots must be absolute non-symlink directories')
        if roots[0] == roots[1] or any(a in b.parents for a,b in (roots, roots[::-1])):
            raise ValueError('PDF library and state roots must be separate')
        token = os.getenv('FOUNDRY_MCP_PDF_UPLOAD_TOKEN', '')
        if uploads and (not token or token in {settings.bridge_token, settings.browser_token, settings.basic_password, settings.mcp_token}):
            raise ValueError('PDF uploads require a separate private capability')
        values = [int(os.getenv('FOUNDRY_MCP_PDF_' + key, str(default))) for key,default in
                  [('MAX_UPLOAD_BYTES',134217728),('QUOTA_BYTES',2147483648),('MAX_CONCURRENT_UPLOADS',2),('IDLE_SECONDS',120)]]
        if any(v <= 0 for v in values) or values[0] > values[1] or values[2] > 8:
            raise ValueError('Invalid PDF size, quota, concurrency or timeout limits')
        return cls(True, *roots, uploads, token, *values, flag('TRUST_TLS_PROXY'))
