import asyncio
import os
import subprocess
import tempfile
import urllib.request
import urllib.parse
import uuid
import re
import numpy as np
import PIL.Image
from PIL import ImageDraw, ImageFont

if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

import edge_tts
from moviepy.editor import AudioFileClip, CompositeAudioClip

# ─────────────────────────────────────────────────────────────────
# VOICE CATALOG  (use ⭐ to highlight top-quality picks)
# ─────────────────────────────────────────────────────────────────
VOICES = {
    "ur-PK": {
        "⭐ Uzma – Natural Female":  "ur-PK-UzmaNeural",
        "⭐ Asad – Natural Male":    "ur-PK-AsadNeural",
    },
    "ur-IN": {
        "⭐ Gul – Warm Female":     "ur-IN-GulNeural",
        "⭐ Salman – Deep Male":   "ur-IN-SalmanNeural",
    },
    "hi-IN": {
        "⭐ Swara – Natural Female": "hi-IN-SwaraNeural",
        "⭐ Madhur – Rich Male":     "hi-IN-MadhurNeural",
    },
    "pa-IN": {
        "⭐ Gurpreet – Native Female": "gtts-pa-female",
        "⭐ Harpreet – Native Male":   "gtts-pa-male",
    },
    "en-US": {
        "⭐ Emma – Ultra Natural (F)":   "en-US-EmmaMultilingualNeural",
        "⭐ Andrew – Ultra Natural (M)": "en-US-AndrewMultilingualNeural",
        "⭐ Aria – Expressive (F)":      "en-US-AriaNeural",
        "⭐ Brian – Warm (M)":           "en-US-BrianMultilingualNeural",
        "⭐ Ava – Crystal Clear (F)":    "en-US-AvaMultilingualNeural",
        "Jenny – Friendly (F)":         "en-US-JennyNeural",
        "Guy – Confident (M)":          "en-US-GuyNeural",
        "Sara – Calm (F)":              "en-US-SaraNeural",
        "Tony – Bold (M)":              "en-US-TonyNeural",
        "Nancy – Bright (F)":           "en-US-NancyNeural",
        "Davis – Deep (M)":             "en-US-DavisNeural",
        "Steffan – Rich (M)":           "en-US-SteffanNeural",
    },
    "en-GB": {
        "⭐ Sonia – British (F)":  "en-GB-SoniaNeural",
        "Ryan – British (M)":     "en-GB-RyanNeural",
        "Libby – British (F)":    "en-GB-LibbyNeural",
        "Maisie – British (F)":   "en-GB-MaisieNeural",
        "Oliver – British (M)":   "en-GB-OliverNeural",
        "Thomas – British (M)":   "en-GB-ThomasNeural",
    },
    "en-AU": {
        "⭐ Natasha – Australian (F)": "en-AU-NatashaNeural",
        "William – Australian (M)":   "en-AU-WilliamNeural",
    },
}

# ─────────────────────────────────────────────────────────────────
# STYLE / MOOD SUPPORT MAP
# Only certain voices support SSML express-as styles
# ─────────────────────────────────────────────────────────────────
VOICE_STYLES = {
    "en-US-AriaNeural":  [
        "chat", "cheerful", "excited", "empathetic",
        "newscast-casual", "customerservice",
        "shouting", "whispering", "sad", "angry", "hopeful", "friendly",
    ],
    "en-US-JennyNeural": ["chat", "customerservice", "assistant", "newscast"],
    "en-US-GuyNeural":   ["newscast", "excited"],
    "en-US-TonyNeural":  [
        "angry", "cheerful", "excited", "friendly",
        "hopeful", "sad", "shouting", "whispering",
    ],
    "en-US-NancyNeural": [
        "angry", "cheerful", "excited", "friendly",
        "hopeful", "sad", "shouting", "whispering",
    ],
    "en-US-DavisNeural": [
        "angry", "cheerful", "excited", "friendly",
        "hopeful", "sad", "shouting", "whispering",
    ],
    "en-US-SaraNeural":  ["cheerful", "angry"],
    "en-US-GuyNeural":   ["newscast", "excited"],
}

MOOD_LABELS = {
    "":                   "🎙️ Default Style",
    "chat":               "💬 Casual / Conversational",
    "cheerful":           "😄 Cheerful & Positive",
    "excited":            "⚡ Energetic & Excited",
    "empathetic":         "🤗 Warm & Empathetic",
    "newscast-casual":    "📰 Newscast – Relaxed",
    "customerservice":    "🎧 Professional",
    "shouting":           "📢 Loud / Hype",
    "whispering":         "🤫 Soft Whisper",
    "sad":                "😢 Emotional / Sad",
    "angry":              "😤 Intense / Angry",
    "hopeful":            "🌟 Hopeful & Uplifting",
    "friendly":           "😊 Warm & Friendly",
    "assistant":          "🤖 AI Assistant",
    "newscast":           "📺 Newscast – Formal",
}

