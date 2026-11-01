"""Typed ChatGPT file handoff and User Data mutations; no game-system semantics."""
import asyncio
import base64
import inspect
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Annotated, Literal
from urllib.parse import unquote

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, RootModel, field_validator

from .selective import SelectiveTool
from .selective_models import Model
from .journal_image_models import ImageLocation, ImageSelector, valid_directory
from .journal_images import DirectoryCapabilities, ImageFollow
from .server import mcp
from foundry_mcp_server.ws.connection import RpcError
from foundry_mcp_server.image_worker import MAX_BYTES


def valid_name(value, *, stem=False):
    if (not value or value != value.strip() or len(value) > 200 or len(value.encode('utf-8')) > 240 or
            re.search(r'[\\/\x00-\x1f\x7f<>:"|?*%#]', value) or value in ('.', '..') or value.endswith('.') or
            (stem and re.search(r'\.(?:jpe?g|png|webp)$', value, re.I))):
        raise ValueError('Use a single name without paths, reserved characters, or an image extension for filenames')
    return value


class DirectoryRequest(Model):
    directory: str = Field(max_length=2048, description='Exact existing User Data directory from browse_journal_images; not Core Data, S3, a journal folder or a host path. Empty means User Data root (folder creation only).')

    @field_validator('directory')
    @classmethod
    def check_directory(cls, value):
        if not valid_directory(value) or '//' in value or value.endswith('/'):
            raise ValueError('Use an exact source-relative directory without traversal or a trailing slash')
        return value

    @property
    def max_bytes(self):
        return 8000


class CreateDirectoryRequest(DirectoryRequest):
    name: str = Field(min_length=1, max_length=200, description='One new child directory name, at most240 UTF-8 bytes. No paths, traversal or recursive parent creation; spaces and Unicode are supported.')

    @field_validator('name')
    @classmethod
    def check_name(cls, value):
        return valid_name(value)


class OpenAIFile(Model):
    download_url: str = Field(min_length=1, max_length=16384, description='Temporary HTTPS URL supplied by ChatGPT file handoff. Never invent a URL or use sandbox:/file IDs as URLs.')
    file_id: str = Field(min_length=1, max_length=512, description='Opaque ChatGPT file identifier; not a Foundry ID. Retrieval uses download_url, not a constructed endpoint.')
    mime_type: str = Field(default='', max_length=256, description='Optional host MIME hint; actual decoded bytes determine the accepted type.')
    file_name: str = Field(default='', max_length=1024, description='Optional host filename hint; does not control the saved name.')


class UploadRequest(DirectoryRequest):
    file: OpenAIFile
    filename: str = Field(min_length=1, max_length=200, description='Save name WITHOUT an extension, at most240 UTF-8 bytes. The detected image format adds .jpg, .png or .webp. Spaces and Unicode supported; no paths or reserved characters.')
    overwrite: bool = Field(default=False, description='False rejects existing files. True PERMANENTLY replaces an existing destination, with no backup or undo; documents using that path may display the replacement.')

    @field_validator('filename')
    @classmethod
    def check_filename(cls, value):
        return valid_name(value, stem=True)


class Identity(Model):
    world_id: str = Field(min_length=1, max_length=256)
    user_id: str = Field(min_length=1, max_length=256)


class Preflight(Identity):
    location: ImageLocation
    capabilities: DirectoryCapabilities


class DirectoryResult(Preflight):
    status: Literal['created', 'already_exists']
    next_call: ImageFollow


class ImageMetadata(Model):
    mime_type: Literal['image/jpeg', 'image/png', 'image/webp']
    width: int = Field(ge=1, le=8192)
    height: int = Field(ge=1, le=8192)
    size_bytes: int = Field(ge=1, le=MAX_BYTES)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class UploadSuccess(ImageMetadata, Identity):
    status: Literal['uploaded']
    filename: str = Field(max_length=205)
    overwritten: bool
    image: ImageSelector


class UploadUnknown(Identity):
    status: Literal['upload_outcome_unknown']
    candidate_path: str = Field(min_length=1, max_length=4096)
    error_code: Literal['UploadFailed', 'VerificationFailed', 'BridgeUnavailable', 'InvalidFoundryResponse']
    message: str = Field(max_length=512)


UploadResult = RootModel[Annotated[UploadSuccess | UploadUnknown, Field(discriminator='status')]]
_operation_lock = asyncio.Lock()


async def worker(operation, path, payload=b'', timeout=30):
    """Kill and reap a stalled worker, including cancellation; never expose stderr."""
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'foundry_mcp_server.image_worker', operation, str(path),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        async with asyncio.timeout(timeout):
            stdout, _ = await process.communicate(payload)
        if process.returncode != 0 or len(stdout) > 4096:
            raise ToolError('ImageProcessingFailed: image worker rejected the file; use a smaller valid static image.')
        result = json.loads(stdout)
        if 'error_code' in result:
            code = result['error_code']
            # Worker reports only fixed categories, not upstream content or URLs.
            if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z]{1,64}', code):
                code = 'ImageProcessingFailed'
            status = result.get('http_status')
            detail = f' (HTTP {status})' if type(status) is int and 100 <= status <= 599 else ''
            raise ToolError(f'{code}{detail}: use a fresh public HTTPS file URL and a valid static JPEG, PNG or WebP within the published limits.')
        return result
    except asyncio.TimeoutError:
        raise ToolError('ImageProcessingTimeout: download/decoding deadline exceeded; use a fresh URL or smaller image.') from None
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()


