"""
Image processing module for PixelForge.

This module implements traditional image-processing algorithms for converting
photographs into pixel art. All processing is performed deterministically using
the Pillow library — no machine learning or external AI APIs are used.

Algorithms implemented:
  1. Pixelation  — downsample then upscale with nearest-neighbour interpolation
  2. Color Quantization — reduce the palette using Pillow's median-cut quantizer
  3. Combined Pixel Art — pixelation followed by colour quantization
"""

import io
from PIL import Image


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_rgb(image: Image.Image) -> Image.Image:
    """Convert any image mode to RGB, correctly handling transparency."""
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (0, 0, 0))
        background.paste(image, mask=image.split()[3])
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image


def _validate_pixel_size(pixel_size: int) -> int:
    """Clamp pixel_size to a safe, meaningful range [2, 64]."""
    return max(2, min(64, int(pixel_size)))


def _validate_color_count(color_count: int) -> int:
    """Ensure color_count is one of the allowed discrete values."""
    allowed = {4, 8, 16, 32, 64, 128}
    if color_count not in allowed:
        # Round to nearest allowed value
        color_count = min(allowed, key=lambda x: abs(x - color_count))
    return color_count


# ---------------------------------------------------------------------------
# Public processing functions
# ---------------------------------------------------------------------------

def pixelate(image: Image.Image, pixel_size: int) -> Image.Image:
    """
    Apply pixelation to an image.

    Algorithm
    ---------
    1. Convert the image to RGB.
    2. Record the original dimensions W × H.
    3. Compute the small resolution:
         small_w = max(1, W // pixel_size)
         small_h = max(1, H // pixel_size)
    4. Downsample to (small_w, small_h) using LANCZOS (high-quality
       antialiasing) to avoid aliasing artifacts in the small version.
    5. Upscale back to (W, H) using NEAREST interpolation so that each
       logical pixel becomes a solid square block of size ≈ pixel_size × pixel_size.

    The relationship between the original dimensions and the number of visible
    pixel blocks is:
        blocks_x = W // pixel_size
        blocks_y = H // pixel_size

    Parameters
    ----------
    image      : PIL Image — the source image
    pixel_size : int — edge length of each square pixel block (2–64)

    Returns
    -------
    PIL Image in RGB mode.
    """
    pixel_size = _validate_pixel_size(pixel_size)
    image = _to_rgb(image)

    original_size = image.size  # (width, height)
    small_w = max(1, original_size[0] // pixel_size)
    small_h = max(1, original_size[1] // pixel_size)

    # Step 1 — downsample (antialiased)
    small = image.resize((small_w, small_h), resample=Image.Resampling.LANCZOS)

    # Step 2 — upscale with nearest-neighbour to preserve hard pixel edges
    pixelated = small.resize(original_size, resample=Image.Resampling.NEAREST)

    return pixelated


def quantize_colors(image: Image.Image, color_count: int) -> Image.Image:
    """
    Reduce the number of distinct colors in an image (color quantization).

    Algorithm
    ---------
    Pillow's Image.quantize() implements a median-cut algorithm to partition
    the color space into `color_count` clusters and maps each pixel to the
    nearest cluster centroid.  The palette image is then converted back to
    RGB so downstream processing treats it as a normal image.

    The effect is a flat, poster-like appearance where only `color_count`
    unique colors appear in the output — characteristic of retro pixel art.

    Parameters
    ----------
    image       : PIL Image — the source image
    color_count : int — maximum number of colors in the output palette

    Returns
    -------
    PIL Image in RGB mode.
    """
    color_count = _validate_color_count(color_count)
    image = _to_rgb(image)

    # quantize() requires the image to have no alpha channel (already handled)
    quantized = image.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    return quantized.convert('RGB')


def convert_to_pixel_art(image: Image.Image, pixel_size: int, color_count: int) -> Image.Image:
    """
    Full pixel-art conversion: pixelation + color quantization.

    Processing sequence
    -------------------
    1. Normalize the image to RGB (handle RGBA, L, P, etc.).
    2. Downsample to a small resolution with LANCZOS antialiasing.
    3. Apply color quantization on the small image to limit the palette.
    4. Upscale back to the original dimensions with NEAREST interpolation.

    Performing quantization on the downsampled image (step 3) is more
    effective than quantizing the full-size image because the smaller image
    already contains only the colors that will actually appear in the final
    output, leading to more faithful palette selection.

    Parameters
    ----------
    image       : PIL Image — the source image
    pixel_size  : int — edge length of each square pixel block (2–64)
    color_count : int — maximum number of colors in the output palette

    Returns
    -------
    PIL Image in RGB mode.
    """
    pixel_size = _validate_pixel_size(pixel_size)
    color_count = _validate_color_count(color_count)
    image = _to_rgb(image)

    original_size = image.size
    small_w = max(1, original_size[0] // pixel_size)
    small_h = max(1, original_size[1] // pixel_size)

    # Step 1 — downsample
    small = image.resize((small_w, small_h), resample=Image.Resampling.LANCZOS)

    # Step 2 — quantize on the small image
    quantized_small = small.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    quantized_small = quantized_small.convert('RGB')

    # Step 3 — upscale with nearest-neighbour
    result = quantized_small.resize(original_size, resample=Image.Resampling.NEAREST)

    return result


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def image_to_bytes(image: Image.Image, fmt: str = 'PNG') -> bytes:
    """
    Serialise a PIL Image to a bytes object.

    Parameters
    ----------
    image : PIL Image
    fmt   : str — Pillow format string, default 'PNG'

    Returns
    -------
    bytes — raw image data
    """
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, optimize=False)
    buffer.seek(0)
    return buffer.read()


def load_image_from_bytes(data: bytes) -> Image.Image:
    """
    Load a PIL Image from a bytes object.

    Parameters
    ----------
    data : bytes — raw image data

    Returns
    -------
    PIL Image
    """
    return Image.open(io.BytesIO(data))


def get_image_info(image: Image.Image) -> dict:
    """
    Return a dictionary with basic metadata about a PIL Image.

    Returns
    -------
    dict with keys: width, height, mode, format
    """
    return {
        'width': image.width,
        'height': image.height,
        'mode': image.mode,
        'format': getattr(image, 'format', 'Unknown') or 'Unknown',
    }