# ─────────────────────────────────────────────────────────────────
# AGE / CHARACTER PRESETS — pitch + rate combos to simulate different
# voice ages AND tonal characters from the same base voice. Honest note:
# edge-tts only ships 2 base Urdu (Pakistan) voices (Uzma, Asad) — these
# presets don't add new synthetic voices, they reshape pitch/rate/tone
# on top of the existing ones so the same voice can sound noticeably
# different depending on the preset picked.
# ─────────────────────────────────────────────────────────────────
AGE_PRESETS = {
    "child":  {"rate": "+28%", "pitch": "+180Hz", "label": "👧 Child",  "desc": "High pitch, fast & energetic"},
    "teen":   {"rate": "+12%", "pitch": "+80Hz",  "label": "🧑 Teen",   "desc": "Slightly higher, lively"},
    "adult":  {"rate": "+0%",  "pitch": "+0Hz",   "label": "👩 Adult",  "desc": "Natural default tone"},
    "aged":   {"rate": "-12%", "pitch": "-60Hz",  "label": "👴 Aged",   "desc": "Deeper, slower, authoritative"},
    "deep":   {"rate": "-8%",  "pitch": "-110Hz", "label": "🎙️ Deep",   "desc": "Rich, low, cinematic tone"},
    "crisp":  {"rate": "+8%",  "pitch": "+20Hz",  "label": "✨ Crisp",  "desc": "Clear, sharp, energetic"},
    "warm":   {"rate": "-4%",  "pitch": "-20Hz",  "label": "🔥 Warm",   "desc": "Smooth, relaxed, inviting"},
    "bold":   {"rate": "+5%",  "pitch": "-40Hz",  "label": "💪 Bold",   "desc": "Confident, powerful, commanding"},
}

# ─────────────────────────────────────────────────────────────────
SAMPLE_SENTENCES = {
    "ur-PK": "السلام علیکم! آج کا دن بہت خاص ہے۔ ہمارے ساتھ رہیں اور کچھ نیا سیکھیں۔",
    "ur-IN": "ست سری اکال! آج کی اس ویڈیو میں ہم کچھ بہت خاص شیر کریں گے۔ ਜਡੀ ਰਹਨਾ ਹਮਾਰੇ ਨਾਲ!",
    "hi-IN": "नमस्ते! आज के इस वीडियो में हम आपके साथ कुछ बहुत खास शेयर करने वाले हैं। जुड़े रहिए हमारे साथ!",
    "pa-IN": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਅੱਜ ਦੀ ਇਸ ਵੀਡੀਓ ਵਿੱਚ ਅਸੀਂ ਕੁਝ ਬਹੁਤ ਹੀ ਖਾਸ ਸਾਂਝਾ ਕਰਾਂਗੇ। ਸਾਡੇ ਨਾਲ ਬਣੇ ਰਹੋ!",
    "en-US": "Hey! Welcome to the channel. Today we're going to share something absolutely incredible with you. Stay with us!",
    "en-GB": "Good day! We have something rather exciting to share with you today. Do stay tuned.",
    "en-AU": "G'day! Welcome aboard. We've got something truly amazing lined up for you today, so let's dive right in.",
}


# ─────────────────────────────────────────────────────────────────
# CORE TTS  (async)
# ─────────────────────────────────────────────────────────────────
async def _tts_async(text: str, voice: str, output_path: str,
                     rate: str = "+0%", pitch: str = "+0Hz",
                     style: str = "", style_degree: float = 1.0,
                     capture_timing: bool = False):
    """Generate speech with optional SSML style via edge-tts.
    If capture_timing=True, also returns a list of {word, start, end} dicts
    (seconds) built from edge-tts's WordBoundary events — used for captions."""
    if style and voice in VOICE_STYLES and style in VOICE_STYLES[voice]:
        lang = voice[:5]          # e.g. "en-US"
        escaped = (text
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        ssml = (
            f'<speak version="1.0" '
            f'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" '
            f'xml:lang="{lang}">'
            f'<voice name="{voice}">'
            f'<mstts:express-as style="{style}" styledegree="{style_degree:.1f}">'
            f'<prosody rate="{rate}" pitch="{pitch}">{escaped}</prosody>'
            f'</mstts:express-as></voice></speak>'
        )
        communicate = edge_tts.Communicate(ssml, voice)
    else:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

    word_timings = []
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif capture_timing and chunk["type"] == "WordBoundary":
                word_timings.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                })
    return word_timings


