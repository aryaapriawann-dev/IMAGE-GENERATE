"""
Quick functional test of the live PixelForge server.
Run with: .\venv\Scripts\python.exe test_live.py
"""
import io
import base64
import json
import urllib.request
import http.cookiejar
from PIL import Image

# ---- Create a test PNG image in memory ----
img = Image.new('RGB', (80, 80), (120, 80, 200))
for x in range(0, 80, 10):
    for y in range(0, 80, 10):
        img.putpixel((x, y), (255 - x, y * 2 % 255, (x + y) % 255))
buf = io.BytesIO()
img.save(buf, 'PNG')
img_bytes = buf.getvalue()

# ---- Get CSRF token from session ----
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

r = opener.open('http://127.0.0.1:8000/')
assert r.status == 200, f"Index returned {r.status}"
html = r.read().decode()
assert 'PixelForge' in html, "Branding not found"
print("[OK] Index page loads — PixelForge branding present")

csrf = None
for c in jar:
    if c.name == 'csrftoken':
        csrf = c.value
        break
assert csrf, "No CSRF token in cookies"
print(f"[OK] CSRF token obtained: {csrf[:10]}...")

# ---- Build multipart POST ----
boundary = 'PF_TEST_BOUNDARY_12345'

def part_text(name, value):
    return (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{name}"\r\n'
        f'\r\n'
        f'{value}\r\n'
    ).encode()

def part_file(name, filename, content_type, data):
    header = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n'
        f'\r\n'
    ).encode()
    return header + data + b'\r\n'

body = (
    part_text('csrfmiddlewaretoken', csrf)
    + part_text('pixel_size', '8')
    + part_text('color_count', '16')
    + part_text('conversion_mode', 'pixel_art')
    + part_file('image', 'test.png', 'image/png', img_bytes)
    + f'--{boundary}--\r\n'.encode()
)

req = urllib.request.Request(
    'http://127.0.0.1:8000/convert/',
    data=body,
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'X-CSRFToken': csrf,
        'Referer': 'http://127.0.0.1:8000/',
    },
    method='POST',
)

r2 = opener.open(req)
assert r2.status == 200, f"Convert returned {r2.status}"
data = json.loads(r2.read().decode())

assert data['success'], f"Conversion failed: {data}"
print("[OK] Conversion successful")

result_bytes = base64.b64decode(data['result_b64'])
assert result_bytes[:4] == b'\x89PNG', "Result is not a valid PNG"
print("[OK] Result is valid PNG")

ri = data['result_info']
assert ri['width'] == 80 and ri['height'] == 80, f"Wrong dimensions: {ri}"
print(f"[OK] Dimensions preserved: {ri['width']}x{ri['height']}")

print(f"[OK] Mode label: {data['mode_label']}")
print(f"[OK] Pixel size: {data['pixel_size']}, Color count: {data['color_count']}")

# ---- Test download endpoint ----
r3 = opener.open('http://127.0.0.1:8000/download/')
assert r3.status == 200, f"Download returned {r3.status}"
assert r3.headers.get('Content-Type') == 'image/png', f"Wrong content-type: {r3.headers.get('Content-Type')}"
dl_bytes = r3.read()
assert dl_bytes[:4] == b'\x89PNG', "Download is not a valid PNG"
print(f"[OK] Download works — Content-Type: image/png, Size: {len(dl_bytes)} bytes")

print("\n=== All live tests passed! ===")
