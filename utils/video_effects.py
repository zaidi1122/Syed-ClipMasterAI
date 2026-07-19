import os
import subprocess
import tempfile

def crop_to_aspect_ratio(clip, target_w, target_h):
    """
    Crops a video clip from its center to match the target aspect ratio,
    then resizes it to the target dimensions.
    (Kept for any remaining moviepy usage, but concatenate_clips no longer uses this.)
    """
    from moviepy.editor import VideoFileClip
    w, h = clip.size
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        new_w = int(h * target_aspect)
        x1 = (w - new_w) // 2
        x2 = x1 + new_w
        clip_cropped = clip.crop(x1=x1, y1=0, x2=x2, y2=h)
    else:
        new_h = int(w / target_aspect)
        y1 = (h - new_h) // 2
        y2 = y1 + new_h
        clip_cropped = clip.crop(x1=0, y1=y1, x2=w, y2=y2)
        
    return clip_cropped.resize(newsize=(target_w, target_h))

def concatenate_clips(video_paths, aspect_ratio="vertical", output_path=None):
    """
    Concatenates multiple video files using pure FFmpeg (no moviepy).
    Each clip is normalized to the target resolution before joining.
    Returns (total_duration, per_clip_durations) — the second is needed
    to time-align per-clip narration segments.
    """
    if not video_paths:
        raise ValueError("No video paths provided to concatenate.")

    existing = [p for p in video_paths if os.path.exists(p) and os.path.getsize(p) > 0]
    if not existing:
        raise ValueError("None of the provided video paths exist or could be loaded.")

    target_w, target_h = (1080, 1920) if aspect_ratio == "vertical" else (1920, 1080)

    # ── Step 1: Normalize every clip to target resolution ────────────
    norm_dir = tempfile.mkdtemp(prefix="concat_norm_")
    normalized = []

    for i, path in enumerate(existing):
        norm_path = os.path.join(norm_dir, f"norm_{i}.mp4")
        # scale+pad to target size, keep audio, re-encode to uniform codec
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:-1:-1:color=black,"
            f"fps=30"
        )
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            norm_path
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode == 0 and os.path.exists(norm_path) and os.path.getsize(norm_path) > 0:
            normalized.append(norm_path)
        else:
            print(f"[concat] Warning: failed to normalize {path}, skipping.")

    if not normalized:
        raise RuntimeError("All clips failed to normalize — cannot concatenate.")

    # ── Step 2: Write concat list file ───────────────────────────────
    concat_list = os.path.join(norm_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    # ── Step 3: Get per-clip and total duration via ffprobe ──────────
    clip_durations = []
    for p in normalized:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            clip_durations.append(float(probe.stdout.strip()))
        except Exception:
            clip_durations.append(0.0)
    total_duration = sum(clip_durations)

    # ── Step 4: Concatenate ───────────────────────────────────────────
    if output_path:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            err = r.stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"FFmpeg concat failed: {err}")

    # ── Cleanup temp normalized clips ─────────────────────────────────
    for p in normalized:
        try:
            os.remove(p)
        except Exception:
            pass
    try:
        os.remove(concat_list)
        os.rmdir(norm_dir)
    except Exception:
        pass

    return total_duration, clip_durations