def parse_pitch_and_rate(pitch_str: str, rate_str: str):
    """Parse string pitch/rate inputs into numeric multipliers for FFmpeg."""
    pitch_factor = 1.0
    rate_factor = 1.0
    try:
        cleaned_pitch = pitch_str.strip().lower()
        if cleaned_pitch.endswith('hz'):
            val = float(cleaned_pitch.replace('hz', ''))
            pitch_factor = 1.0 + (val / 200.0)
        elif cleaned_pitch.endswith('%'):
            val = float(cleaned_pitch.replace('%', ''))
            pitch_factor = 1.0 + (val / 100.0)
    except Exception:
        pass
    try:
        cleaned_rate = rate_str.strip().lower()
        if cleaned_rate.endswith('%'):
            val = float(cleaned_rate.replace('%', ''))
            rate_factor = 1.0 + (val / 100.0)
    except Exception:
        pass
    pitch_factor = max(0.4, min(2.5, pitch_factor))
    rate_factor = max(0.4, min(2.5, rate_factor))
    return pitch_factor, rate_factor


def generate_speech_gtts(text: str, lang: str, output_path: str, gender: str,
                         rate_str: str = "+0%", pitch_str: str = "+0Hz") -> bool:
    """Generate speech via gTTS and apply pitch/speed filters using FFmpeg."""
    from gtts import gTTS
    import tempfile
    
    temp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    temp_mp3.close()
    
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(temp_mp3.name)
        
        pitch_factor, rate_factor = parse_pitch_and_rate(pitch_str, rate_str)
        if gender == 'male':
            pitch_factor *= 0.75
        pitch_factor = max(0.4, min(2.5, pitch_factor))
        
        tempo_factor = rate_factor / pitch_factor
        tempo_factor = max(0.5, min(2.0, tempo_factor))
        
        cmd = [
            "ffmpeg", "-y", "-i", temp_mp3.name,
            "-filter:a", f"asetrate=44100*{pitch_factor:.3f},atempo={tempo_factor:.3f}",
            output_path
        ]
        
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"[gTTS Postprocess Error] {res.stderr.decode('utf-8')}")
            import shutil
            shutil.copy(temp_mp3.name, output_path)
            
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"[gTTS Error] {e}")
        return False
    finally:
        if os.path.exists(temp_mp3.name):
            try:
                os.remove(temp_mp3.name)
            except Exception:
                pass


def generate_speech(text: str, voice: str, output_path: str,
                    rate: str = "+0%", pitch: str = "+0Hz",
                    style: str = "", style_degree: float = 1.0,
                    return_timing: bool = False):
    """Synchronous TTS wrapper. Returns True on success, or (bool, word_timings)
    if return_timing=True. word_timings is [] for gTTS voices (no boundary data)."""
    try:
        if voice.startswith("gtts-"):
            parts = voice.split("-")
            lang = parts[1]
            gender = parts[2]
            ok = generate_speech_gtts(text, lang, output_path, gender, rate, pitch)
            return (ok, []) if return_timing else ok

        # Use a fresh event loop to avoid conflicts with gunicorn threads
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        timings = []
        try:
            timings = loop.run_until_complete(_tts_async(text, voice, output_path,
                                               rate, pitch, style, style_degree,
                                               capture_timing=return_timing))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        ok = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        return (ok, timings or []) if return_timing else ok
    except Exception as e:
        print(f"[TTS Error] {e}")
        return (False, []) if return_timing else False


def generate_preview(voice: str, lang_prefix: str,
                     style: str = "", style_degree: float = 1.0,
                     rate: str = "+0%", pitch: str = "+0Hz",
                     output_path: str = "") -> bool:
    """Generate a short preview sample for the given voice+style."""
    sample = SAMPLE_SENTENCES.get(lang_prefix, SAMPLE_SENTENCES["en-US"])
    return generate_speech(sample, voice, output_path,
                           rate=rate, pitch=pitch,
                           style=style, style_degree=style_degree)


# ─────────────────────────────────────────────────────────────────
# AUDIO MIXING
# ─────────────────────────────────────────────────────────────────
def create_mixed_audio(voiceover_path: str, bg_music_path: str,
                       output_path: str, target_duration: float,
                       bg_volume: float = 0.15) -> bool:
    """
    Mix voiceover (full vol) with optional background music (bg_volume).
    Both are trimmed/padded to target_duration.

    Previously: if the voiceover was SHORTER than target_duration, nothing
    padded it, and the merge step's `-shortest` flag then truncated the
    entire video down to the voiceover's length — silently losing footage.
    Now the voiceover is padded with silence to exactly match target_duration.
    """
    try:
        from moviepy.audio.AudioClip import AudioClip, concatenate_audioclips

        voice_clip = AudioFileClip(voiceover_path)
        if voice_clip.duration > target_duration:
            voice_clip = voice_clip.subclip(0, target_duration)
        elif voice_clip.duration < target_duration - 0.05:
            pad_dur = target_duration - voice_clip.duration
            nch = getattr(voice_clip, 'nchannels', 2) or 2
            silence_frame = (lambda t: 0.0) if nch == 1 else (lambda t: [0.0] * nch)
            silence = AudioClip(silence_frame, duration=pad_dur, fps=voice_clip.fps or 44100)
            voice_clip = concatenate_audioclips([voice_clip, silence])

        if bg_music_path and os.path.exists(bg_music_path):
            bg_clip = AudioFileClip(bg_music_path)
            if bg_clip.duration < target_duration:
                loops = int(target_duration / bg_clip.duration) + 1
                bg_clip = concatenate_audioclips([bg_clip] * loops)
            bg_clip = bg_clip.subclip(0, target_duration).volumex(bg_volume)
            final_audio = CompositeAudioClip([voice_clip, bg_clip])
        else:
            final_audio = voice_clip

        final_audio.write_audiofile(output_path, fps=44100,
                                    verbose=False, logger=None)
        voice_clip.close()
        return True
    except Exception as e:
        print(f"[Audio Mix Error] {e}")
        return False


