from .config import PDFConfig
from .library import Library, LibraryError

config=PDFConfig.from_env()
library=Library(config) if config.enabled else None

def require_library():
    if library is None or not library.started:
        raise LibraryError('PDF library disabled or unavailable. Operator must configure private storage and exclusively GM-trusted authenticated MCP access.')
    return library
