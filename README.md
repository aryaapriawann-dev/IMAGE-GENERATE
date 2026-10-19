# PixelForge — Image to Pixel Art Converter

**A Digital Image Processing university project** that converts photographs into retro pixel art using classical image-processing algorithms implemented in Python and Django.

---

## Project Overview

PixelForge is a fully local web application that accepts JPG, PNG, or WEBP images and converts them into pixel art using two fundamental image-processing techniques:

1. **Pixelation** — nearest-neighbour upscaling after downsampling
2. **Colour Quantization** — median-cut palette reduction via Pillow

No machine learning, deep learning, external AI APIs, or datasets are used. All processing is deterministic and runs locally on your machine.

---

## Project Objectives

- Demonstrate practical application of classical digital image-processing algorithms
- Implement pixelation using bilinear downsampling and nearest-neighbour upscaling
- Implement colour reduction using the median-cut quantization algorithm
- Provide an interactive web interface for exploring the effect of algorithm parameters
- Produce downloadable PNG output with no quality degradation

---

## Technologies Used

| Component         | Technology                          |
|-------------------|-------------------------------------|
| Language          | Python 3.12                         |
| Web framework     | Django 5.x                          |
| Image processing  | Pillow (PIL) 10+                    |
| Frontend          | HTML5, Vanilla CSS3, Vanilla JS     |
| Layout            | Bootstrap Icons (icon font only)    |
| Fonts             | Google Fonts — Inter, JetBrains Mono|
| Database          | SQLite (Django internals only)      |

---

## Explanation of Processing Algorithms

### A. Pixelation

Pixelation simulates the appearance of low-resolution images displayed at a larger size.

**Steps:**
1. Given an original image of size W × H and a pixel block size *s*:
2. Compute the reduced resolution: `W_small = ⌊W/s⌋`, `H_small = ⌊H/s⌋`
3. Downsample the image to `(W_small, H_small)` using **LANCZOS** (high-quality antialiasing)
4. Upscale back to `(W, H)` using **nearest-neighbour interpolation**

Nearest-neighbour assigns each destination pixel the value of the nearest source pixel without interpolation, creating hard-edged square blocks that are the visual signature of pixel art.

**Effect of pixel size *s*:**
- Small *s* (e.g., 2–4): Subtle pixelation, many fine blocks
- Large *s* (e.g., 32–64): Strong pixelation, few coarse blocks

### B. Colour Quantization

Colour quantization reduces the number of distinct colours in an image from potentially millions to a small fixed palette of *k* colours.

**Algorithm (Median Cut):**
1. Find the colour channel (R, G, or B) with the greatest range among all pixels
2. Sort all pixels by that channel's value
3. Split the pixel set at the median point into two equal halves
4. Recurse on each half until *k* groups are formed
5. Compute a representative colour for each group (typically the mean)
6. Replace every pixel's colour with its group's representative

**Effect of *k*:**
- Small *k* (e.g., 4–8): Highly stylised, poster-like appearance
- Large *k* (e.g., 64–128): Subtle quantization, near-photographic quality

### C. Combined Pixel Art Conversion

The primary conversion mode chains both algorithms:

1. Normalise → Convert to RGB (handles RGBA, grayscale)
2. Downsample to `(W_small, H_small)` with LANCZOS
3. Apply median-cut quantization with *k* colours **on the small image**
4. Upscale to `(W, H)` with nearest-neighbour

Quantizing at the small resolution is intentional: the downsampled image already contains only the colours that will appear in the final pixel blocks, so the *k*-colour palette faithfully represents the output without wasting colours on full-resolution detail that will be averaged away.

---

## Project Structure

```
CONVERT TO ANIMASI/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
├── pixelforge/
│   ├── __init__.py
│   ├── settings.py        — Django settings (MAX_UPLOAD_SIZE_MB, allowed extensions)
│   ├── urls.py            — Root URL routing
│   ├── asgi.py
│   └── wsgi.py
├── converter/
│   ├── __init__.py
│   ├── apps.py            — AppConfig
│   ├── urls.py            — /  /convert/  /download/
│   ├── forms.py           — ImageUploadForm with server-side validation
│   ├── views.py           — index, convert_image (JSON API), download_image
│   ├── image_processor.py — pixelate(), quantize_colors(), convert_to_pixel_art()
│   └── tests.py           — Unit + integration tests (38 test cases)
├── templates/
│   └── converter/
│       ├── base.html      — Nav, footer, static links
│       └── index.html     — Full single-page tool UI
└── static/
    ├── css/
    │   └── style.css      — Dark charcoal theme, responsive layout
    └── js/
        └── app.js         — Drag-drop upload, AJAX, result rendering
```

