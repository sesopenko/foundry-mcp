"""Internal preview contracts, independent of decoder/transfer implementation."""
import itertools
import unittest

from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from foundry_mcp_server.mcp_server.image_preview_models import (
    Crop, ImageInfoRequest, ImageUrlRequest, ImageInfoResult, ImageUrlResult,
)
from foundry_mcp_server.mcp_server.image_uploads import UploadRequest
from foundry_mcp_server.mcp_server.journal_images import BrowseImagesRequest
from foundry_mcp_server.image_preview_errors import MESSAGES, preview_error

IMAGE = dict(source='public', directory='icons/svg', src='icons/svg/anchor.svg')
INFO = dict(source_id='opaque_handle', source_expires_at='2026-11-11T20:00:00Z',
    width=10000, height=5000, mime_type='image/png', size_bytes=120000, frame_policy='still')
URL = dict(source_id=INFO['source_id'], source_expires_at=INFO['source_expires_at'],
    url='https://preview.example/image-previews/8f780792-0661-47fc-8903-12f68a152793.png',
    expires_at='2026-11-18T19:30:00Z', source_width=10000, source_height=5000,
    region=dict(x=7200, y=3100, width=1280, height=960), width=1280, height=960,
    mime_type='image/png', size_bytes=100000)


class PreviewModelsTests(unittest.TestCase):
    def test_errors_are_actionable_and_never_reflect_unknown_native_text(self):
        for code in MESSAGES:
            error = str(preview_error(code, width=10000, height=5000))
            self.assertTrue(error.startswith(code + ':'))
            self.assertIn('width=10000, height=5000', error)
        self.assertNotIn('secret', str(preview_error('secret native URL')))
        self.assertNotIn('width=', str(preview_error('InvalidCrop', width=True, height=5000)))

    def test_every_input_combination(self):
        values = dict(image=IMAGE, src='worlds/test/α image.png?cache=1', map=dict(scene_uuid='Scene.one',level_id='floor',role='background'),source_id='opaque_handle')
        for model, names in [(ImageInfoRequest, ['image', 'src','map']), (ImageUrlRequest, list(values))]:
            for enabled in itertools.product([False, True], repeat=len(names)):
                args = {name: values[name] for name, yes in zip(names, enabled) if yes}
                with self.subTest(model=model.__name__, selectors=list(args)):
                    if sum(enabled) == 1:
                        expected={**args,**({'map_notes':False} if model is ImageUrlRequest else {})}
                        self.assertEqual(model.model_validate(args).model_dump(exclude_none=True), expected)
                    else:
                        with self.assertRaises(ValidationError):
                            model.model_validate(args)

    def test_extras_nulls_and_wrong_tool_fields(self):
        for model in (ImageInfoRequest, ImageUrlRequest):
            flag=dict(map_notes=False) if model is ImageInfoRequest else dict(map_notes=None)
            for bad in [dict(extra=True), dict(map={}), flag, dict(src=None), dict(image=None)]:
                with self.subTest(model=model.__name__, bad=bad), self.assertRaises(ValidationError):
                    model.model_validate(dict(src='icons/svg/anchor.svg', **bad) if 'src' not in bad else bad)
        for bad in [dict(crop=URL['region']), dict(source_id='handle')]:
            with self.assertRaises(ValidationError):
                ImageInfoRequest.model_validate(dict(image=IMAGE, **bad))

    def test_selector_contract_is_reused_without_coercion(self):
        for image in [dict(source='s3', directory='portraits', bucket='my-bucket', src='https://bucket.example/portraits/a.png?signature=private'),
                dict(source='data', directory='worlds/test', src='worlds/test/α%20image.png'), IMAGE]:
            self.assertEqual(ImageInfoRequest(image=image).image.model_dump(exclude_none=True), image)
        for patch in [dict(bucket=None), dict(bucket='irrelevant'), dict(directory='../private'), dict(directory='%2e%2e/private'),
                dict(directory='/etc'), dict(source='s3'), dict(src='javascript:a.png'), dict(src='x.txt'), dict(src=''), dict(src=True), dict(directory=1)]:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                ImageInfoRequest(image={**IMAGE, **patch})
        for bad in ['', 'x.txt', 'javascript:a.png', True, 1, 'a\n.png']:
            with self.subTest(src=bad), self.assertRaises(ValidationError):
                ImageInfoRequest(src=bad)

    def test_crop_strictness_and_error_category(self):
        good = dict(x=0, y=0, width=1, height=1)
        bad = [None, True, [], {}, {**good, 'extra': 1}]
        for field in good:
            for value in [True, False, 1.0, '1', -1, None, 32769]:
                bad.append({**good, field: value})
        bad += [{**good, 'width': 0}, {**good, 'height': 0}]
        for value in bad:
            with self.subTest(crop=value), self.assertRaises(ValidationError) as caught:
                ImageUrlRequest(image=IMAGE, crop=value) if value is not None else Crop.model_validate(value)
            self.assertIn('InvalidCrop', str(caught.exception))
        self.assertEqual(Crop(**good).check_containment(1, 1).model_dump(), good)
        with self.assertRaisesRegex(ToolError, 'InvalidCrop.*width=1, height=1'):
            Crop(x=1, y=0, width=1, height=1).check_containment(1, 1)

    def test_complete_valid_results_and_original_region_output_distinctions(self):
        self.assertEqual(ImageInfoResult(**INFO).model_dump(), INFO)
        self.assertEqual(ImageUrlResult(**URL).model_dump(), URL)
        self.assertEqual(ImageInfoResult(**{**INFO, 'frame_policy': 'first_frame'}).frame_policy, 'first_frame')
        full = {**URL, 'region': dict(x=0, y=0, width=10000, height=5000), 'width': 2048, 'height': 1024}
        self.assertEqual(ImageUrlResult(**full).source_width, 10000)

    def test_results_reject_malformed_metadata(self):
        for model, good, changes in [
            (ImageInfoResult, INFO, [dict(width=True), dict(height=1.0), dict(size_bytes=0), dict(size_bytes=128*1024*1024+1),
                dict(width=12000, height=12000), dict(frame_policy='all'), dict(mime_type='text/plain'), dict(source_id='bad/path')]),
            (ImageUrlResult, URL, [dict(width=1281), dict(width=2049), dict(width=2048, height=2048, region=dict(x=0,y=0,width=4096,height=4096)),
                dict(region=dict(x=9999,y=0,width=2,height=1)), dict(source_width=32768,source_height=32768),
                dict(size_bytes=2*1024*1024+1), dict(mime_type='image/jpeg'), dict(height=False)]),
        ]:
            for change in [*changes, dict(extra=True), dict(source_expires_at='2026-11-11'), dict(source_expires_at='2026-11-11T20:00:00'),
                    dict(source_expires_at='2026-02-30T20:00:00Z'), dict(source_expires_at='2026-11-11T20:00:00+01:00')]:
                with self.subTest(model=model.__name__, change=change), self.assertRaises(ValidationError):
                    model.model_validate({**good, **change})

    def test_capability_url_shape_is_exact_and_format_bound(self):
        for value in [URL['url']+'?probe=1', URL['url']+'#fragment', URL['url'].replace('https:', 'http:'),
                URL['url'].replace('preview.example', 'user:secret@preview.example'), URL['url'].replace('.png', '.webp'),
                URL['url'].replace('-47fc-', '-17fc-'), URL['url'].replace('/image-previews/', '/originals/'),
                URL['url'].replace('preview.example', ''), URL['url']+'?']:
            with self.subTest(url=value), self.assertRaises(ValidationError):
                ImageUrlResult(**{**URL, 'url': value})

    def test_existing_browse_upload_schemas_keep_bounds_and_source_scope(self):
        browse = BrowseImagesRequest()
        self.assertEqual((browse.limit, browse.max_bytes), (10, 8000))
        self.assertIs(ImageInfoRequest.model_fields['image'].annotation.__args__[0], type(ImageInfoRequest(image=IMAGE).image))
        self.assertNotIn('source_id', BrowseImagesRequest.model_fields)
        upload = UploadRequest(file=dict(download_url='https://example.org/file', file_id='file'), directory='assets', filename='α image')
        self.assertFalse(upload.overwrite)
        for bad in [dict(source='public'), dict(source_id='handle'), dict(filename='image.png')]:
            with self.assertRaises(ValidationError):
                UploadRequest.model_validate({**upload.model_dump(), **bad})
