"""
Django forms for PixelForge image conversion.
"""
from django import forms
from django.conf import settings


CONVERSION_MODE_CHOICES = [
    ('pixel_art', 'Pixel Art (Pixelation + Color Reduction)'),
    ('pixelate', 'Pixelation Only'),
    ('quantize', 'Color Reduction Only'),
]

COLOR_COUNT_CHOICES = [
    (4,   '4 colors'),
    (8,   '8 colors'),
    (16,  '16 colors'),
    (32,  '32 colors'),
    (64,  '64 colors'),
    (128, '128 colors'),
]

PIXEL_SIZE_MIN = 2
PIXEL_SIZE_MAX = 64


class ImageUploadForm(forms.Form):
    """
    Validates image uploads and conversion parameters.

    Field validation is intentionally strict:
    - File extension must be one of the allowed types.
    - File content is verified by Pillow (not just MIME type).
    - File size is checked against MAX_UPLOAD_SIZE_BYTES.
    - pixel_size must be an integer in [PIXEL_SIZE_MIN, PIXEL_SIZE_MAX].
    - color_count must be one of the discrete allowed values.
    - conversion_mode must be one of the three defined modes.
    """

    image = forms.ImageField(
        label='Image',
        error_messages={
            'required': 'Please select an image file.',
            'invalid_image': 'The uploaded file is not a valid image.',
        },
    )
    pixel_size = forms.IntegerField(
        min_value=PIXEL_SIZE_MIN,
        max_value=PIXEL_SIZE_MAX,
        initial=8,
        label='Pixel Size',
        error_messages={
            'required': 'Pixel size is required.',
            'invalid': 'Pixel size must be a whole number.',
            'min_value': f'Pixel size must be at least {PIXEL_SIZE_MIN}.',
            'max_value': f'Pixel size must not exceed {PIXEL_SIZE_MAX}.',
        },
    )
    color_count = forms.ChoiceField(
        choices=COLOR_COUNT_CHOICES,
        initial=16,
        label='Color Palette',
        error_messages={
            'required': 'Color count is required.',
            'invalid_choice': 'Select a valid color count.',
        },
    )
    conversion_mode = forms.ChoiceField(
        choices=CONVERSION_MODE_CHOICES,
        initial='pixel_art',
        label='Conversion Mode',
        error_messages={
            'required': 'Conversion mode is required.',
            'invalid_choice': 'Select a valid conversion mode.',
        },
    )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            raise forms.ValidationError('No image was uploaded.')

        # Check file size
        max_bytes = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 10 * 1024 * 1024)
        if image.size > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise forms.ValidationError(
                f'File size exceeds the {max_mb} MB limit. '
                f'Please upload a smaller image.'
            )

        # Check extension
        allowed_exts = getattr(settings, 'ALLOWED_IMAGE_EXTENSIONS', ['jpg', 'jpeg', 'png', 'webp'])
        name = image.name.lower()
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        if ext not in allowed_exts:
            raise forms.ValidationError(
                f'Unsupported file format ".{ext}". '
                f'Allowed formats: {", ".join(allowed_exts).upper()}.'
            )

        return image

    def clean_color_count(self):
        raw = self.cleaned_data.get('color_count')
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise forms.ValidationError('Invalid color count.')

        allowed = {4, 8, 16, 32, 64, 128}
        if value not in allowed:
            raise forms.ValidationError(
                f'{value} is not a valid color count. '
                f'Choose from: {", ".join(str(c) for c in sorted(allowed))}.'
            )
        return value