# ─────────────────────────────────────────────────────────────────
# AI VIDEO GENERATION (Script-to-Video)
# ─────────────────────────────────────────────────────────────────

UPLOAD_FOLDER_ABS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')

STOPWORDS = {"welcome", "to", "the", "channel", "today", "we", "are", "going", "have", "you", "a", "an", "of", "and", "in", "is", "it", "that", "this", "for", "with", "on", "at", "by", "from", "up", "about", "into", "over", "after"}

# ─────────────────────────────────────────────────────────────────
# PER-CLIP NARRATION SYNC (Merge tab)
# Splits the script across the uploaded clips (by sentence groups) and
# time-fits each segment to its clip's actual duration, so narration
# never drifts ahead of / behind the clip currently on screen.
# ─────────────────────────────────────────────────────────────────

def _distribute_sentences(sentences: list, n_groups: int) -> list:
    """Split a sentence list into n_groups ordered, near-equal chunks.
    If there are fewer sentences than groups, later groups are left empty
    (silent) rather than repeating narration."""
    groups = [[] for _ in range(n_groups)]
    if not sentences or n_groups <= 0:
        return groups
    if len(sentences) >= n_groups:
        k, m = divmod(len(sentences), n_groups)
        idx = 0
        for i in range(n_groups):
            size = k + (1 if i < m else 0)
            groups[i] = sentences[idx: idx + size]
            idx += size
    else:
        for i, s in enumerate(sentences):
            groups[i] = [s]
    return groups


