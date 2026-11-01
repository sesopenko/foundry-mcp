"""Isolated bounded HTTPS retrieval and image decoding for MCP uploads.

Only the parent-supplied private staging path is writable. URL/error details
never leave this worker. The parent enforces a hard wall-clock deadline and
kills/reaps this process, including when DNS or a decoder stalls.
"""
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
from urllib.parse import urljoin, urlsplit
import warnings

MAX_BYTES = 10 * 1024 * 1024
FORMATS = {'JPEG': ('image/jpeg', 'jpg'), 'PNG': ('image/png', 'png'), 'WEBP': ('image/webp', 'webp')}


class ImageError(Exception):
    """Only fixed, public error categories may cross the worker boundary."""


def public_address(value):
    ip = ipaddress.ip_address(value)
    # IPv4 mappings/translation and scoped IPv6 are unnecessary for uploads.
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and '%' not in value and not (
        isinstance(ip, ipaddress.IPv6Address) and (ip.ipv4_mapped or ip.sixtofour or ip.teredo))


def destination(url):
    """Resolve once, validate every address, then connect to one pinned IP.

    TLS still authenticates the original hostname. No ambient proxy, cookie,
    Authorization, or caller credential is used.
    """
    try:
        p = urlsplit(url)
        if (p.scheme != 'https' or not p.hostname or p.port not in (None, 443)
                or p.username is not None or p.password is not None or p.fragment
                or '\\' in url or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)
                or len(url) > 16384):
            raise ValueError
        host = p.hostname.encode('idna').decode('ascii')
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or not all(public_address(entry[4][0]) for entry in addresses):
            raise ValueError
        return p, host, addresses[0]
    except (ValueError, UnicodeError):
        raise ImageError('UnsafeURL') from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, port=443, timeout=5, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        family, kind, protocol, _, target = self.address
        raw = socket.socket(family, kind, protocol)
        try:
            raw.settimeout(5)
            raw.connect(target)
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def download(url, path):
    for redirect in range(4):
        parsed, host, address = destination(url)
        connection = PinnedHTTPS(host, address)
        try:
            target = parsed.path or '/'
            if parsed.query:
                target += '?' + parsed.query
            connection.request('GET', target, headers={'Accept': 'image/png,image/jpeg,image/webp', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if redirect == 3 or not location:
                    raise ImageError('RedirectLimit')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                return {'error_code': 'DownloadRejected', 'http_status': response.status}
            if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise ImageError('UnsupportedEncoding')
            length = response.getheader('Content-Length')
            if length is not None and (not length.isdecimal() or int(length) > MAX_BYTES):
                raise ImageError('ImageTooLarge')
            size = 0
            with path.open('wb') as output:
                while chunk := response.read(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ImageError('ImageTooLarge')
                    output.write(chunk)
            if not size or (length is not None and size != int(length)):
                raise ImageError('IncompleteDownload')
            return {'http_status': 200}
        finally:
            connection.close()
    raise ImageError('RedirectLimit')


def validate(path):
    """Decode only supported static formats, with process memory/CPU bounds.

    Pillow format detection is authoritative; response and caller MIME claims
    are advisory. Original bytes are preserved, not transcoded.
    https://pillow.readthedocs.io/en/stable/reference/Image.html
    """
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 32_000_000
    warnings.simplefilter('error', Image.DecompressionBombWarning)
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ImageError('ImageTooLarge')
    with Image.open(path, formats=list(FORMATS)) as image:
        fmt, width, height = image.format, image.width, image.height
        if width > 8192 or height > 8192 or width * height > 32_000_000:
            raise ImageError('ImageDimensionsExceeded')
        if getattr(image, 'is_animated', False) or getattr(image, 'n_frames', 1) != 1:
            raise ImageError('AnimatedImageUnsupported')
        image.verify()
    with Image.open(path, formats=[fmt]) as image:
        image.load()
    mime, extension = FORMATS[fmt]
    return dict(mime_type=mime, extension=extension, width=width, height=height,
                size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    try:
        operation, filename = sys.argv[1:]
        path = Path(filename)
        if operation == 'download':
            result = download(json.loads(sys.stdin.read(20000))['url'], path)
        elif operation == 'validate':
            result = validate(path)
        else:
            raise ImageError('InvalidOperation')
    except ImageError as error:
        result = {'error_code': str(error)}
    except Exception:
        result = {'error_code': 'DownloadFailed' if sys.argv[1] == 'download' else 'InvalidImage'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
