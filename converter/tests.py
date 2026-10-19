"""
Automated tests for PixelForge converter.

Run with:
    python manage.py test converter

Tests cover:
- Index page renders correctly
- Pixelation algorithm produces distinct output
- Color quantization reduces palette
- Combined conversion produces pixel art
- Invalid file upload is rejected
- Unsupported extension is rejected
- Invalid pixel_size is rejected
- Invalid color_count is rejected
- PNG output generation
- Download response content-type
- Aspect ratio preservation
- Different settings produce different outputs
"""

import io
import base64
from PIL import Image

from django.test import TestCase, Client
from django.urls import reverse

from .image_processor import (
    pixelate,
    quantize_colors,
    convert_to_pixel_art,
    image_to_bytes,
    load_image_from_bytes,
    get_image_info,
    _to_rgb,
    _validate_pixel_size,
    _validate_color_count,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_image(width=100, height=80, mode='RGB', color=(120, 80, 200)) -> Image.Image:
    """Create a small in-memory test image."""
    img = Image.new(mode, (width, height), color)
    # Add some variation so quantization has something to work with
    for x in range(0, width, 10):
        for y in range(0, height, 10):
            img.putpixel((x, y), (255 - x % 128, y % 255, x + y % 100))
    return img


def _image_to_upload_file(image: Image.Image, fmt='PNG', filename='test.png'):
    """Convert a PIL Image to a Django-compatible in-memory upload file."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    buf.seek(0)
    content_type_map = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}
    return SimpleUploadedFile(filename, buf.read(), content_type=content_type_map.get(fmt, 'image/png'))


def _post_convert(client, image, pixel_size=8, color_count=16, mode='pixel_art', filename='test.png', fmt='PNG'):
    """Post to the convert endpoint and return the response."""
    upload = _image_to_upload_file(image, fmt=fmt, filename=filename)
    return client.post(
        reverse('converter:convert'),
        {
            'image': upload,
            'pixel_size': pixel_size,
            'color_count': color_count,
            'conversion_mode': mode,
        },
        format='multipart',
    )


# ---------------------------------------------------------------------------
# Unit tests — image_processor module
# ---------------------------------------------------------------------------

class ImageProcessorUnitTests(TestCase):

    def test_validate_pixel_size_clamps_below(self):
        self.assertEqual(_validate_pixel_size(0), 2)
        self.assertEqual(_validate_pixel_size(-5), 2)

    def test_validate_pixel_size_clamps_above(self):
        self.assertEqual(_validate_pixel_size(100), 64)

    def test_validate_pixel_size_valid(self):
        self.assertEqual(_validate_pixel_size(16), 16)

    def test_validate_color_count_nearest(self):
        # 10 → nearest allowed is 8
        self.assertEqual(_validate_color_count(10), 8)

    def test_validate_color_count_exact(self):
        for v in (4, 8, 16, 32, 64, 128):
            self.assertEqual(_validate_color_count(v), v)

    def test_to_rgb_from_rgba(self):
        img = Image.new('RGBA', (10, 10), (255, 0, 0, 128))
        result = _to_rgb(img)
        self.assertEqual(result.mode, 'RGB')

    def test_to_rgb_from_grayscale(self):
        img = Image.new('L', (10, 10), 128)
        result = _to_rgb(img)
        self.assertEqual(result.mode, 'RGB')

    def test_to_rgb_already_rgb(self):
        img = Image.new('RGB', (10, 10), (100, 100, 100))
        result = _to_rgb(img)
        self.assertEqual(result.mode, 'RGB')
        self.assertIs(result, img)  # same object returned

    # --- pixelate -----------------------------------------------------------

    def test_pixelate_preserves_dimensions(self):
        img = _make_test_image(100, 80)
        result = pixelate(img, pixel_size=8)
        self.assertEqual(result.size, (100, 80))

    def test_pixelate_output_differs_from_input(self):
        img = _make_test_image(100, 80)
        result = pixelate(img, pixel_size=10)
        self.assertNotEqual(list(img.getdata()), list(result.getdata()))

    def test_pixelate_is_rgb(self):
        img = _make_test_image(60, 60, mode='RGBA')
        result = pixelate(img, pixel_size=8)
        self.assertEqual(result.mode, 'RGB')

    def test_pixelate_large_pixel_size(self):
        img = _make_test_image(64, 64)
        result = pixelate(img, pixel_size=32)
        self.assertEqual(result.size, (64, 64))

    def test_pixelate_minimal_pixel_size(self):
        img = _make_test_image(50, 50)
        result = pixelate(img, pixel_size=2)
        self.assertEqual(result.size, (50, 50))

    # --- quantize_colors ----------------------------------------------------

    def test_quantize_preserves_dimensions(self):
        img = _make_test_image(100, 80)
        result = quantize_colors(img, color_count=8)
        self.assertEqual(result.size, (100, 80))

    def test_quantize_limits_colors(self):
        img = _make_test_image(100, 80)
        result = quantize_colors(img, color_count=4)
        unique_colors = len(set(result.getdata()))
        self.assertLessEqual(unique_colors, 4)

    def test_quantize_is_rgb(self):
        img = _make_test_image(60, 60)
        result = quantize_colors(img, color_count=16)
        self.assertEqual(result.mode, 'RGB')

    def test_quantize_fewer_colors_produces_different_result_than_more(self):
        img = _make_test_image(60, 60)
        r4 = quantize_colors(img.copy(), color_count=4)
        r64 = quantize_colors(img.copy(), color_count=64)
        # 4-color image should have fewer unique colors
        self.assertLessEqual(
            len(set(r4.getdata())),
            len(set(r64.getdata())),
        )

    # --- convert_to_pixel_art -----------------------------------------------

    def test_pixel_art_preserves_dimensions(self):
        img = _make_test_image(100, 80)
        result = convert_to_pixel_art(img, pixel_size=8, color_count=16)
        self.assertEqual(result.size, (100, 80))

    def test_pixel_art_is_rgb(self):
        img = _make_test_image(60, 60)
        result = convert_to_pixel_art(img, pixel_size=8, color_count=16)
        self.assertEqual(result.mode, 'RGB')

    def test_pixel_art_limits_colors(self):
        img = _make_test_image(80, 80)
        result = convert_to_pixel_art(img, pixel_size=8, color_count=8)
        unique_colors = len(set(result.getdata()))
        self.assertLessEqual(unique_colors, 8)

    def test_different_pixel_sizes_produce_different_output(self):
        img = _make_test_image(100, 80)
        r_small = convert_to_pixel_art(img.copy(), pixel_size=4, color_count=16)
        r_large = convert_to_pixel_art(img.copy(), pixel_size=32, color_count=16)
        self.assertNotEqual(list(r_small.getdata()), list(r_large.getdata()))

    def test_different_color_counts_produce_different_output(self):
        img = _make_test_image(80, 80)
        r_few = convert_to_pixel_art(img.copy(), pixel_size=8, color_count=4)
        r_many = convert_to_pixel_art(img.copy(), pixel_size=8, color_count=64)
        self.assertNotEqual(list(r_few.getdata()), list(r_many.getdata()))

    # --- PNG serialisation --------------------------------------------------

    def test_image_to_bytes_produces_valid_png(self):
        img = _make_test_image(50, 50)
        data = image_to_bytes(img, fmt='PNG')
        # PNG magic bytes: \x89PNG
        self.assertTrue(data[:4] == b'\x89PNG')

    def test_load_image_from_bytes_roundtrip(self):
        img = _make_test_image(40, 40)
        data = image_to_bytes(img, fmt='PNG')
        loaded = load_image_from_bytes(data)
        self.assertEqual(loaded.size, img.size)

    def test_get_image_info(self):
        img = _make_test_image(60, 45)
        info = get_image_info(img)
        self.assertEqual(info['width'], 60)
        self.assertEqual(info['height'], 45)
        self.assertEqual(info['mode'], 'RGB')

    # --- Aspect ratio -------------------------------------------------------

    def test_pixelate_preserves_aspect_ratio(self):
        w, h = 160, 90
        img = _make_test_image(w, h)
        result = pixelate(img, pixel_size=8)
        self.assertEqual(result.size, (w, h))

    def test_pixel_art_preserves_aspect_ratio(self):
        w, h = 200, 133
        img = _make_test_image(w, h)
        result = convert_to_pixel_art(img, pixel_size=10, color_count=16)
        self.assertEqual(result.size, (w, h))


# ---------------------------------------------------------------------------
# Integration tests — Django views
# ---------------------------------------------------------------------------

class ViewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_index_returns_200(self):
        response = self.client.get(reverse('converter:index'))
        self.assertEqual(response.status_code, 200)

    def test_index_contains_branding(self):
        response = self.client.get(reverse('converter:index'))
        self.assertContains(response, 'PixelForge')

    def test_convert_successful_pixel_art(self):
        img = _make_test_image(80, 80)
        response = _post_convert(self.client, img, pixel_size=8, color_count=16, mode='pixel_art')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('result_b64', data)
        self.assertIn('original_b64', data)

    def test_convert_successful_pixelate_only(self):
        img = _make_test_image(80, 80)
        response = _post_convert(self.client, img, mode='pixelate')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_convert_successful_quantize_only(self):
        img = _make_test_image(80, 80)
        response = _post_convert(self.client, img, mode='quantize')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_convert_result_is_valid_png(self):
        img = _make_test_image(60, 60)
        response = _post_convert(self.client, img)
        data = response.json()
        png_bytes = base64.b64decode(data['result_b64'])
        self.assertTrue(png_bytes[:4] == b'\x89PNG', 'Result is not a valid PNG')

    def test_convert_result_dimensions_match_original(self):
        img = _make_test_image(100, 75)
        response = _post_convert(self.client, img)
        data = response.json()
        self.assertEqual(data['result_info']['width'], 100)
        self.assertEqual(data['result_info']['height'], 75)

    def test_convert_missing_image_returns_400(self):
        response = self.client.post(reverse('converter:convert'), {
            'pixel_size': 8,
            'color_count': 16,
            'conversion_mode': 'pixel_art',
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

    def test_convert_invalid_pixel_size_below_min(self):
        img = _make_test_image(60, 60)
        response = _post_convert(self.client, img, pixel_size=0)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_convert_invalid_pixel_size_above_max(self):
        img = _make_test_image(60, 60)
        response = _post_convert(self.client, img, pixel_size=200)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_convert_invalid_color_count(self):
        img = _make_test_image(60, 60)
        response = _post_convert(self.client, img, color_count=7)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_convert_unsupported_extension(self):
        img = _make_test_image(60, 60)
        upload = _image_to_upload_file(img, fmt='PNG', filename='test.bmp')
        response = self.client.post(reverse('converter:convert'), {
            'image': upload,
            'pixel_size': 8,
            'color_count': 16,
            'conversion_mode': 'pixel_art',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_convert_non_image_file_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_file = SimpleUploadedFile('test.png', b'this is not an image', content_type='image/png')
        response = self.client.post(reverse('converter:convert'), {
            'image': fake_file,
            'pixel_size': 8,
            'color_count': 16,
            'conversion_mode': 'pixel_art',
        })
        self.assertIn(response.status_code, [400, 500])
        self.assertFalse(response.json()['success'])

    def test_download_without_conversion_returns_404(self):
        response = self.client.get(reverse('converter:download'))
        self.assertEqual(response.status_code, 404)

    def test_download_after_conversion_returns_png(self):
        img = _make_test_image(80, 80)
        # First convert
        _post_convert(self.client, img)
        # Then download
        response = self.client.get(reverse('converter:download'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')

    def test_download_content_disposition_filename(self):
        img = _make_test_image(80, 80)
        _post_convert(self.client, img, filename='myphoto.png')
        response = self.client.get(reverse('converter:download'))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('myphoto_pixel_art.png', response['Content-Disposition'])

    def test_different_pixel_sizes_produce_different_results_via_api(self):
        img = _make_test_image(80, 80)
        r1 = _post_convert(self.client, img, pixel_size=4, mode='pixelate')
        r2 = _post_convert(self.client, img, pixel_size=32, mode='pixelate')
        b1 = base64.b64decode(r1.json()['result_b64'])
        b2 = base64.b64decode(r2.json()['result_b64'])
        self.assertNotEqual(b1, b2)

    def test_convert_jpeg_upload(self):
        img = _make_test_image(80, 80)
        response = _post_convert(self.client, img, fmt='JPEG', filename='photo.jpg')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_convert_rgba_image(self):
        img = _make_test_image(60, 60, mode='RGBA', color=(100, 150, 200, 200))
        response = _post_convert(self.client, img, fmt='PNG', filename='image.png')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
