/* ============================================================
   Jigarzzz Video Suite — Frontend Logic
   Wires up tabs, forms, TTS controls, uploads, and the library.
   ============================================================ */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const LANG_LABELS = {
    'ur-PK': '🇵🇰 Urdu (Pakistan)',
    'ur-IN': '🕊️ Punjabi / Urdu (India) — Gul & Salman',
    'hi-IN': '🇮🇳 Hindi (India)',
    'pa-IN': '🌾 Punjabi (India) — Native',
    'en-US': '🇺🇸 English (US)',
    'en-GB': '🇬🇧 English (UK)',
    'en-AU': '🇦🇺 English (Australian)',
  };

  let VOICE_DATA = null; // { voices, voice_styles, mood_labels, age_presets }

  /* ---------------- Toast ---------------- */
  let toastTimer = null;
  function toast(msg, type = 'success') {
    const el = $('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast show ${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3800);
  }

  /* ---------------- Tabs ---------------- */
  function initTabs() {
    const buttons = qsa('.tab-btn');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('active'));
        qsa('.tab-content').forEach((c) => c.classList.remove('active'));
        btn.classList.add('active');
        $(btn.dataset.tab)?.classList.add('active');
      });
    });
  }

  /* ---------------- Generic toggle-btn groups (audio source / slicing mode) --- */
  function wireToggleGroup(pairs) {
    const buttons = pairs.map((p) => $(p.btnId)).filter(Boolean);
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        pairs.forEach((p) => $(p.panelId)?.classList.remove('active'));
        const match = pairs.find((p) => p.btnId === btn.id);
        if (match) $(match.panelId)?.classList.add('active');
      });
    });
  }

  function currentToggleType(pairs) {
    const active = pairs.find((p) => $(p.btnId)?.classList.contains('active'));
    return active ? $(active.btnId).dataset.type : pairs[0].value;
  }

  /* ---------------- Voice / Mood / Age panels ---------------- */
  function formatRate(v) { return (v >= 0 ? '+' : '') + v + '%'; }
  function formatPitch(v) { return (v >= 0 ? '+' : '') + v + 'Hz'; }
  function rateLabelText(v) { if (v <= -20) return 'Slow'; if (v >= 20) return 'Fast'; return 'Normal'; }
  function pitchLabelText(v) { if (v <= -50) return 'Low'; if (v >= 50) return 'High'; return 'Normal'; }

  function initVoicePanel(cfg) {
    const langSel = $(cfg.lang), voiceSel = $(cfg.voice);
    const moodGrid = $(cfg.moodGrid), moodTag = $(cfg.moodTag), ageGrid = $(cfg.ageGrid);
    const rateSlider = $(cfg.rateSlider), pitchSlider = $(cfg.pitchSlider);
    const rateVal = $(cfg.rateVal), pitchVal = $(cfg.pitchVal);
    const styleHidden = $(cfg.styleHidden), styleDegreeHidden = $(cfg.styleDegreeHidden);
    const rateHidden = $(cfg.rateHidden), pitchHidden = $(cfg.pitchHidden);
    if (!langSel || !voiceSel) return;

    // Populate language dropdown if empty (e.g. AI tab's <select> is blank in HTML)
    if (langSel.options.length === 0) {
      Object.keys(VOICE_DATA.voices).forEach((code) => {
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = LANG_LABELS[code] || code;
        if (code === 'ur-PK') opt.selected = true;
        langSel.appendChild(opt);
      });
    }

    function refreshVoices() {
      const lang = langSel.value;
      const voices = VOICE_DATA.voices[lang] || {};
      voiceSel.innerHTML = '';
      Object.entries(voices).forEach(([label, id]) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = label;
        voiceSel.appendChild(opt);
      });
      refreshMood();
    }

    function refreshMood() {
      const voiceId = voiceSel.value;
      const supported = (VOICE_DATA.voice_styles && VOICE_DATA.voice_styles[voiceId]) || [];
      const keys = ['', ...supported];
      moodGrid.innerHTML = '';
      keys.forEach((key) => {
        const chip = document.createElement('div');
        chip.className = 'mood-chip' + (key === '' ? ' active' : '');
        chip.textContent = VOICE_DATA.mood_labels[key] || key;
        chip.dataset.key = key;
        chip.addEventListener('click', () => {
          qsa('.mood-chip', moodGrid).forEach((c) => c.classList.remove('active'));
          chip.classList.add('active');
          if (styleHidden) styleHidden.value = key;
          if (styleDegreeHidden) styleDegreeHidden.value = '1.0';
        });
        moodGrid.appendChild(chip);
      });
      if (styleHidden) styleHidden.value = '';
      if (moodTag) {
        moodTag.textContent = supported.length
          ? `${supported.length} styles supported`
          : 'No extra styles for this voice';
      }
    }

    function wireSlider(slider, valEl, hiddenEl, fmt, labelFn) {
      if (!slider) return;
      slider.addEventListener('input', () => {
        const v = parseInt(slider.value, 10);
        if (valEl) valEl.textContent = labelFn(v);
        if (hiddenEl) hiddenEl.value = fmt(v);
      });
    }
    wireSlider(rateSlider, rateVal, rateHidden, formatRate, rateLabelText);
    wireSlider(pitchSlider, pitchVal, pitchHidden, formatPitch, pitchLabelText);

    function renderAgeGrid() {
      if (!ageGrid || !VOICE_DATA.age_presets) return;
      ageGrid.innerHTML = '';
      Object.entries(VOICE_DATA.age_presets).forEach(([key, preset]) => {
        const chip = document.createElement('div');
        chip.className = 'age-chip' + (key === 'adult' ? ' active' : '');
        chip.innerHTML = `${preset.label}<span class="age-desc">${preset.desc}</span>`;
        chip.addEventListener('click', () => {
          qsa('.age-chip', ageGrid).forEach((c) => c.classList.remove('active'));
          chip.classList.add('active');
          const rateNum = parseInt(preset.rate, 10);
          const pitchNum = parseInt(preset.pitch, 10);
          if (rateSlider) { rateSlider.value = rateNum; rateSlider.dispatchEvent(new Event('input')); }
          if (pitchSlider) { pitchSlider.value = pitchNum; pitchSlider.dispatchEvent(new Event('input')); }
        });
        ageGrid.appendChild(chip);
      });
    }
    renderAgeGrid();

    langSel.addEventListener('change', refreshVoices);
    voiceSel.addEventListener('change', refreshMood);
    refreshVoices();
  }

  function wirePreviewButton(btnId, cfg) {
    const btn = $(btnId);
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const voiceSel = $(cfg.voice), langSel = $(cfg.lang);
      const styleHidden = $(cfg.styleHidden), styleDegreeHidden = $(cfg.styleDegreeHidden);
      const rateHidden = $(cfg.rateHidden), pitchHidden = $(cfg.pitchHidden);
      const player = $(cfg.playerWrap), audio = $(cfg.audioEl);
      const original = btn.textContent;
      btn.textContent = '⏳ Loading…';
      btn.disabled = true;
      try {
        const fd = new FormData();
        fd.append('voice', voiceSel.value);
        fd.append('lang', langSel.value);
        fd.append('style', styleHidden ? styleHidden.value : '');
        fd.append('style_degree', styleDegreeHidden ? styleDegreeHidden.value : '1.0');
        fd.append('rate', rateHidden ? rateHidden.value : '+0%');
        fd.append('pitch', pitchHidden ? pitchHidden.value : '+0Hz');
        const res = await fetch('/api/preview-voice', { method: 'POST', body: fd });
        if (!res.ok) throw new Error('Preview generation failed');
        const blob = await res.blob();
        audio.src = URL.createObjectURL(blob);
        player.style.display = 'block';
        audio.play();
      } catch (err) {
        toast(err.message || 'Preview failed', 'error');
      } finally {
        btn.textContent = original;
        btn.disabled = false;
      }
    });
  }

  /* ---------------- Drag & drop video uploader (merge tab) ---------------- */
  let selectedVideoFiles = [];
  function initDropzone() {
    const zone = $('video-dropzone');
    const input = $('videos');
    const queue = $('video-queue');
    const pill = $('video-count-pill');
    if (!zone || !input) return;

    function renderQueue() {
      queue.innerHTML = '';
      selectedVideoFiles.forEach((file, idx) => {
        const item = document.createElement('div');
        item.className = 'queue-item';
        const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
        item.innerHTML = `<span>🎬 ${file.name} <small style="opacity:.55">(${sizeMb} MB)</small></span>`;
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'remove-btn';
        removeBtn.textContent = '✕';
        removeBtn.addEventListener('click', () => {
          selectedVideoFiles.splice(idx, 1);
          renderQueue();
        });
        item.appendChild(removeBtn);
        queue.appendChild(item);
      });
      if (pill) {
        pill.style.display = selectedVideoFiles.length ? 'inline-flex' : 'none';
        pill.textContent = `${selectedVideoFiles.length} file${selectedVideoFiles.length === 1 ? '' : 's'}`;
      }
    }

    input.addEventListener('change', () => {
      selectedVideoFiles = selectedVideoFiles.concat(Array.from(input.files || []));
      input.value = '';
      renderQueue();
    });

    ['dragover', 'dragenter'].forEach((evt) =>
      zone.addEventListener(evt, (e) => { e.preventDefault(); zone.classList.add('dragover'); })
    );
    ['dragleave', 'dragend'].forEach((evt) =>
      zone.addEventListener(evt, () => zone.classList.remove('dragover'))
    );
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const files = Array.from(e.dataTransfer.files || []).filter((f) => f.type.startsWith('video/'));
      selectedVideoFiles = selectedVideoFiles.concat(files);
      renderQueue();
    });
  }

  /* ---------------- Progress bar simulation ---------------- */
  function simulateProgress(prefix, steps) {
    const wrap = $(`${prefix}-progress`);
    const fill = $(`${prefix}-fill`);
    const pct = $(`${prefix}-pct`);
    const stepText = $(`${prefix}-step`);
    wrap?.classList.add('visible');
    let i = 0, value = 0;
    const timer = setInterval(() => {
      value = Math.min(value + Math.random() * 9 + 3, 90);
      if (fill) fill.style.width = `${value}%`;
      if (pct) pct.textContent = `${Math.round(value)}%`;
      if (stepText && steps.length) {
        stepText.textContent = steps[Math.min(i, steps.length - 1)];
        if (value > ((i + 1) / steps.length) * 90) i++;
      }
    }, 700);
    return {
      finish() {
        clearInterval(timer);
        if (fill) fill.style.width = '100%';
        if (pct) pct.textContent = '100%';
        if (stepText) stepText.textContent = 'Done!';
        setTimeout(() => wrap?.classList.remove('visible'), 1200);
      },
      fail() {
        clearInterval(timer);
        wrap?.classList.remove('visible');
      },
    };
  }

  function setSubmitting(btnId, submitting) {
    const btn = $(btnId);
    if (!btn) return;
    btn.disabled = submitting;
    btn.classList.toggle('loading', submitting);
  }

  /* ---------------- Form: Merge Videos ---------------- */
  function initMergeForm() {
    const form = $('merge-form');
    if (!form) return;
    const audioTogglePairs = [
      { btnId: 'audio-toggle-script', panelId: 'tts-panel' },
      { btnId: 'audio-toggle-upload', panelId: 'audio-upload-panel' },
      { btnId: 'audio-toggle-none', panelId: 'no-audio-panel' },
    ];
    wireToggleGroup(audioTogglePairs);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (selectedVideoFiles.length === 0) {
        toast('Please add at least one video clip.', 'error');
        return;
      }
      const fd = new FormData(form);
      fd.delete('videos');
      selectedVideoFiles.forEach((f) => fd.append('videos', f));
      fd.set('audio_source', currentToggleType(audioTogglePairs));
      fd.set('language', $('tts-language')?.value || 'ur-PK'); // no name attr on this select

      setSubmitting('merge-submit-btn', true);
      const progress = simulateProgress('merge', ['Merging clips…', 'Generating audio…', 'Mixing tracks…', 'Finalising…']);
      try {
        const res = await fetch('/api/merge', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Merge failed');
        progress.finish();
        toast('✅ Video merged successfully!');
        selectedVideoFiles = [];
        $('video-queue').innerHTML = '';
        $('video-count-pill').style.display = 'none';
        loadLibrary();
      } catch (err) {
        progress.fail();
        toast(err.message || 'Merge failed', 'error');
      } finally {
        setSubmitting('merge-submit-btn', false);
      }
    });
  }

  /* ---------------- Form: YouTube Clipper ---------------- */
  function initClipForm() {
    const form = $('clip-form');
    if (!form) return;
    const slicingPairs = [
      { btnId: 'clip-toggle-auto', panelId: 'auto-clip-panel' },
      { btnId: 'clip-toggle-ts', panelId: 'timestamps-clip-panel' },
    ];
    wireToggleGroup(slicingPairs);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      fd.set('mode', currentToggleType(slicingPairs)); // no field named "mode" in the HTML

      setSubmitting('clip-submit-btn', true);
      const progress = simulateProgress('clip', ['Downloading video…', 'Slicing clips…', 'Applying safety filters…', 'Finalising…']);
      try {
        const res = await fetch('/api/clip', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Clipping failed');
        progress.finish();
        toast(data.message || '✅ Clips created!');
        loadLibrary();
      } catch (err) {
        progress.fail();
        toast(err.message || 'Clipping failed', 'error');
      } finally {
        setSubmitting('clip-submit-btn', false);
      }
    });
  }

  /* ---------------- Form: AI Video Creator ---------------- */
  function initAiForm() {
    const form = $('ai-video-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      setSubmitting('ai-submit-btn', true);
      const progress = simulateProgress('ai', ['Writing scene plan…', 'Generating voiceover…', 'Fetching visuals…', 'Rendering video…']);
      try {
        const res = await fetch('/api/generate-video', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'Generation failed');
        progress.finish();
        toast('✅ AI video generated!');
        loadLibrary();
      } catch (err) {
        progress.fail();
        toast(err.message || 'Generation failed', 'error');
      } finally {
        setSubmitting('ai-submit-btn', false);
      }
    });
  }

  /* ---------------- Media Library ---------------- */
  let libraryCache = [];

  function openModal(filename) {
    $('modal-title').textContent = `▶ ${filename}`;
    $('modal-player').src = `/api/outputs/${encodeURIComponent(filename)}`;
    $('video-modal').classList.add('active');
  }
  function closeModal() {
    $('video-modal').classList.remove('active');
    const player = $('modal-player');
    player.pause();
    player.src = '';
  }

  function renderLibrary(list) {
    const container = $('gallery-container');
    if (!container) return;
    if (list.length === 0) {
      container.innerHTML = `<div class="empty-library">
          <div class="library-empty-art">🎞️</div>
          <span>No files exported yet.<br>Run a merge or clipping operation to begin.</span>
        </div>`;
      return;
    }
    container.innerHTML = '';
    list.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'library-item';
      el.innerHTML = `
        <div class="library-item-info">
          <span class="library-item-name" title="${item.filename}">${item.filename}</span>
          <span class="library-item-meta">${item.size} · ${item.duration}</span>
        </div>
        <div class="library-item-actions">
          <button type="button" class="play-btn" title="Play">▶</button>
          <a href="/api/outputs/${encodeURIComponent(item.filename)}" download title="Download">⬇</a>
        </div>`;
      el.querySelector('.play-btn').addEventListener('click', () => openModal(item.filename));
      container.appendChild(el);
    });
  }

  function updateStats(list) {
    const clips = list.filter((f) => f.filename.startsWith('clip_')).length;
    const withAudio = list.filter((f) => f.filename.startsWith('merged_') || f.filename.startsWith('ai_video_')).length;
    if ($('stat-files')) $('stat-files').textContent = list.length;
    if ($('stat-clips')) $('stat-clips').textContent = clips;
    if ($('stat-audio')) $('stat-audio').textContent = withAudio;
  }

  async function loadLibrary() {
    try {
      const res = await fetch('/api/outputs');
      libraryCache = await res.json();
      renderLibrary(libraryCache);
      updateStats(libraryCache);
    } catch (err) {
      console.error('Failed to load library', err);
    }
  }

  function initLibrary() {
    $('refresh-gallery')?.addEventListener('click', loadLibrary);
    $('clear-library-btn')?.addEventListener('click', async () => {
      if (!confirm('Delete all exported files? This cannot be undone.')) return;
      try {
        const res = await fetch('/api/clear-library', { method: 'POST' });
        const data = await res.json();
        toast(`🗑 Deleted ${data.deleted} file(s)`);
        loadLibrary();
      } catch (err) {
        toast('Failed to clear library', 'error');
      }
    });
    $('library-search')?.addEventListener('input', (e) => {
      const q = e.target.value.trim().toLowerCase();
      const filtered = q ? libraryCache.filter((f) => f.filename.toLowerCase().includes(q)) : libraryCache;
      renderLibrary(filtered);
    });
    $('modal-close')?.addEventListener('click', closeModal);
    $('modal-close-btn')?.addEventListener('click', closeModal);
  }

  /* ---------------- Boot ---------------- */
  async function boot() {
    initTabs();
    initDropzone();
    initMergeForm();
    initClipForm();
    initAiForm();
    initLibrary();

    try {
      const res = await fetch('/api/voices');
      VOICE_DATA = await res.json();
      initVoicePanel({
        lang: 'tts-language', voice: 'tts-voice', moodGrid: 'tts-mood-grid', moodTag: 'tts-mood-support-tag',
        ageGrid: 'tts-age-grid', rateSlider: 'tts-rate-slider', pitchSlider: 'tts-pitch-slider',
        rateVal: 'tts-rate-val', pitchVal: 'tts-pitch-val', styleHidden: 'tts-style',
        styleDegreeHidden: 'tts-style-degree', rateHidden: 'tts-rate', pitchHidden: 'tts-pitch',
      });
      initVoicePanel({
        lang: 'ai-language', voice: 'ai-voice', moodGrid: 'ai-mood-grid', moodTag: 'ai-mood-support-tag',
        ageGrid: 'ai-age-grid', rateSlider: 'ai-rate-slider', pitchSlider: 'ai-pitch-slider',
        rateVal: 'ai-rate-val', pitchVal: 'ai-pitch-val', styleHidden: 'ai-tts-style',
        styleDegreeHidden: 'ai-tts-style-degree', rateHidden: 'ai-tts-rate', pitchHidden: 'ai-tts-pitch',
      });
      wirePreviewButton('preview-voice-btn', {
        lang: 'tts-language', voice: 'tts-voice', styleHidden: 'tts-style', styleDegreeHidden: 'tts-style-degree',
        rateHidden: 'tts-rate', pitchHidden: 'tts-pitch', playerWrap: 'voice-preview-player', audioEl: 'preview-audio',
      });
      wirePreviewButton('ai-preview-voice-btn', {
        lang: 'ai-language', voice: 'ai-voice', styleHidden: 'ai-tts-style', styleDegreeHidden: 'ai-tts-style-degree',
        rateHidden: 'ai-tts-rate', pitchHidden: 'ai-tts-pitch', playerWrap: 'ai-voice-preview-player', audioEl: 'ai-preview-audio',
      });
    } catch (err) {
      console.error('Failed to load voice catalog', err);
      toast('Could not load voice list from server', 'error');
    }

    loadLibrary();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
