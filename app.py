import streamlit as st
import os
import subprocess
import math
import concurrent.futures
import asyncio
import edge_tts
import time
import shutil
import gc
import threading
import base64
import json
import tempfile
# ─────────────────────────────────────────────
# Timer Utility
# ─────────────────────────────────────────────

def format_time(seconds):
    """Format seconds into mm:ss or mm:ss.ms format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 10)
    if mins > 0:
        return f"{mins}:{secs:02d}"
    return f"{secs}.{ms}s"


# ─────────────────────────────────────────────
# TTS Voices, Recap Styles, and Emotions
# ─────────────────────────────────────────────

@st.cache_resource
def get_voices():
    return [
        {"id": "v1", "name": "V1 ♂", "gender": "Male"},
        {"id": "v2", "name": "V2 ♀", "gender": "Female"},
        {"id": "v3", "name": "V3 ♂", "gender": "Male"},
        {"id": "v4", "name": "V4 ♂", "gender": "Male"},
        {"id": "v5", "name": "V5 ♂", "gender": "Male"},
        {"id": "v6", "name": "V6 ♀", "gender": "Female"},
        {"id": "v7", "name": "V7 ♂", "gender": "Male"},
        {"id": "v8", "name": "V8 ♀", "gender": "Female"},
        {"id": "v9", "name": "V9 ♂", "gender": "Male"},
        {"id": "v10", "name": "V10 ♀", "gender": "Female"},
        {"id": "v11", "name": "V11 ♀", "gender": "Female"},
        {"id": "v12", "name": "V12 ♂", "gender": "Male"},
        {"id": "v13", "name": "V13 ♀", "gender": "Female"},
        {"id": "v14", "name": "V14 ♂", "gender": "Male"},
        {"id": "v15", "name": "V15 ♀", "gender": "Female"},
        {"id": "v16", "name": "V16 ♀", "gender": "Female"},
        {"id": "v17", "name": "V17 ♂", "gender": "Male"},
        {"id": "v18", "name": "V18 ♂", "gender": "Male"},
        {"id": "v19", "name": "V19 ♀", "gender": "Female"}
    ]

@st.cache_resource
def get_recap_styles():
    return [
        {"id": "Normal", "name": "ပုံမှန်အသံ", "speed": 0, "pitch": 0},
        {"id": "NyoGyi_25", "name": "ကျားကြီး ၁", "speed": 0, "pitch": 25},
        {"id": "NyoGyi_35", "name": "ကျားကြီး ၂", "speed": 0, "pitch": 35},
        {"id": "NyoGyi_45", "name": "ကျားကြီး ၃", "speed": 0, "pitch": 45},
        {"id": "Nilar_40", "name": "နီလာ ချွဲသံ", "speed": 0, "pitch": 40},
        {"id": "Combo_15", "name": "ပေါင်းစပ် ၁၅", "speed": 15, "pitch": 15},
        {"id": "Combo_30", "name": "ပေါင်းစပ် ၃၀", "speed": 30, "pitch": 30},
        {"id": "Combo_50", "name": "ပေါင်းစပ် ၅၀", "speed": 50, "pitch": 50},
        {"id": "Pitch_20", "name": "အသံသေး ၂၀", "speed": 0, "pitch": 20},
        {"id": "Pitch_50", "name": "အသံသေး ၅၀", "speed": 0, "pitch": 50}
    ]

@st.cache_resource
def get_emotions():
    return [
        {"id": "EXCITING", "name": "စိတ်လှုပ်ရှား 🤩", "s": 15, "p": 10},
        {"id": "CALM", "name": "တည်ငြိမ် 😌", "s": -10, "p": -5},
        {"id": "PROFESSIONAL", "name": "သတင်း 💼", "s": 0, "p": -2},
        {"id": "NARRATIVE", "name": "ဇာတ်ကြောင်း 📖", "s": -5, "p": 0},
        {"id": "HAPPY", "name": "ပျော်ရွှင် 😊", "s": 10, "p": 15},
        {"id": "SERIOUS", "name": "လေးနက် 😠", "s": -5, "p": -10},
        {"id": "WHISPER", "name": "တီးတိုး 🤫", "s": -15, "p": -20},
        {"id": "SAD", "name": "ဝမ်းနည်း 😢", "s": -15, "p": -15},
        {"id": "SARCASTIC", "name": "ရွဲ့ပြော 🙄", "s": -10, "p": 5},
        {"id": "ANGRY", "name": "ဒေါသထွက် 🤬", "s": 20, "p": -10},
        {"id": "FEAR", "name": "ကြောက်လန့် 😨", "s": 10, "p": 20}
    ]

VOICES = get_voices()
RECAP_STYLES = get_recap_styles()
EMOTIONS = get_emotions()

st.set_page_config(page_title="Dubbing Script", layout="wide")


# ─────────────────────────────────────────────
# SRT Subtitle Generator
# ─────────────────────────────────────────────

class SmartSubMaker:
    """Generate SRT subtitles proportional to text length and total video duration."""

    def __init__(self, full_text, duration_seconds):
        self.full_text = full_text.strip().replace('\n', ' ')
        self.duration_seconds = duration_seconds
        self.max_chars_per_line = 60

    def safe_myanmar_split(self, text):
        """Split Myanmar text safely without breaking syllables.
        Checks Unicode range \u102B-\u103E and \u105E-\u105F for medials/vowels/signs."""
        chunks = []
        words = text.split(' ')
        current_chunk = ""
        for word in words:
            if not word:
                continue
            if current_chunk and len(current_chunk) + len(word) + 1 > self.max_chars_per_line:
                chunks.append(current_chunk.strip())
                current_chunk = word + " "
            else:
                current_chunk += word + " "
        while len(current_chunk) > self.max_chars_per_line + 20:
            split_idx = self.max_chars_per_line
            while split_idx < len(current_chunk):
                char = current_chunk[split_idx]
                if '\u102B' <= char <= '\u103E' or '\u105E' <= char <= '\u105F':
                    split_idx += 1
                else:
                    break
            chunks.append(current_chunk[:split_idx].strip())
            current_chunk = current_chunk[split_idx:]
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks

    def generate_subs(self):
        """Generate full SRT text with proportional timestamps."""
        if not self.full_text or self.duration_seconds <= 0:
            return "1\n00:00:00,000 --> 00:00:05,000\n[အသံထွက်နေပါသည်...]\n\n"

        # Split by Myanmar period (။) first
        raw_sentences = [s.strip() + "။" for s in self.full_text.split("။") if s.strip()]
        if not raw_sentences:
            raw_sentences = [self.full_text]

        # Further split long sentences by space within char limit
        final_chunks = []
        for rs in raw_sentences:
            split_parts = self.safe_myanmar_split(rs)
            final_chunks.extend(split_parts)

        total_chars = sum(len(c) for c in final_chunks)
        if total_chars == 0:
            total_chars = 1

        srt_text = ""
        current_time = 0.0
        for i, chunk in enumerate(final_chunks, 1):
            char_ratio = len(chunk) / total_chars
            chunk_duration = self.duration_seconds * char_ratio
            start_time = current_time
            end_time = current_time + chunk_duration
            srt_text += f"{i}\n"
            srt_text += f"{self._format_time(start_time)} --> {self._format_time(end_time)}\n"
            srt_text += f"{chunk}\n\n"
            current_time = end_time
        return srt_text

    def _format_time(self, seconds_float):
        """Format seconds to SRT timestamp HH:MM:SS,mmm."""
        hours = int(seconds_float // 3600)
        minutes = int((seconds_float % 3600) // 60)
        secs = int(seconds_float % 60)
        millis = int(round((seconds_float - int(seconds_float)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def count_paragraphs(text):
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return paragraphs


def make_output_basename(uploaded_name):
    original_name = os.path.splitext(os.path.basename(uploaded_name))[0]
    return f"BE_{original_name[:20].replace(' ', '_')}"


# ─────────────────────────────────────────────
# TTS Generation
# ─────────────────────────────────────────────

async def generate_all_tts(paragraphs, audio_dir, voice_id, speed, pitch):
    """Generate TTS for all paragraphs in parallel."""
    tasks = []
    for i, paragraph in enumerate(paragraphs):
        tasks.append(generate_tts_async(paragraph, os.path.join(audio_dir, f"audio_{i}.mp3"), voice_id, speed, pitch))
    await asyncio.gather(*tasks)


VOICE_MAP = {
    "v1": "my-MM-ThihaNeural",
    "v2": "my-MM-NilarNeural",
    "v3": "it-IT-GiuseppeMultilingualNeural",
    "v4": "en-AU-WilliamMultilingualNeural",
    "v5": "en-US-AndrewMultilingualNeural",
    "v6": "en-US-AvaMultilingualNeural",
    "v7": "en-US-BrianMultilingualNeural",
    "v8": "en-US-EmmaMultilingualNeural",
    "v9": "fr-FR-RemyMultilingualNeural",
    "v10": "fr-FR-VivienneMultilingualNeural",
    "v11": "de-DE-SeraphinaMultilingualNeural",
    "v12": "de-DE-FlorianMultilingualNeural",
    "v13": "pt-BR-ThalitaMultilingualNeural",
    "v14": "ko-KR-HyunsuMultilingualNeural",
    "v15": "en-US-JennyNeural",
    "v16": "en-US-AriaNeural",
    "v17": "en-US-GuyNeural",
    "v18": "en-GB-RyanNeural",
    "v19": "en-GB-SoniaNeural"
}

ENGLISH_VOICE_IDS = {"v4", "v5", "v6", "v7", "v8", "v15", "v16", "v17", "v18", "v19"}
ENGLISH_VOICE_LABELS = {
    "v4": "William (AU)",
    "v5": "Andrew (US)",
    "v6": "Ava (US)",
    "v7": "Brian (US)",
    "v8": "Emma (US)",
    "v15": "Jenny (US)",
    "v16": "Aria (US)",
    "v17": "Guy (US)",
    "v18": "Ryan (GB)",
    "v19": "Sonia (GB)",
}

MYANMAR_VOICE_IDS = {"v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14"}

MYANMAR_VOICE_LABELS = {
    "v1": "V1 ♂ Thiha (MM)",
    "v2": "V2 ♀ Nilar (MM)",
    "v3": "V3 ♂ Giuseppe (IT)",
    "v4": "V4 ♂ William (AU)",
    "v5": "V5 ♂ Andrew (US)",
    "v6": "V6 ♀ Ava (US)",
    "v7": "V7 ♂ Brian (US)",
    "v8": "V8 ♀ Emma (US)",
    "v9": "V9 ♂ Remy (FR)",
    "v10": "V10 ♀ Vivienne (FR)",
    "v11": "V11 ♀ Seraphina (DE)",
    "v12": "V12 ♂ Florian (DE)",
    "v13": "V13 ♀ Thalita (PT-BR)",
    "v14": "V14 ♂ Hyunsu (KO)",
}

ENGLISH_VOICE_LABELS = {
    "v4": "William (AU) ♂",
    "v5": "Andrew (US) ♂",
    "v6": "Ava (US) ♀",
    "v7": "Brian (US) ♂",
    "v8": "Emma (US) ♀",
    "v15": "Jenny (US) ♀",
    "v16": "Aria (US) ♀",
    "v17": "Guy (US) ♂",
    "v18": "Ryan (GB) ♂",
    "v19": "Sonia (GB) ♀",
}

RECAP_STYLE_EN = {
    "ပုံမှန်အသံ": "Normal",
    "ကျားကြီး ၁": "Deep Male 1",
    "ကျားကြီး ၂": "Deep Male 2",
    "ကျားကြီး ၃": "Deep Male 3",
    "နီလာ ချွဲသံ": "Soft Voice",
    "ပေါင်းစပ် ၁၅": "Combo Light",
    "ပေါင်းစပ် ၃၀": "Combo Medium",
    "ပေါင်းစပ် ၅၀": "Combo Strong",
    "အသံသေး ၂၀": "High Pitch Light",
    "အသံသေး ၅၀": "High Pitch Strong",
}

EMOTION_EN = {
    "စိတ်လှုပ်ရှား 🤩": "Exciting 🤩",
    "တည်ငြိမ် 😌": "Calm 😌",
    "သတင်း 💼": "News 💼",
    "ဇာတ်ကြောင်း 📖": "Narrative 📖",
    "ပျော်ရွှင် 😊": "Happy 😊",
    "လေးနက် 😠": "Serious 😠",
    "တီးတိုး 🤫": "Whisper 🤫",
    "ဝမ်းနည်း 😢": "Sad 😢",
    "ရွဲ့ပြော 🙄": "Sarcastic 🙄",
    "ဒေါသထွက် 🤬": "Angry 🤬",
    "ကြောက်လန့် 😨": "Fear 😨",
}

async def generate_tts_async(text, output_path, voice_id, speed, pitch):
    """Async TTS generation for parallel execution."""
    real_voice = VOICE_MAP.get(voice_id, "my-MM-ThihaNeural")
    rate_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
    pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
    communicate = edge_tts.Communicate(text, real_voice, rate=rate_str, pitch=pitch_str)
    await communicate.save(output_path)
    return output_path


# ─────────────────────────────────────────────
# Probe Helpers
# ─────────────────────────────────────────────

def get_video_duration(video_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


def get_video_resolution(video_path):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    res = result.stdout.strip().split('x')
    w, h = int(res[0]), int(res[1])
    return w, h


def get_audio_duration(audio_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


# ─────────────────────────────────────────────
# Step 1: Split video into segments (video only, no audio)
# ─────────────────────────────────────────────

def split_video(video_path, num_segments, output_dir):
    """Split video into segments using fast copy (instant, no re-encoding).
    Audio is stripped to avoid conflicts."""
    duration = get_video_duration(video_path)
    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start_time = i * segment_duration
        output_path = os.path.join(output_dir, f"segment_{i}.mp4")
        cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(segment_duration),
               '-i', video_path, '-c:v', 'copy', '-an',
               '-avoid_negative_ts', 'make_zero', output_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segments.append(output_path)
    return segments, segment_duration


# ─────────────────────────────────────────────
# Step 2: Speed-adjust each segment to match TTS audio
# ─────────────────────────────────────────────

def speed_adjust_segment(index, video_segment, audio_path, adjusted_dir):
    """Speed-adjust VIDEO ONLY to match TTS audio duration.
    TTS audio is kept at original speed (no atempo).
    Returns the path to the adjusted segment (video+audio combined).
    Cleans up the original segment after success."""
    audio_duration = get_audio_duration(audio_path)
    orig_duration = get_video_duration(video_segment)
    output_path = os.path.join(adjusted_dir, f"adjusted_{index}.mp4")

    # Target video duration is rounded up to the nearest 0.5s increment
    # relative to the audio duration (ensuring a buffer of 0 to 0.5s).
    # This prevents audio truncation while keeping the buffer small.
    target_video_duration = math.ceil(audio_duration * 2) / 2
    
    # Ensure the video is at least as long as the audio (handle float precision)
    if target_video_duration < audio_duration:
        target_video_duration = audio_duration
        
    speed_factor = target_video_duration / orig_duration

    # Use a simpler filter complex that only touches video PTS.
    # We map audio directly (1:a) to ensure the TTS audio duration is strictly preserved.
    # We do NOT use -shortest because we want the video to be slightly longer (0-0.5s) than the audio.
    cmd = [
        'ffmpeg', '-y',
        '-i', video_segment,
        '-i', audio_path,
        '-filter_complex', f"[0:v]setpts={speed_factor}*PTS[v]",
        '-map', '[v]',
        '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac',
        output_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0 and os.path.exists(output_path):
        if os.path.exists(video_segment):
            os.remove(video_segment)
        return output_path
    else:
        raise Exception(f"Speed adjust failed for segment {index}: {result.stderr}")


# ─────────────────────────────────────────────
# Step 3: Merge all speed-adjusted segments
# ─────────────────────────────────────────────

def merge_speed_adjusted_segments(adjusted_segments, output_path):
    """Merge all speed-adjusted segments into a single video."""
    concat_file = output_path + "_concat.txt"
    with open(concat_file, 'w') as f:
        for seg in adjusted_segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge speed-adjusted segments failed: {result.stderr}")
    for seg in adjusted_segments:
        if os.path.exists(seg):
            os.remove(seg)



# ─────────────────────────────────────────────
# Step 5: Apply cycle repeat to a single chunk
# ─────────────────────────────────────────────

def build_cycle_filter(video_path, audio_path, chunk_duration,
                       freeze1_dur, freeze2_dur,
                       freeze1_zoom, freeze2_zoom, zoom_dur):
    """Build FFmpeg filter complex for cycle repeat on a chunk."""
    fps = 24
    cycle_duration = freeze1_dur + freeze2_dur
    num_cycles = math.ceil(chunk_duration / cycle_duration)

    # Use original resolution
    width, height = get_video_resolution(video_path)
    res_str = f"{width}x{height}"

    def make_zoom_filter(zoom_dur, total_dur, zoom_type):
        total_frames = max(int(total_dur * fps), 1)
        zoom_frames = max(int(zoom_dur * fps), 1)
        # Cap zoom_frames at total_frames to avoid overflow
        z_frames = min(zoom_frames, total_frames)
        
        if zoom_type == "Zoom In":
            # Zoom from 1.0 to 1.15 over z_frames, then stay at 1.15
            return (f"zoompan=z='if(lte(on,{z_frames}),min(1+0.15*on/{z_frames},1.15),1.15)':"
                    f"d={total_frames}:s={res_str}:fps={fps}")
        elif zoom_type == "Zoom Out":
            # Zoom from 1.15 to 1.0 over z_frames, then stay at 1.0
            return (f"zoompan=z='if(lte(on,{z_frames}),max(1.15-0.15*on/{z_frames},1.0),1.0)':"
                    f"d={total_frames}:s={res_str}:fps={fps}")
        return None

    f1_z = make_zoom_filter(zoom_dur, freeze1_dur, freeze1_zoom) if freeze1_zoom != "None" else None
    f2_z = make_zoom_filter(zoom_dur, freeze2_dur, freeze2_zoom) if freeze2_zoom != "None" else None

    filter_parts = []
    concat_inputs = []

    for i in range(num_cycles):
        curr = i * cycle_duration

        # Play section


        # Freeze 1
        f1_start = curr
        if f1_start < chunk_duration:
            f1_end = min(f1_start + freeze1_dur, chunk_duration)
            f1_actual_dur = f1_end - f1_start
            if f1_actual_dur > 0:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start}:end={f1_end},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(f1_actual_dur * fps)}:size=1:start=0[vf1_{i}];")
                if f1_z:
                    filter_parts.append(f"[vf1_{i}]{f1_z}[vf1z_{i}];")
                    concat_inputs.append(f"[vf1z_{i}]")
                else:
                    concat_inputs.append(f"[vf1_{i}]")

        # Freeze 2
        f2_start = curr + freeze1_dur
        if f2_start < chunk_duration:
            f2_end = min(f2_start + freeze2_dur, chunk_duration)
            f2_actual_dur = f2_end - f2_start
            if f2_actual_dur > 0:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start}:end={f2_end},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(f2_actual_dur * fps)}:size=1:start=0[vf2_{i}];")
                if f2_z:
                    filter_parts.append(f"[vf2_{i}]{f2_z}[vf2z_{i}];")
                    concat_inputs.append(f"[vf2z_{i}]")
                else:
                    concat_inputs.append(f"[vf2_{i}]")

    filter_str = "".join(filter_parts)
    filter_str += "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=1:a=0[vout]"
    
    return filter_str


def process_chunk_with_retry(index, chunk_path, chunk_duration, output_dir,
                            play_dur, freeze1_dur, freeze2_dur,
                            freeze1_zoom, freeze2_zoom, zoom_dur, retries=2):
    """Process a single chunk with FFmpeg filter complex. Retries on failure."""
    output_path = os.path.join(output_dir, f"processed_{index}.mp4")
    filter_str = build_cycle_filter(chunk_path, chunk_path, chunk_duration,
                                    play_dur, freeze1_dur, freeze2_dur,
                                    freeze1_zoom, freeze2_zoom, zoom_dur)
    
    cmd = [
        'ffmpeg', '-y', '-i', chunk_path,
        '-filter_complex', filter_str,
        '-map', '[vout]', '-map', '0:a',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
        '-c:a', 'copy', output_path
    ]

    for attempt in range(retries + 1):
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and os.path.exists(output_path):
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
            return output_path
        time.sleep(1)
    
    raise Exception(f"Chunk {index} failed after {retries} retries: {result.stderr}")


def merge_videos(video_list, output_path):
    valid_videos = [v for v in video_list if v is not None and os.path.exists(v)]
    if not valid_videos:
        raise Exception("No valid segments to merge.")
    concat_file = "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video in valid_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge Error: {result.stderr}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def parse_dubbing_timestamp(value):
    """Parse HH:MM:SS,mmm or HH:MM:SS.mmm into milliseconds."""
    text = str(value).strip().replace(",", ".")
    parts = text.split(":")
    if len(parts) != 3:
        raise ValueError(f"အချိန်မှတ်တမ်း ပုံစံမမှန်ပါ: {value}")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds_parts = parts[2].split(".", 1)
    seconds = int(seconds_parts[0])
    millis = int((seconds_parts[1] if len(seconds_parts) > 1 else "0").ljust(3, "0")[:3])
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"အချိန်မှတ်တမ်းအပိုင်းတန်ဖိုး မမှန်ပါ: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def validate_dubbing_json(payload):
    """Validate the JSON document emitted by Dubbing Script."""
    if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
        raise ValueError("JSON ထဲတွင် segments စာရင်း မပါပါ။")
    segments = []
    warnings = []
    if payload.get("errors"):
        warnings.append("JSON ထဲတွင် မပြီးဆုံးသေးသော အပိုင်း သို့မဟုတ် ဖတ်မရသော အချက်အလက်ရှိသည်။")
    for index, raw in enumerate(payload["segments"], 1):
        if not isinstance(raw, dict):
            raise ValueError(f"segments အမှတ် {index} သည် object မဟုတ်ပါ။")
        text = str(raw.get("text", "")).strip()
        speaker_id = str(raw.get("speaker_id", "unknown")).strip() or "unknown"
        if not text:
            raise ValueError(f"segments အမှတ် {index} တွင် စကားစာသား မပါပါ။")
        try:
            start_ms = parse_dubbing_timestamp(raw.get("start", ""))
            end_ms = parse_dubbing_timestamp(raw.get("end", ""))
        except Exception as exc:
            raise ValueError(f"segments အမှတ် {index}: {exc}") from exc
        if end_ms <= start_ms:
            raise ValueError(f"segments အမှတ် {index} ၏ ပြီးဆုံးချိန်သည် စတင်ချိန်ထက် နောက်ကျရမည်။")
        age_group = str(raw.get("age_group", "unknown")).strip().lower()
        age_group = {"child": "kid", "young": "youth", "young_adult": "youth", "teen": "youth", "teenager": "youth"}.get(age_group, age_group)
        if age_group not in {"kid", "youth", "adult", "unknown"}:
            age_group = "unknown"
        gender = str(raw.get("gender", "unknown")).strip().lower()
        voice_type = str(raw.get("voice_type", "unknown")).strip().lower()
        allowed_voice_types = {"kid_male", "kid_female", "youth_male", "youth_female", "adult_male", "adult_female", "unknown"}
        if voice_type not in allowed_voice_types:
            voice_type = "unknown"
        if voice_type == "unknown":
            if age_group in {"kid", "youth", "adult"} and gender in {"male", "female"}:
                voice_type = f"{age_group}_{gender}"
        segments.append({
            "cue_id": str(raw.get("cue_id", index)),
            "start": str(raw.get("start", "")),
            "end": str(raw.get("end", "")),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "speaker_id": speaker_id,
            "age_group": age_group,
            "gender": gender,
            "voice_type": voice_type,
            "text": text,
        })
    if not segments:
        raise ValueError("JSON အတွင်း အသုံးပြုနိုင်သော ဒပ်လုပ်စာသား မရှိပါ။")
    segments.sort(key=lambda item: (item["start_ms"], item["end_ms"], item["cue_id"]))
    return segments, warnings


VOICE_PITCH_MAP = {
    ("kid", "male"): ("v1", 20),
    ("kid", "female"): ("v2", 20),
    ("youth", "male"): ("v4", 0),
    ("youth", "female"): ("v11", 0),
    ("adult", "male"): ("v3", -10),
    ("adult", "female"): ("v6", -10),
}


def resolve_voice_config(segment):
    """Choose a fixed voice and pitch from JSON age group and gender."""
    age_group = segment.get("age_group", "unknown")
    gender = segment.get("gender", "unknown")
    voice_type = segment.get("voice_type", "unknown")
    if age_group not in {"kid", "youth", "adult"} and voice_type != "unknown":
        parts = voice_type.split("_", 1)
        if len(parts) == 2 and parts[0] in {"kid", "youth", "adult"}:
            age_group = parts[0]
            if gender not in {"male", "female"} and parts[1] in {"male", "female"}:
                gender = parts[1]
    if age_group not in {"kid", "youth", "adult"}:
        age_group = "youth"
    if gender not in {"male", "female"}:
        if voice_type.endswith("_female"):
            gender = "female"
        else:
            gender = "male"
    return VOICE_PITCH_MAP[(age_group, gender)]


def build_speaker_voice_map(segments):
    """Keep one fixed voice/pitch pair per speaker, based on the first cue."""
    speaker_map = {}
    conflicts = set()
    for segment in segments:
        speaker_id = segment["speaker_id"]
        config = resolve_voice_config(segment)
        if speaker_id not in speaker_map:
            speaker_map[speaker_id] = config
        elif speaker_map[speaker_id] != config:
            conflicts.add(speaker_id)
    return speaker_map, sorted(conflicts)


async def generate_dubbing_audio(segments, audio_dir, speaker_voice_map, max_workers=3):
    """Generate each line concurrently with fixed per-speaker voice and pitch."""
    semaphore = asyncio.Semaphore(max(1, int(max_workers)))

    async def generate_one(index, segment):
        voice_id, pitch = speaker_voice_map[segment["speaker_id"]]
        audio_path = os.path.join(audio_dir, f"line_{index:05d}.mp3")
        async with semaphore:
            await generate_tts_async(segment["text"], audio_path, voice_id, 0, pitch)
        return {"segment": segment, "audio_path": audio_path, "voice_id": voice_id, "pitch": pitch}

    return await asyncio.gather(*(generate_one(i, seg) for i, seg in enumerate(segments)))


def create_timed_dubbing_track(generated, video_duration, output_path):
    """Place every generated line at its JSON start time and mix lines only."""
    if not generated:
        raise ValueError("အသံဖန်တီးရန် စာသား မရှိပါ။")
    command = ["ffmpeg", "-y"]
    for item in generated:
        command.extend(["-i", item["audio_path"]])
    filters = []
    labels = []
    for index, item in enumerate(generated):
        delay_ms = int(item["segment"]["start_ms"])
        filters.append(f"[{index}:a]adelay={delay_ms}|{delay_ms}[line{index}]")
        labels.append(f"[line{index}]")
    mix = "".join(labels)
    mix += (
        f"amix=inputs={len(generated)}:duration=longest:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95,apad,atrim=duration={video_duration:.3f}[dubbed]"
    )
    filters.append(mix)
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "[dubbed]",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{video_duration:.3f}", output_path,
    ])
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ဒပ်လုပ်အသံကို ပေါင်းစည်း၍ မရပါ: {result.stderr[-1800:]}")
    return output_path


def mux_dubbing_video(video_path, dubbed_audio_path, output_path, video_duration):
    """Keep original video timing and pixels; omit original audio completely."""
    command = [
        "ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_path,
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "192k", "-t", f"{video_duration:.3f}", "-movflags", "+faststart", output_path,
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ဗီဒီယိုနှင့် ဒပ်လုပ်အသံကို ပေါင်းစည်း၍ မရပါ: {result.stderr[-1800:]}")
    return output_path


def main():
    st.title("🎙️ Dubbing Script")
    st.caption("ဒပ်လုပ် JSON ဖိုင်နှင့် မူရင်းဗီဒီယိုကို ထည့်ပါ။ အချိန်မှတ်တမ်းအတိုင်း အသံကို ဗီဒီယိုနှင့် ကိုက်ညီစေပါမည်။")
    st.info("ဤဗားရှင်းတွင် မူရင်းဗီဒီယိုအသံကို အပြည့်အဝပိတ်ပြီး အသစ်ဖန်တီးထားသော စကားသံကိုသာ ထည့်သွင်းပါမည်။")

    json_file = st.file_uploader("ဒပ်လုပ် JSON ဖိုင်", type=["json"], key="dubbing_json_file")
    video_file = st.file_uploader("မူရင်းဗီဒီယို", type=["mp4", "mov", "avi", "mkv"], key="dubbing_video_file")
    max_workers = 3

    segments = None
    json_warnings = []
    if json_file is not None:
        try:
            payload = json.loads(json_file.getvalue().decode("utf-8-sig"))
            segments, json_warnings = validate_dubbing_json(payload)
            st.success(f"JSON ဖိုင်ကို ဖတ်ပြီးပါပြီ။ စကားပြော {len(segments)} ပိုင်း၊ ဇာတ်ကောင် {len({s['speaker_id'] for s in segments})} ဦး။")
            for warning in json_warnings:
                st.warning(warning)
        except Exception as exc:
            st.error(f"JSON ဖိုင်ကို ဖတ်မရပါ: {exc}")

    speaker_voice_map = {}
    if segments:
        speaker_voice_map, conflicting_speakers = build_speaker_voice_map(segments)
        for speaker_id in conflicting_speakers:
            st.warning(f"{speaker_id} အတွက် အသက်အုပ်စု သို့မဟုတ် ကျား/မ မတူညီနေသည်။ ပထမစာကြောင်း၏ အသံကို အားလုံးအတွက် သုံးမည်။")

        if video_file is not None and st.button("ဒပ်လုပ်ဗီဒီယို ဖန်တီးရန်", type="primary", use_container_width=True):
            work_dir = tempfile.mkdtemp(prefix="be_dubbing_")
            audio_dir = os.path.join(work_dir, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            video_path = os.path.join(work_dir, "source_video" + os.path.splitext(video_file.name)[1])
            output_audio = os.path.join(work_dir, "dubbing_track.m4a")
            output_video = os.path.join(work_dir, "final_dubbing.mp4")
            try:
                with open(video_path, "wb") as target:
                    target.write(video_file.getvalue())
                video_duration = get_video_duration(video_path)
                if video_duration <= 0:
                    raise ValueError("ဗီဒီယိုကြာချိန်ကို ဖတ်မရပါ။")
                outside = [s for s in segments if s["start_ms"] >= int(video_duration * 1000)]
                if outside:
                    raise ValueError(f"{len(outside)} ပိုင်း၏ စတင်ချိန်သည် ဗီဒီယိုအဆုံးထက် နောက်ကျနေသည်။")
                beyond = [s for s in segments if s["end_ms"] > int(video_duration * 1000)]
                if beyond:
                    st.warning(f"{len(beyond)} ပိုင်း၏ ပြီးဆုံးချိန်သည် ဗီဒီယိုအရှည်ထက် ကျော်လွန်နေသည်။ ဗီဒီယိုအဆုံးတွင် အသံဖြတ်မည်။")

                status = st.status("ဒပ်လုပ်အသံ ဖန်တီးနေသည်...", expanded=True)
                status.write(f"စကားပြော {len(segments)} ပိုင်းကို {max_workers} လမ်းဖြင့် တစ်ပြိုင်နက် ဖန်တီးနေသည်။")
                generated = asyncio.run(generate_dubbing_audio(segments, audio_dir, speaker_voice_map, max_workers))
                status.write("ဖန်တီးထားသော အသံများ၏ ကြာချိန်ကို စစ်ဆေးနေသည်။")
                overflows = []
                for item in generated:
                    audio_duration = get_audio_duration(item["audio_path"])
                    slot_duration = (item["segment"]["end_ms"] - item["segment"]["start_ms"]) / 1000
                    if audio_duration > slot_duration + 0.15:
                        overflows.append((item["segment"]["cue_id"], audio_duration, slot_duration))
                if overflows:
                    st.warning(f"{len(overflows)} စာကြောင်း၏ ပြောချိန်သည် သတ်မှတ်ချိန်ထက် ရှည်နေသည်။ စတင်ချိန်ကို ထိန်းထားပြီး စကားအပြည့် ထည့်သွင်းမည်ဖြစ်သောကြောင့် နောက်စာကြောင်းနှင့် ထပ်နိုင်သည်။")
                create_timed_dubbing_track(generated, video_duration, output_audio)
                status.write("JSON ထဲက စတင်ချိန်အတိုင်း အသံများကို နေရာချထားပြီးပါပြီ။")
                mux_dubbing_video(video_path, output_audio, output_video, video_duration)
                with open(output_video, "rb") as source:
                    st.session_state["dubbing_output_bytes"] = source.read()
                st.session_state["dubbing_output_name"] = make_output_basename(video_file.name).replace("BE_", "DUB_") + "_dubbed.mp4"
                st.session_state["dubbing_output_meta"] = {
                    "segments": len(segments),
                    "speakers": len(speaker_voice_map),
                    "duration": video_duration,
                    "overflow_count": len(overflows),
                }
                status.update(label="ဒပ်လုပ်ဗီဒီယို အဆင်သင့်ဖြစ်ပါပြီ", state="complete", expanded=False)
                st.success("မူရင်းဗီဒီယို၏ ရုပ်ပုံနှင့် ကြာချိန်ကို ထိန်းထားပြီး မူရင်းအသံကို အပြည့်အဝ ပိတ်ထားပါသည်။")
            except Exception as exc:
                st.error(f"ဒပ်လုပ်ဗီဒီယို ဖန်တီးရာတွင် အမှားဖြစ်သည်: {exc}")
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

    if st.session_state.get("dubbing_output_bytes"):
        st.subheader("ပြီးစီးသော ဗီဒီယို")
        st.video(st.session_state["dubbing_output_bytes"])
        st.download_button(
            "ဒပ်လုပ်ဗီဒီယိုကို ဒေါင်းလုဒ်ရယူရန်",
            data=st.session_state["dubbing_output_bytes"],
            file_name=st.session_state.get("dubbing_output_name", "dubbing_output.mp4"),
            mime="video/mp4",
            use_container_width=True,
        )
        meta = st.session_state.get("dubbing_output_meta", {})
        st.caption(f"စကားပြောအပိုင်းများ: {meta.get('segments', 0)} · ဇာတ်ကောင်များ: {meta.get('speakers', 0)} · ထပ်နိုင်သော အပိုင်းများ: {meta.get('overflow_count', 0)}")


if __name__ == "__main__":
    main()