---

## Prerequisites

- Python 3.10 or later (tested with Python 3.12)
- pip (bundled with Python)
- Internet access for initial Google Fonts load (optional — fonts degrade gracefully)

---

## Installation (Windows PowerShell)

### 1. Navigate to the project directory

```powershell
cd "d:\CONVERT TO ANIMASI"
```

### 2. Create and activate a virtual environment (recommended)

```powershell
# Create
.\venv\Scripts\python.exe -m venv venv   # if venv doesn't exist yet

# Activate
.\venv\Scripts\Activate.ps1
```

> If PowerShell blocks script execution, run:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Apply Django migrations (creates db.sqlite3 for Django internals)

```powershell
python manage.py migrate
```

---

## Starting the Development Server

```powershell
python manage.py runserver
```

Open your browser at: **http://127.0.0.1:8000/**

---

## How to Use the Application

1. **Upload** — Drag an image onto the upload zone or click "Drop image here" to browse. JPG, PNG, and WEBP up to 10 MB are supported.
2. **Select mode** — Choose from:
   - *Pixel Art* — full conversion (pixelation + colour reduction)
   - *Pixelation Only* — block pixelation without colour reduction
   - *Color Reduction Only* — palette reduction without pixelation
3. **Adjust settings:**
   - *Pixelation Strength* — drag the slider (2 px to 64 px block size)
   - *Color Palette* — click a button (4 to 128 colours)
4. **Convert** — Click "Convert to Pixel Art". The result appears alongside the original.
5. **Download** — Click "Download PNG" to save the pixel-art image.

---

## Testing

### Run system checks

```powershell
python manage.py check
```

### Run the full test suite

```powershell
python manage.py test converter
```

### Verbose output

```powershell
python manage.py test converter --verbosity=2
```

The test suite covers 38 test cases including:
- Successful conversions for all three modes
- Aspect-ratio preservation
- Color palette limits
- Invalid uploads (unsupported extension, non-image data, oversized files)
- Invalid parameters (pixel_size out of range, invalid color_count)
- PNG output validation (magic bytes)
- Download response content-type and filename
- Different settings producing different outputs

---

## Known Limitations

- **Session storage** — The converted image is held in the Django session (server-side). If the server restarts between conversion and download, the download will return 404.
- **Large images** — Very large input images (> 4000 × 4000 px) may take 1–3 seconds to process depending on hardware.
- **WEBP on Windows** — Pillow requires libwebp. The pre-built Pillow wheels for Windows include it, so this should work out of the box.
- **Animations / GIFs** — Not supported; only the first frame would be processed.
- **No persistent history** — Conversion results are not saved to disk. Each session is independent.

---

## Academic Explanation (Project Report)

### Digital Image Processing Techniques Used

**PixelForge** applies two classical, deterministic image-processing algorithms described in standard textbooks (Gonzalez & Woods, *Digital Image Processing*, 4th ed.):

**Spatial Domain Processing — Nearest-Neighbour Interpolation:**
Nearest-neighbour interpolation is the simplest geometric transformation. When enlarging an image by factor *s*, the colour of output pixel *(x, y)* is taken directly from input pixel `(⌊x/s⌋, ⌊y/s⌋)` without any blending. This zero-order hold produces the hard, blocky edges characteristic of pixel art.

**Colour Space Processing — Median-Cut Quantization:**
The median-cut algorithm (Heckbert, 1982) partitions the three-dimensional RGB colour space into *k* axis-aligned boxes by recursively bisecting along the axis with the greatest range. It is a variance-minimising strategy that minimises the maximum quantization error within each partition. The output palette is the set of *k* representative colours (box means or medians).

Both algorithms are entirely deterministic given fixed inputs. There are no random seeds, no learned parameters, and no external API calls. The application is a self-contained implementation of foundational DIP concepts.

---

*PixelForge — Digital Image Processing Project | Python 3.12 · Django 5 · Pillow*
