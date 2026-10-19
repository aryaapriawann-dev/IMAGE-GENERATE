/**
 * PixelForge — Frontend Application JS
 *
 * Responsibilities:
 *  - Drag-and-drop image upload
 *  - Local image preview thumbnail
 *  - Dynamic slider value display
 *  - Color palette button group
 *  - AJAX form submission to /convert/
 *  - Rendering side-by-side original / result previews
 *  - Error display
 *  - Reset / clear state
 *  - Mode hint text
 *
 * The authoritative conversion always happens on the Django backend.
 * JS only handles UI interactions and XHR.
 */

/* ---- Wait for DOM ---------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {

  /* ---- Element references -------------------------------- */
  const form         = document.getElementById('convert-form');
  const fileInput    = document.getElementById('image-input');
  const dropZone     = document.getElementById('drop-zone');
  const previewWrap  = document.getElementById('preview-wrap');
  const previewThumb = document.getElementById('original-preview-thumb');
  const previewName  = document.getElementById('preview-filename');

  const pixelSlider  = document.getElementById('pixel_size');
  const pixelDisplay = document.getElementById('pixel-size-display');
  const colorInput   = document.getElementById('color_count');
  const colorBtns    = document.querySelectorAll('.pf-color-btn');

  const modeSelect   = document.getElementById('conversion_mode');
  const modeHint     = document.getElementById('mode-hint-text');
  const pixelField   = document.getElementById('pixel-size-field');
  const colorField   = document.getElementById('color-count-field');

  const convertBtn   = document.getElementById('convert-btn');
  const convertText  = document.getElementById('convert-btn-text');
  const resetBtn     = document.getElementById('reset-btn');
  const errorBanner  = document.getElementById('error-banner');

  // Preview panes
  const previewIdle    = document.getElementById('preview-idle');
  const previewLoading = document.getElementById('preview-loading');
  const previewResult  = document.getElementById('preview-result');

  const compareOriginal = document.getElementById('compare-original');
  const compareResult   = document.getElementById('compare-result');
  const originalMeta    = document.getElementById('original-meta');
  const resultMeta      = document.getElementById('result-meta');
  const resultModeLabel = document.getElementById('result-mode-label');

  const statPixelSize   = document.getElementById('stat-pixel-size');
  const statColorCount  = document.getElementById('stat-color-count');
  const statDimensions  = document.getElementById('stat-dimensions');

  /* ---- State -------------------------------------------- */
  let hasFile = false;

  /* ===================================================
     MODE HINTS
     =================================================== */
  const MODE_HINTS = {
    'pixel_art': 'Applies pixelation then reduces the colour palette — produces authentic pixel art.',
    'pixelate':  'Enlarges pixel blocks only. Colour remains unreduced.',
    'quantize':  'Reduces the number of distinct colours only. No pixelation applied.',
  };

  function updateModeHint() {
    const mode = modeSelect.value;
    modeHint.textContent = MODE_HINTS[mode] || '';

    // Show / hide relevant controls based on mode
    const showPixel = (mode === 'pixel_art' || mode === 'pixelate');
    const showColor = (mode === 'pixel_art' || mode === 'quantize');
    pixelField.style.display = showPixel ? '' : 'none';
    colorField.style.display = showColor ? '' : 'none';
  }

  modeSelect.addEventListener('change', updateModeHint);
  updateModeHint(); // initialise on load

  /* ===================================================
     PIXEL SLIDER
     =================================================== */
  function updateSliderDisplay() {
    const val = parseInt(pixelSlider.value, 10);
    pixelDisplay.textContent = `${val} px`;
    pixelSlider.setAttribute('aria-valuenow', val);

    // Update CSS custom property for gradient fill
    const min = parseInt(pixelSlider.min, 10);
    const max = parseInt(pixelSlider.max, 10);
    const pct = ((val - min) / (max - min)) * 100;
    pixelSlider.style.setProperty('--slider-pct', pct);
    // Inline background for cross-browser
    pixelSlider.style.background = `linear-gradient(to right,
      var(--accent) 0%, var(--accent) ${pct}%,
      var(--border) ${pct}%, var(--border) 100%)`;
  }

  pixelSlider.addEventListener('input', updateSliderDisplay);
  updateSliderDisplay(); // initialise

  /* ===================================================
     COLOR PALETTE BUTTONS
     =================================================== */
  colorBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      colorBtns.forEach(b => {
        b.classList.remove('pf-color-btn--active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('pf-color-btn--active');
      btn.setAttribute('aria-pressed', 'true');
      colorInput.value = btn.dataset.value;
    });
  });

  /* ===================================================
     FILE SELECTION & DRAG-AND-DROP
     =================================================== */
  // Click on drop zone opens file picker
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) {
      handleFile(fileInput.files[0]);
    }
  });

  // Drag events
  ;['dragenter', 'dragover'].forEach(evt => {
    dropZone.addEventListener(evt, e => {
      e.preventDefault();
      dropZone.classList.add('pf-dropzone--active');
    });
  });
  ;['dragleave', 'dragend', 'drop'].forEach(evt => {
    dropZone.addEventListener(evt, () => dropZone.classList.remove('pf-dropzone--active'));
  });

  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      // Inject into the file input so the form picks it up
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      handleFile(file);
    }
  });

  function handleFile(file) {
    // Client-side quick validation (backend always re-validates)
    const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];
    const MAX_MB  = 10;

    if (!ALLOWED.includes(file.type)) {
      showError(`Unsupported format: ${file.type}. Please use JPG, PNG, or WEBP.`);
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      showError(`File too large (${(file.size / 1048576).toFixed(1)} MB). Maximum is ${MAX_MB} MB.`);
      return;
    }

    hideError();

    // Show thumbnail preview in drop zone
    const reader = new FileReader();
    reader.onload = evt => {
      previewThumb.src = evt.target.result;
      previewName.textContent = file.name;
      previewWrap.hidden = false;
      dropZone.classList.add('pf-dropzone--has-file');
    };
    reader.readAsDataURL(file);

    hasFile = true;
    convertBtn.disabled = false;
  }

  /* ===================================================
     FORM SUBMISSION (AJAX)
     =================================================== */
  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!hasFile) {
      showError('Please select an image first.');
      return;
    }

    // Show loading state
    setPreviewState('loading');
    convertBtn.disabled = true;
    convertText.textContent = 'Converting…';
    hideError();

    try {
      const formData = new FormData(form);

      const response = await fetch(window.PIXELFORGE.convertUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.PIXELFORGE.csrfToken },
        body: formData,
      });

      const data = await response.json();

      if (!data.success) {
        const messages = Object.values(data.errors || {}).flat().join(' ');
        showError(messages || 'Conversion failed. Please try again.');
        setPreviewState('idle');
        return;
      }

      // Render results
      renderResult(data);
      setPreviewState('result');

    } catch (err) {
      console.error('Conversion request failed:', err);
      showError('Network error. Please check your connection and try again.');
      setPreviewState('idle');
    } finally {
      convertBtn.disabled = false;
      convertText.textContent = 'Convert to Pixel Art';
    }
  });

  /* ===================================================
     RENDER RESULT
     =================================================== */
  function renderResult(data) {
    const origSrc   = 'data:image/png;base64,' + data.original_b64;
    const resultSrc = 'data:image/png;base64,' + data.result_b64;

    compareOriginal.src = origSrc;
    compareResult.src   = resultSrc;

    const oi = data.original_info;
    const ri = data.result_info;

    originalMeta.textContent = `${oi.width} × ${oi.height} px · ${oi.mode}`;
    resultMeta.textContent   = `${ri.width} × ${ri.height} px · PNG`;

    resultModeLabel.textContent = data.mode_label;

    statPixelSize.textContent  = `${data.pixel_size} px block`;
    statColorCount.textContent = `${data.color_count} colors`;
    statDimensions.textContent = `${ri.width} × ${ri.height}`;
  }

  /* ===================================================
     PREVIEW STATE MACHINE
     =================================================== */
  function setPreviewState(state) {
    previewIdle.hidden    = (state !== 'idle');
    previewLoading.hidden = (state !== 'loading');
    previewResult.hidden  = (state !== 'result');
  }

  /* ===================================================
     ERROR / RESET
     =================================================== */
  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.hidden = false;
  }
  function hideError() {
    errorBanner.hidden = true;
    errorBanner.textContent = '';
  }

  resetBtn.addEventListener('click', () => {
    form.reset();
    fileInput.value = '';
    previewWrap.hidden = true;
    previewThumb.src = '';
    previewName.textContent = '';
    dropZone.classList.remove('pf-dropzone--has-file', 'pf-dropzone--active');
    hasFile = false;
    convertBtn.disabled = true;
    convertText.textContent = 'Convert to Pixel Art';
    hideError();
    setPreviewState('idle');
    updateSliderDisplay();
    updateModeHint();
    // Reset color buttons to default (16)
    colorBtns.forEach(btn => {
      const active = btn.dataset.value === '16';
      btn.classList.toggle('pf-color-btn--active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    colorInput.value = '16';
    pixelSlider.value = 8;
    updateSliderDisplay();
  });

});