def pitch_shift_audio(input_audio_path, output_audio_path, semitones=0.8):
    """
    Pitch shifts an audio file using FFmpeg's asetrate and atempo filters.
    semitones: shift amount (positive = higher, negative = lower).
    """
    multiplier = 2.0 ** (semitones / 12.0)
    sample_rate = 44100
    new_rate = int(sample_rate * multiplier)
    tempo = 1.0 / multiplier
    
    cmd = [
        "ffmpeg", "-y", "-i", input_audio_path,
        "-filter_complex", f"asetrate={new_rate},atempo={tempo}",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

QUALITY_PRESETS = {
    "720p":  {"vertical": (720, 1280),   "horizontal": (1280, 720)},
    "1080p": {"vertical": (1080, 1920),  "horizontal": (1920, 1080)},
    "4k":    {"vertical": (2160, 3840),  "horizontal": (3840, 2160)},
}

# Encoder preset per quality tier — higher resolutions get a slower/more
# efficient preset since file size grows fast at 4K.
ENCODE_PRESET = {"720p": "faster", "1080p": "fast", "4k": "medium"}


def burn_subtitles(input_path: str, srt_path: str, output_path: str) -> bool:
    """
    Burns styled captions into the video using FFmpeg's libass-based
    subtitles filter. Font size scales with video height for readability
    on both 9:16 and 16:9 output.
    """
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=height",
         "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        height = int(probe.stdout.strip())
    except Exception:
        height = 1080
    font_size = max(24, round(height * 0.045))

    # Escape path for the ffmpeg filter graph (colons/backslashes need escaping)
    escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    style = (
        f"FontName=DejaVu Sans,FontSize={font_size},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,Bold=1,"
        "Alignment=2,MarginV=" + str(round(height * 0.06))
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"subtitles='{escaped_srt}':force_style='{style}'",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (result.returncode == 0 and os.path.exists(output_path)
            and os.path.getsize(output_path) > 0)


def apply_copyright_filters(input_path, output_path, options):
    """
    Applies visual and audio transformations to bypass copyright filters.
    Uses pure FFmpeg subprocess for reliability — no moviepy silent failures.

    Filters applied:
    - Aspect Ratio (vertical 9:16, horizontal 16:9, or original) at a chosen quality tier
    - Horizontal mirror (hflip)
    - 5% center zoom-in (crop + scale)
    - Speed adjustment (setpts + atempo)
    - Audio pitch shift (asetrate + atempo correction)
    """
    aspect       = options.get("aspect_ratio", "original")
    quality      = options.get("quality", "1080p")
    if quality not in QUALITY_PRESETS:
        quality = "1080p"
    do_mirror    = options.get("mirror", True)
    do_zoom      = options.get("zoom", True)
    speed_factor = float(options.get("speed", 1.04))
    pitch_semi   = float(options.get("pitch_shift", 0.8))

    # ── Check if the source has an audio stream ──────────────────────
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name",
         "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    has_audio = bool(probe.stdout.strip())

    # ── Build video filter chain ──────────────────────────────────────
    vf = []

    if aspect in ("vertical", "horizontal"):
        target_w, target_h = QUALITY_PRESETS[quality][aspect]
        vf.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                  f"pad={target_w}:{target_h}:-1:-1:color=black")

    if do_mirror:
        vf.append("hflip")

    if do_zoom:
        # Scale up 5%, then crop center back to original size
        vf.append("scale=iw*1.05:ih*1.05,crop=iw/1.05:ih/1.05")

    if speed_factor != 1.0:
        vf.append(f"setpts=PTS/{speed_factor:.4f}")

    # ── Build audio filter chain ──────────────────────────────────────
    af = []

    if has_audio:
        if speed_factor != 1.0:
            af.append(f"atempo={speed_factor:.4f}")

        if pitch_semi != 0.0:
            # asetrate shifts pitch; atempo corrects back to original speed
            multiplier = 2.0 ** (pitch_semi / 12.0)
            new_rate   = int(44100 * multiplier)
            tempo_corr = 1.0 / multiplier
            af.append(f"asetrate={new_rate},atempo={tempo_corr:.6f}")

    # ── Assemble FFmpeg command ───────────────────────────────────────
    cmd = ["ffmpeg", "-y", "-i", input_path]

    if vf:
        cmd += ["-vf", ",".join(vf)]

    cmd += ["-c:v", "libx264", "-preset", ENCODE_PRESET[quality], "-movflags", "+faststart"]

    if has_audio:
        if af:
            cmd += ["-af", ",".join(af)]
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]   # no audio stream in source — don't try to encode one

    cmd.append(output_path)

    # ── Run ───────────────────────────────────────────────────────────
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        err = result.stderr.decode("utf-8", errors="ignore")[-600:]
        raise RuntimeError(f"FFmpeg filter failed for {os.path.basename(input_path)}: {err}")


def slice_video(input_path, output_dir, mode="auto", intervals=8, custom_ranges=None):
    """
    Slices a video into multiple segments.
    mode: "auto" (split every N seconds) or "timestamps" (split by custom list of ranges).
    intervals: number of seconds per slice in auto mode.
    custom_ranges: list of tuples/lists e.g. [[10, 20], [35, 45]] (in seconds).
    Returns a list of created file paths.
    """
    clip = VideoFileClip(input_path)
    duration = clip.duration
    clip.close()
    
    slices = []
    if mode == "auto":
        start = 0
        idx = 1
        while start < duration:
            end = min(start + intervals, duration)
            # Avoid tiny trailing clips less than 1 second
            if duration - end < 1.0:
                end = duration
            slices.append((start, end, f"clip_{idx}.mp4"))
            idx += 1
            if end == duration:
                break
            start = end
    elif mode == "timestamps" and custom_ranges:
        for idx, r in enumerate(custom_ranges, 1):
            start = r[0]
            end = min(r[1], duration)
            if start < duration:
                slices.append((start, end, f"clip_{idx}.mp4"))
                
    output_files = []
    for start, end, filename in slices:
        out_path = os.path.join(output_dir, filename)
        # Use FFmpeg directly for fast lossless seeking and cutting
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
            "-i", input_path, "-c", "copy", out_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            output_files.append(out_path)
            
    return output_files
