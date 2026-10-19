"""
Views for PixelForge — Image to Pixel Art Converter.
"""

import base64
import io
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from PIL import Image

from .forms import ImageUploadForm, CONVERSION_MODE_CHOICES, COLOR_COUNT_CHOICES
from .image_processor import (
    convert_to_pixel_art,
    pixelate,
    quantize_colors,
    image_to_bytes,
    load_image_from_bytes,
    get_image_info,
    _to_rgb,
)

logger = logging.getLogger(__name__)

# Session key where the processed PNG bytes are temporarily stored (base64-encoded)
SESSION_KEY_RESULT = 'pixelforge_result_b64'
SESSION_KEY_ORIGINAL = 'pixelforge_original_b64'
SESSION_KEY_META = 'pixelforge_meta'


def index(request):
    """Render the main upload / conversion page."""
    form = ImageUploadForm()
    context = {
        'form': form,
        'color_choices': COLOR_COUNT_CHOICES,
        'mode_choices': CONVERSION_MODE_CHOICES,
    }
    return render(request, 'converter/index.html', context)


@require_http_methods(['POST'])
@csrf_protect
def convert_image(request):
    """
    Handle image upload and conversion.

    Accepts a multipart POST with:
        - image         : the uploaded file
        - pixel_size    : int [2–64]
        - color_count   : one of {4, 8, 16, 32, 64, 128}
        - conversion_mode : 'pixel_art' | 'pixelate' | 'quantize'

    Returns a JSON response containing:
        - success       : bool
        - original_b64  : base64-encoded PNG of the original image
        - result_b64    : base64-encoded PNG of the processed image
        - original_info : {width, height, mode, format}
        - result_info   : {width, height, mode, format}
        - mode_label    : human-readable conversion mode
        - errors        : dict of field-level errors (on failure)
    """
    form = ImageUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    uploaded_file = form.cleaned_data['image']
    pixel_size = form.cleaned_data['pixel_size']
    color_count = form.cleaned_data['color_count']
    conversion_mode = form.cleaned_data['conversion_mode']

    try:
        # ------------------------------------------------------------------ #
        # Load and validate the image via Pillow (defence in depth)           #
        # ------------------------------------------------------------------ #
        raw_bytes = uploaded_file.read()
        original_image = Image.open(io.BytesIO(raw_bytes))
        original_image.verify()  # raises if corrupted

        # Re-open after verify() (verify() exhausts the stream)
        original_image = Image.open(io.BytesIO(raw_bytes))
        original_image.load()    # force decode

        # ------------------------------------------------------------------ #
        # Serialise original as PNG for preview                               #
        # ------------------------------------------------------------------ #
        original_rgb = _to_rgb(original_image.copy())
        original_png_bytes = image_to_bytes(original_rgb, fmt='PNG')
        original_b64 = base64.b64encode(original_png_bytes).decode('ascii')
        original_info = get_image_info(original_image)

        # ------------------------------------------------------------------ #
        # Run the selected conversion algorithm                               #
        # ------------------------------------------------------------------ #
        if conversion_mode == 'pixelate':
            result_image = pixelate(original_image.copy(), pixel_size)
            mode_label = 'Pixelation Only'
        elif conversion_mode == 'quantize':
            result_image = quantize_colors(original_image.copy(), color_count)
            mode_label = 'Color Reduction Only'
        else:  # 'pixel_art' (default)
            result_image = convert_to_pixel_art(original_image.copy(), pixel_size, color_count)
            mode_label = 'Pixel Art (Pixelation + Color Reduction)'

        # ------------------------------------------------------------------ #
        # Serialise result as PNG                                              #
        # ------------------------------------------------------------------ #
        result_png_bytes = image_to_bytes(result_image, fmt='PNG')
        result_b64 = base64.b64encode(result_png_bytes).decode('ascii')
        result_info = get_image_info(result_image)

        # ------------------------------------------------------------------ #
        # Store in session for the download endpoint                          #
        # ------------------------------------------------------------------ #
        request.session[SESSION_KEY_RESULT] = result_b64
        request.session[SESSION_KEY_ORIGINAL] = original_b64
        request.session[SESSION_KEY_META] = {
            'original_info': original_info,
            'result_info': result_info,
            'mode_label': mode_label,
            'pixel_size': pixel_size,
            'color_count': color_count,
            'conversion_mode': conversion_mode,
            'filename': uploaded_file.name,
        }

        return JsonResponse({
            'success': True,
            'original_b64': original_b64,
            'result_b64': result_b64,
            'original_info': original_info,
            'result_info': result_info,
            'mode_label': mode_label,
            'pixel_size': pixel_size,
            'color_count': color_count,
        })

    except Exception as exc:
        logger.exception('Image conversion failed: %s', exc)
        return JsonResponse(
            {'success': False, 'errors': {'image': [str(exc)]}},
            status=500,
        )


@require_http_methods(['GET'])
def download_image(request):
    """
    Serve the most recently converted image as a downloadable PNG file.

    Reads from the session — no files are written to disk.
    Returns HTTP 404 if no converted image exists in the session.
    """
    result_b64 = request.session.get(SESSION_KEY_RESULT)
    if not result_b64:
        return HttpResponse(
            'No converted image found. Please convert an image first.',
            status=404,
            content_type='text/plain',
        )

    try:
        png_bytes = base64.b64decode(result_b64)
        meta = request.session.get(SESSION_KEY_META, {})
        original_filename = meta.get('filename', 'image')
        # Strip extension and append _pixel_art.png
        base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        download_name = f'{base_name}_pixel_art.png'

        response = HttpResponse(png_bytes, content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{download_name}"'
        response['Content-Length'] = len(png_bytes)
        return response

    except Exception as exc:
        logger.exception('Download failed: %s', exc)
        return HttpResponse('Failed to retrieve converted image.', status=500, content_type='text/plain')