async def retrieve_image(url, path):
    await worker('download', path, json.dumps({'url': url}).encode(), 30)
    result = await worker('validate', path, timeout=10)
    extension = result.pop('extension')
    meta = ImageMetadata.model_validate(result)
    if extension != {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[meta.mime_type] or meta.width * meta.height > 32_000_000:
        raise ToolError('InvalidImage: decoder returned inconsistent metadata.')
    return meta, extension


def manager_and_socket():
    from .tools import _foundry_manager
    socket = _foundry_manager.websockets.get('gm') if _foundry_manager else None
    if socket is None:
        raise ToolError('BridgeUnavailable: connect the existing ready GM browser.')
    return _foundry_manager, socket


async def call(manager, socket, method, params, timeout=15):
    # No await between checking ownership and manager.call capturing its socket.
    if manager.websockets.get('gm') is not socket:
        raise ConnectionError('GM socket changed')
    return await manager.call('gm', method, params, timeout=timeout)


def rpc_error(error):
    # Never echo arbitrary browser errors or private native API messages.
    code = error.error.get('code', error.error.get('type', 'WriteFailed'))
    messages = {
        'FileExists': 'Destination already exists. Choose another filename or explicitly set overwrite=true for permanent replacement.',
        'PermissionDenied': 'FilePicker denies this operation. Browse User Data and select a permitted directory.',
        'Busy': 'Another image operation is active; retry after it completes.',
        'ContextChanged': 'World or GM changed. Reconnect and browse again.',
        'BrowseFailed': 'Destination is missing, denied or unavailable. Browse an existing directory.',
        'DirectoryTooLarge': 'Choose a directory below10000 entries/2MiB of listing data.',
        'NotReady': 'Wait for the existing ready GM world.',
        'UnsupportedVersion': 'These tools require Foundry14.',
        'UnsupportedCapability': 'Check the configured public FilePicker and matching module version.',
        'CreateDirectoryFailed': 'Creation failed; browse the parent before retrying.',
        'InvalidRequest': 'Check names, directory and the published schema.',
    }
    if code not in messages:
        code = 'WriteFailed'
    return ToolError(f'{code}: {messages.get(code, "Operation failed; inspect the destination before retrying.")}')


async def create_image_directory(request):
    """Create one folder in Foundry User Data, as the connected ready core14 GM.

    Use browse_journal_images first: capabilities.can_create_directory must be
    true. directory is the existing User Data parent from its returned selector;
    name is one child, not a path. Empty directory means User Data root. No Core
    Data/S3 writes, recursive creation, deletion, privacy changes or PF2e semantics.
    Returns status(created/already_exists),world_id,user_id,location,capabilities,
    next_call for browse_journal_images. Existing verified folders are reused.
    Permissions are advisory until rechecked by Foundry at mutation time.
    FileExists means a file occupies the name; choose another name. BrowseFailed
    is missing/denied/unavailable, not proof of absence. After timeout, browse the
    parent before retrying. BridgeUnavailable/NotReady: connect the ready GM;
    PermissionDenied: choose a writable User Data parent. InvalidRequest: inspect
    the schema. Example: {"directory":"","name":"Generated portraits"}.
    """
    if _operation_lock.locked():
        raise ToolError('Busy: another image operation is active; retry afterward.')
    async with _operation_lock:
        manager, socket = manager_and_socket()
        try:
            result = DirectoryResult.model_validate(await call(manager, socket, 'createImageDirectory', request.model_dump()))
            expected = '/'.join(filter(None, (request.directory, request.name)))
            if (result.location.source != 'data' or result.location.bucket is not None or unquote(result.location.directory) != unquote(expected) or
                    result.next_call.arguments != result.location):
                raise ValueError
            return result.model_dump(exclude_none=True)
        except RpcError as error:
            raise rpc_error(error) from None
        except (TimeoutError, ConnectionError, RuntimeError):
            raise ToolError('OutcomeUnknown: connection lost or timed out; browse the parent before retrying folder creation.') from None
        except ValueError:
            raise ToolError('InvalidFoundryResponse: folder may exist; browse the parent before retrying.') from None


async def upload_image(request):
    """Save a ChatGPT-provided image to an existing Foundry User Data directory.

    Use browse_journal_images and optionally create_image_directory first. Requires
    capabilities.can_upload and the connected ready core14 GM. All game systems;
    no Core Data/S3 writes or automatic journal/Actor changes. ChatGPT supplies
    file via openai/fileParams: required download_url/file_id, optional MIME/name
    hints. Generated-image handoff depends on ChatGPT; do not invent URLs or pass
    sandbox paths/base64. filename is WITHOUT extension; validated bytes determine
    .jpg/.png/.webp. No conversion. overwrite=false rejects collisions (FileExists).
    overwrite=true PERMANENTLY replaces that exact file, with no backup or undo;
    existing journals/tokens referencing it may display the replacement.

    HTTPS/public destinations only, up to3 redirects; download30s/10MiB,
    decode10s, static JPEG/PNG/WebP only, axes<=8192 and pixels<=32 million.
    MIME hints are advisory. Original validated bytes are retained. One active
    image operation; Busy means retry later. Filename/directory validation occurs
    before network access. Source URL/file ID and bytes never appear in results.
    User Data root permits folders but not uploads; choose/create a child.

    Returns status=uploaded,world_id,user_id,filename,mime_type,width,height,
    size_bytes,sha256,overwritten,image{source,directory,src}. Pass image directly
    to write_journal action.operation=embed_image after its normal writing guidance
    and page-revision checks; no extra image discovery call is needed. This does
    not prove player access. The exact canonical src is not a document UUID.

    Upload/verification timeout or disconnect returns upload_outcome_unknown with
    candidate_path,error_code,message,world_id,user_id: a file may already exist;
    inspect it before retrying, especially replacements. Never automatically retry
    writes. Public browse-then-upload cannot lock out external concurrent writers.
    BridgeUnavailable: reconnect GM; PermissionDenied/BrowseFailed: browse another
    User Data destination; download/validation errors: supply a fresh accessible
    URL or smaller valid image. InvalidRequest: inspect the schema. Upload RPC
    deadline60s; receipt<=8000 JSON bytes. No bulk mode or pagination.
    """
    if _operation_lock.locked():
        raise ToolError('Busy: another image operation is active; retry afterward.')
    async with _operation_lock:
        manager, socket = manager_and_socket()
        try:
            preflight = Preflight.model_validate(await call(manager, socket, 'prepareImageUpload', {'directory': request.directory}))
            if (preflight.location.source != 'data' or preflight.location.bucket is not None or
                    unquote(preflight.location.directory) != unquote(request.directory) or not preflight.capabilities.can_upload):
                raise ValueError
        except RpcError as error:
            raise rpc_error(error) from None
        except (TimeoutError, ConnectionError, RuntimeError):
            raise ToolError('BridgeUnavailable: reconnect the ready GM and browse the destination.') from None
        except ValueError:
            raise ToolError('InvalidFoundryResponse: upload preflight failed its contract; check module/server versions.') from None
        with tempfile.TemporaryDirectory(prefix='foundry-image-') as staging:
            path = Path(staging) / 'image'
            metadata, extension = await retrieve_image(request.file.download_url, path)
            content = path.read_bytes()
            import hashlib
            if len(content) != metadata.size_bytes or hashlib.sha256(content).hexdigest() != metadata.sha256:
                raise ToolError('InvalidImage: staged image changed before transfer.')
            filename = request.filename + '.' + extension
            destination = preflight.location.directory
            candidate = destination + '/' + filename
            identity = dict(world_id=preflight.world_id, user_id=preflight.user_id)
            params = dict(directory=destination, filename=request.filename, overwrite=request.overwrite,
                          **identity, **metadata.model_dump(), content=base64.b64encode(content).decode('ascii'))
            try:
                raw = await call(manager, socket, 'uploadImage', params, timeout=60)
            except RpcError as error:
                raise rpc_error(error) from None
            except (TimeoutError, ConnectionError, RuntimeError):
                return dict(status='upload_outcome_unknown', **identity, candidate_path=candidate,
                    error_code='BridgeUnavailable', message='File may have been stored. Inspect the destination before retrying; replacements have no undo.')
            try:
                result = UploadResult.model_validate(raw).root
                if result.world_id != preflight.world_id or result.user_id != preflight.user_id:
                    raise ValueError
                if isinstance(result, UploadSuccess):
                    if (result.filename != filename or result.image.source != 'data' or result.image.bucket is not None or
                            result.image.directory != destination or unquote(result.image.src) != unquote(candidate) or
                            (result.overwritten and not request.overwrite) or
                            any(getattr(result, field) != value for field, value in metadata.model_dump().items())):
                        raise ValueError
                elif result.candidate_path != candidate:
                    raise ValueError
                return result.model_dump(exclude_none=True)
            except ValueError:
                return dict(status='upload_outcome_unknown', **identity, candidate_path=candidate,
                    error_code='InvalidFoundryResponse', message='Upload receipt was invalid; file may exist. Inspect the destination before retrying.')


for name, request, response, handler in [
    ('create_image_directory', CreateDirectoryRequest, DirectoryResult, create_image_directory),
    ('upload_image', UploadRequest, UploadResult, upload_image),
]:
    mcp.add_tool(SelectiveTool(name=name, description=inspect.cleandoc(handler.__doc__),
        parameters=request.model_json_schema(), output_schema=response.model_json_schema(),
        request_model=request, response_model=response, handler=handler,
        meta={'openai/fileParams': ['file']} if name == 'upload_image' else None,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=name == 'upload_image',
            idempotentHint=False, openWorldHint=name == 'upload_image')))