def generate_synced_narration(script_text: str, clip_durations: list, voice_id: str,
                               output_path: str, rate: str = "+0%", pitch: str = "+0Hz",
                               style: str = "", style_degree: float = 1.0,
                               max_speedup: float = 1.25) -> bool:
    """
    Generates one narration track whose segments are time-locked to each
    uploaded clip's actual duration — segment i always plays exactly during
    clip i, never drifting into the next clip.
    Returns (success: bool, sentence_groups: list) — the groups are the
    exact per-clip text used, needed to build caption cues with matching timing.
    """
    sentences = split_into_sentences(script_text)
    n = len(clip_durations)
    if n == 0:
        return False, []
    groups = _distribute_sentences(sentences, n)

    tmp_dir = tempfile.mkdtemp(prefix="sync_narr_")
    seg_paths = []
    try:
        for i, (group, dur) in enumerate(zip(groups, clip_durations)):
            dur = max(dur, 0.1)
            raw_path = os.path.join(tmp_dir, f"raw_{i}.mp3")
            fixed_path = os.path.join(tmp_dir, f"fixed_{i}.mp3")
            text = " ".join(group).strip()
            has_audio = False

            if text:
                ok = generate_speech(text, voice_id, raw_path, rate=rate, pitch=pitch,
                                      style=style, style_degree=style_degree)
                has_audio = ok and os.path.exists(raw_path) and os.path.getsize(raw_path) > 0

            if has_audio:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", raw_path],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                try:
                    seg_dur = float(probe.stdout.strip())
                except Exception:
                    seg_dur = dur

                factor = 1.0
                if seg_dur > dur and dur > 0:
                    factor = min(seg_dur / dur, max_speedup)

                cmd = [
                    "ffmpeg", "-y", "-i", raw_path,
                    "-filter:a", f"atempo={factor:.3f},apad",
                    "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2",
                    fixed_path
                ]
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                has_audio = r.returncode == 0 and os.path.exists(fixed_path) and os.path.getsize(fixed_path) > 0

            if not has_audio:
                # Silent segment — clip has no matching sentence, or TTS failed
                cmd = [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "2", fixed_path
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(fixed_path) and os.path.getsize(fixed_path) > 0:
                seg_paths.append(fixed_path)

        if not seg_paths:
            return False, groups

        cmd = ["ffmpeg", "-y"]
        for p in seg_paths:
            cmd += ["-i", p]
        filter_inputs = "".join(f"[{i}:a]" for i in range(len(seg_paths)))
        cmd += ["-filter_complex", f"{filter_inputs}concat=n={len(seg_paths)}:v=0:a=1[out]",
                "-map", "[out]", output_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ok = (result.returncode == 0 and os.path.exists(output_path)
              and os.path.getsize(output_path) > 0)
        return ok, groups
    except Exception as e:
        print(f"[Narration Sync Error] {e}")
        return False, []
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _format_srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        millis = 0
        secs += 1
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def write_srt(cues: list, output_path: str) -> bool:
    """
    cues: list of (start_seconds, end_seconds, text) tuples, in order.
    Writes a standard .srt subtitle file.
    """
    try:
        lines = []
        idx = 1
        for start, end, text in cues:
            text = (text or "").strip()
            if not text or end <= start:
                continue
            lines.append(str(idx))
            lines.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
            lines.append(text)
            lines.append("")
            idx += 1
        if not lines:
            return False
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True
    except Exception as e:
        print(f"[SRT Write Error] {e}")
        return False


def build_caption_cues_from_groups(sentence_groups: list, segment_durations: list) -> list:
    """For per-clip / per-slide narration: each group already has an exact
    start/end (the cumulative clip durations), so captions line up exactly
    with what's on screen — no guessing involved."""
    cues = []
    t = 0.0
    for group, dur in zip(sentence_groups, segment_durations):
        dur = max(dur, 0.1)
        text = " ".join(group).strip()
        if text:
            cues.append((t, t + dur, text))
        t += dur
    return cues


def build_caption_cues_estimated(script_text: str, total_duration: float) -> list:
    """Fallback for a single continuous narration track (one clip, no
    per-segment timing available): distributes sentences across the total
    duration weighted by character length. Approximate, not frame-exact —
    fine for captions, would NOT be fine for audio sync."""
    sentences = split_into_sentences(script_text)
    if not sentences or total_duration <= 0:
        return []
    weights = [max(len(s), 1) for s in sentences]
    total_w = sum(weights)
    cues = []
    t = 0.0
    for s, w in zip(sentences, weights):
        dur = total_duration * (w / total_w)
        cues.append((t, t + dur, s))
        t += dur
    return cues


def extract_keyword(text: str) -> str:
    """Extract 1 to 2 key descriptive words from a script sentence."""
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    if filtered:
        return " ".join(filtered[:2])
    return "abstract"


def get_font_for_lang(lang: str) -> str:
    """Find a suitable system font for the language to handle non-English glyphs.
    Works on both macOS and Linux (Docker/HF Spaces).
    """
    # Linux (Docker) font paths — installed via apt fonts-dejavu-core, fonts-liberation
    linux_unicode = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    # macOS font paths — fallback when running locally
    macos_unicode = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]

    # Try language-specific paths first (Linux then macOS)
    lang_paths = []
    if lang.startswith("pa"):
        lang_paths = [
            "/System/Library/Fonts/Supplemental/Gurmukhi MN.ttc",
        ]
    elif lang.startswith("hi"):
        lang_paths = [
            "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
        ]

    for p in lang_paths + linux_unicode + macos_unicode:
        if os.path.exists(p):
            return p
    return "DejaVuSans"  # Last resort — PIL will try to find it


def make_ken_burns_frame(img_obj, target_w, target_h, t, duration, zoom_ratio=0.12):
    """Crop and zoom a frame dynamically to create a smooth Ken Burns effect."""
    img_w, img_h = img_obj.size
    scale = 1.0 - (zoom_ratio * (t / duration))
    target_aspect = target_w / target_h
    img_aspect = img_w / img_h
    
    if img_aspect > target_aspect:
        crop_h = img_h * scale
        crop_w = crop_h * target_aspect
    else:
        crop_w = img_w * scale
        crop_h = crop_w / target_aspect
        
    left = (img_w - crop_w) / 2
    top = (img_h - crop_h) / 2
    cropped = img_obj.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((target_w, target_h), PIL.Image.Resampling.LANCZOS)


def draw_wrapped_text(draw, text, font, max_width, center_x, center_y, fill_color, stroke_color, stroke_width):
    """Draw wrapped caption text with a clean dark border/stroke."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        try:
            w = font.getlength(line_str)
        except AttributeError:
            w, _ = draw.textsize(line_str, font=font) if hasattr(draw, 'textsize') else (font.getmask(line_str).getbbox()[2], 0)
            
        if w > max_width:
            if len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(line_str)
                current_line = []
                
    if current_line:
        lines.append(" ".join(current_line))
        
    # Draw centered lines
    y = center_y - (len(lines) * font.size * 1.25) / 2
    for line in lines:
        try:
            line_w = font.getlength(line)
        except AttributeError:
            line_w, _ = draw.textsize(line, font=font) if hasattr(draw, 'textsize') else (font.getmask(line).getbbox()[2], 0)
            
        x = center_x - line_w / 2
        # Stroke / Border
        if stroke_width > 0:
            for offset_x in range(-stroke_width, stroke_width + 1):
                for offset_y in range(-stroke_width, stroke_width + 1):
                    if offset_x != 0 or offset_y != 0:
                        draw.text((x + offset_x, y + offset_y), line, font=font, fill=stroke_color)
                        
        draw.text((x, y), line, font=font, fill=fill_color)
        y += font.size * 1.30


def download_slide_image(keyword: str, width: int, height: int, index: int, dest_path: str) -> bool:
    """Fetch random themed royalty-free stock image via loremflickr."""
    try:
        url = f"https://loremflickr.com/{width}/{height}/{urllib.parse.quote(keyword.replace(' ', ','))}?random={index}"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
    except Exception as e:
        print(f"[Download Image Error] {e}")
        return False


def search_mixkit_videos(keyword: str) -> list:
    """Search Mixkit for free stock videos and return a list of MP4 URLs."""
    # Clean up keyword: replace spaces with hyphens, convert to lower case, and alphanumeric only
    clean_kw = re.sub(r'[^a-zA-Z0-9\s-]', '', keyword).strip().lower()
    clean_kw = re.sub(r'[\s-]+', '-', clean_kw)
    if not clean_kw:
        clean_kw = "abstract"
    
    url = f"https://mixkit.co/free-stock-video/{clean_kw}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as res:
            html = res.read().decode('utf-8', errors='ignore')
            
        mp4_urls = re.findall(r'https://[^\s"\']*?\.mp4', html)
        unique_urls = list(set(mp4_urls))
        
        # Map 360p URLs to 720p equivalents to get HD while keeping download sizes small (~5MB)
        processed_urls = []
        for u in unique_urls:
            if "-360.mp4" in u:
                high_res = u.replace("-360.mp4", "-720.mp4")
                processed_urls.append(high_res)
                processed_urls.append(u)
            elif "-video-360.mp4" in u:
                high_res = u.replace("-video-360.mp4", "-video-720.mp4")
                processed_urls.append(high_res)
                processed_urls.append(u)
            else:
                processed_urls.append(u)
                
        seen = set()
        final_urls = []
        for u in processed_urls:
            if u not in seen:
                seen.add(u)
                final_urls.append(u)
        return final_urls
    except Exception as e:
        print(f"[Mixkit Search Error for '{keyword}']: {e}")
        return []


def download_mixkit_video(keyword: str, index: int, dest_path: str) -> bool:
    """Search Mixkit and download the first valid video file."""
    urls = search_mixkit_videos(keyword)
    if not urls and " " in keyword:
        # Try individual words
        words = [w for w in keyword.split() if len(w) > 2]
        for w in words:
            urls = search_mixkit_videos(w)
            if urls:
                print(f"[Mixkit Fallback] Found videos using word: '{w}'")
                break
                
    if not urls:
        return False
        
    selected_url = urls[index % len(urls)]
    try_urls = []
    if "-360.mp4" in selected_url:
        try_urls.append(selected_url.replace("-360.mp4", "-720.mp4"))
    elif "-video-360.mp4" in selected_url:
        try_urls.append(selected_url.replace("-video-360.mp4", "-video-720.mp4"))
    try_urls.append(selected_url)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in try_urls:
        try:
            print(f"Downloading video clip from: {url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as response:
                with open(dest_path, 'wb') as f:
                    f.write(response.read())
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                print(f"Video clip downloaded successfully: {url}")
                return True
        except Exception as e:
            print(f"Failed to download video clip {url}: {e}")
            
    return False


def fetch_video_segment(keyword: str, index: int, dest_path: str, fallback_theme: str) -> str:
    """
    Attempts to download a stock video clip. Falls back to other keywords if needed.
    Returns: 'video' or 'image' depending on which media type was successfully downloaded.
    """
    if download_mixkit_video(keyword, index, dest_path):
        return "video"
        
    if fallback_theme and fallback_theme != "auto":
        print(f"[Mixkit Fallback] Video search for '{keyword}' failed, trying theme: '{fallback_theme}'")
        if download_mixkit_video(fallback_theme, index, dest_path):
            return "video"
            
    safe_terms = ["abstract", "nature", "city", "technology"]
    for term in safe_terms:
        print(f"[Mixkit Fallback] Video search failed, trying safe category: '{term}'")
        if download_mixkit_video(term, index, dest_path):
            return "video"
            
    return "image"


def download_ai_generated_image(prompt: str, width: int, height: int, dest_path: str) -> bool:
    """Generate and download a custom AI image via Hugging Face Space (Stable Diffusion 3) based on the prompt."""
    try:
        from gradio_client import Client
        import shutil
        
        space = "stabilityai/stable-diffusion-3-medium"
        # We ensure width/height are standard multiples of 64 or 128 that SD3 supports well
        sd_w = 1024 if width > height else 768
        sd_h = 768 if width > height else 1024
        
        print(f"Connecting to Hugging Face Space '{space}' to generate image for prompt: '{prompt}'...")
        client = Client(space)
        
        result = client.predict(
            prompt=prompt,
            negative_prompt="deformed, low quality, bad hands, blurry, watermark",
            seed=0,
            randomize_seed=True,
            width=sd_w,
            height=sd_h,
            guidance_scale=5.0,
            num_inference_steps=20,
            api_name="/infer"
        )
        
        image_path = result[0] if isinstance(result, tuple) else result
        if image_path and os.path.exists(image_path):
            shutil.copy(image_path, dest_path)
            print(f"Successfully generated AI image saved to: {dest_path}")
            return True
        else:
            print("[AI Generation Error] Result path does not exist.")
            return False
            
    except Exception as e:
        print(f"[AI Generation Error] Failed to generate image via Gradio Space: {e}")
        return False


def split_into_sentences(text: str) -> list:
    """Split text script into clean sentences."""
    sentences = re.split(r'[.!?\n۔।]+', text)
    cleaned = []
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) > 3:
            cleaned.append(s_clean)
    return cleaned


def make_video_frame_closure(video_clip_obj, text, dur, w, h, f_path, f_sz):
    try:
        font = ImageFont.truetype(f_path, f_sz)
    except Exception:
        font = ImageFont.load_default()
        
    def make_frame(t):
        safe_t = min(t, video_clip_obj.duration - 0.01)
        frame_rgb = video_clip_obj.get_frame(safe_t)
        frame_img = PIL.Image.fromarray(frame_rgb)
        
        # Semi-transparent overlay at bottom
        overlay = PIL.Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([0, int(h * 0.65), w, h], fill=(0, 0, 0, 120))
        combined = PIL.Image.alpha_composite(frame_img.convert('RGBA'), overlay).convert('RGB')
        
        draw = ImageDraw.Draw(combined)
        draw_wrapped_text(
            draw=draw,
            text=text,
            font=font,
            max_width=int(w * 0.85),
            center_x=w / 2,
            center_y=h * 0.80,
            fill_color=(255, 255, 255),
            stroke_color=(0, 0, 0),
            stroke_width=3
        )
        return np.array(combined)
    return make_frame


def make_image_frame_closure(i_obj, text, dur, w, h, f_path, f_sz):
    try:
        font = ImageFont.truetype(f_path, f_sz)
    except Exception:
        font = ImageFont.load_default()
        
    def make_frame(t):
        frame_img = make_ken_burns_frame(i_obj, w, h, t, dur)
        overlay = PIL.Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.rectangle([0, int(h * 0.65), w, h], fill=(0, 0, 0, 120))
        combined = PIL.Image.alpha_composite(frame_img.convert('RGBA'), overlay).convert('RGB')
        
        draw = ImageDraw.Draw(combined)
        draw_wrapped_text(
            draw=draw,
            text=text,
            font=font,
            max_width=int(w * 0.85),
            center_x=w / 2,
            center_y=h * 0.80,
            fill_color=(255, 255, 255),
            stroke_color=(0, 0, 0),
            stroke_width=3
        )
        return np.array(combined)
    return make_frame


def generate_ai_video(script_text: str, theme: str, aspect_ratio: str,
                       voice_id: str, rate: str, pitch: str,
                       bg_music_file, trim_audio: bool, output_path: str,
                       captions: bool = False) -> dict:
    """End-to-end AI script-to-video generation."""
    from moviepy.editor import VideoFileClip, VideoClip, concatenate_videoclips, concatenate_audioclips
    from utils.video_effects import crop_to_aspect_ratio, burn_subtitles

    if aspect_ratio == 'vertical':
        target_w, target_h = 1080, 1920
    else:
        target_w, target_h = 1920, 1080
        
    sentences = split_into_sentences(script_text)
    if not sentences:
        raise ValueError("Script text contains no valid sentences.")
        
    job_id = str(uuid.uuid4())
    temp_files = []
    video_clips = []
    audio_clips = []
    downloaded_video_clips = []
    
    try:
        theme_keywords = {
            "space": "space,galaxy",
            "tech": "technology,cyberpunk,coding",
            "nature": "nature,landscape,forest",
            "finance": "finance,business,money",
            "city": "city,urban,street",
            "abstract": "abstract,gradient,art"
        }
        base_keyword = theme_keywords.get(theme, "abstract")
        
        lang_code = "en"
        if voice_id.startswith("gtts-"):
            parts = voice_id.split("-")
            if len(parts) > 1:
                lang_code = parts[1]
        elif len(voice_id) >= 5:
            lang_code = voice_id[:2]
            
        font_path = get_font_for_lang(lang_code)
        caption_cues = []
        running_t = 0.0
        
        for idx, sentence in enumerate(sentences):
            # 1. Voiceover for this slide
            sentence_audio_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_speech_{idx}.mp3")
            ok = generate_speech(sentence, voice_id, sentence_audio_path, rate=rate, pitch=pitch)
            if not ok or not os.path.exists(sentence_audio_path):
                raise ValueError(f"Failed to generate speech for sentence: {sentence}")
            temp_files.append(sentence_audio_path)
            
            audio_clip = AudioFileClip(sentence_audio_path)
            duration = audio_clip.duration
            audio_clips.append(audio_clip)
            caption_cues.append((running_t, running_t + duration, sentence))
            running_t += duration
            
            # 2. Extract keyword and search stock media or generate AI scene
            keyword = base_keyword
            if theme == "auto":
                keyword = extract_keyword(sentence)
                
            media_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_media_{idx}.mp4")
            
            font_size = 55 if aspect_ratio == 'vertical' else 45
            
            if theme == "ai_generative":
                # AI Generative Mode: skip Mixkit search, directly trigger Flux/Sora-style scene generation
                media_type = "image"
            else:
                # Stock Video Mode
                print(f"Processing slide {idx}: keyword='{keyword}', duration={duration:.2f}s")
                media_type = fetch_video_segment(keyword, idx, media_path, fallback_theme=base_keyword)
                temp_files.append(media_path)
            
            if media_type == "video":
                # Create moving video slide using downloaded stock clip
                try:
                    downloaded_clip = VideoFileClip(media_path)
                    processed_clip = crop_to_aspect_ratio(downloaded_clip, target_w, target_h)
                    downloaded_video_clips.append(downloaded_clip)
                    
                    if processed_clip.duration < duration:
                        # Loop video clip if it is too short
                        loops = int(duration / processed_clip.duration) + 1
                        processed_clip = concatenate_videoclips([processed_clip] * loops)
                    processed_clip = processed_clip.subclip(0, duration)
                    
                    frame_gen = make_video_frame_closure(processed_clip, sentence, duration, target_w, target_h, font_path, font_size)
                    video_clip = VideoClip(frame_gen, duration=duration)
                    video_clips.append(video_clip)
                except Exception as ve:
                    print(f"Error processing video slide {idx}: {ve}. Falling back to image.")
                    media_type = "image"
                    
            if media_type == "image":
                # Generative AI Image or Stock Image Fallback
                image_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_image_{idx}.jpg")
                
                if theme == "ai_generative":
                    # Generate exact custom match scene using Flux/Pollinations AI
                    ok = download_ai_generated_image(sentence, target_w, target_h, image_path)
                else:
                    # Random themed stock image fallback
                    ok = download_slide_image(keyword, target_w, target_h, idx + 1, image_path)
                    
                if not ok or not os.path.exists(image_path):
                    # Solid color fallback
                    img = PIL.Image.new('RGB', (target_w, target_h), color=(30 + (idx * 20) % 150, 45, 85))
                    img.save(image_path)
                temp_files.append(image_path)
                
                img_obj = PIL.Image.open(image_path)
                frame_gen = make_image_frame_closure(img_obj, sentence, duration, target_w, target_h, font_path, font_size)
                video_clip = VideoClip(frame_gen, duration=duration)
                video_clips.append(video_clip)
            
        # 4. Concatenate visual and audio
        final_video_raw = concatenate_videoclips(video_clips, method="compose")
        final_audio_raw = concatenate_audioclips(audio_clips)
        
        temp_video_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_raw_video.mp4")
        temp_audio_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_raw_audio.mp3")
        temp_files.extend([temp_video_path, temp_audio_path])
        
        final_audio_raw.write_audiofile(temp_audio_path, verbose=False, logger=None)
        
        # Mix background music
        mixed_audio_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_mixed_audio.mp3")
        temp_files.append(mixed_audio_path)
        
        bg_music_path = None
        if bg_music_file and bg_music_file.filename != '':
            bg_music_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_bg_music.mp3")
            bg_music_file.save(bg_music_path)
            temp_files.append(bg_music_path)
            
        create_mixed_audio(
            voiceover_path=temp_audio_path,
            bg_music_path=bg_music_path,
            output_path=mixed_audio_path,
            target_duration=final_video_raw.duration,
            bg_volume=0.15
        )
        
        # Render video with ultrafast preset for maximum speed
        final_video_raw.write_videofile(temp_video_path, fps=24, preset="ultrafast", verbose=False, logger=None)
        
        # FFmpeg combine
        cmd = [
            "ffmpeg", "-y", "-i", temp_video_path, "-i", mixed_audio_path,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            "-shortest" if trim_audio else "", output_path
        ]
        cmd = [c for c in cmd if c != ""]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # Burn in captions — timing here is exact (each cue's window is the
        # same duration used to generate that slide's visual), no guessing.
        if captions and caption_cues:
            srt_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_captions.srt")
            temp_files.append(srt_path)
            if write_srt(caption_cues, srt_path):
                captioned_path = os.path.join(UPLOAD_FOLDER_ABS, f"{job_id}_captioned.mp4")
                temp_files.append(captioned_path)
                if burn_subtitles(output_path, srt_path, captioned_path):
                    os.remove(output_path)
                    os.rename(captioned_path, output_path)
        
        # Cleanup clips memory
        for c in video_clips: c.close()
        for c in audio_clips: c.close()
        for c in downloaded_video_clips: c.close()
        final_video_raw.close()
        final_audio_raw.close()
        
        return {
            "success": True,
            "duration": final_video_raw.duration,
            "sentences_count": len(sentences)
        }
        
    finally:
        for p in temp_files:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
