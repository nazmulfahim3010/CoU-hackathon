import io
import json
import subprocess
import sys
from pathlib import Path
from gtts import gTTS

scenarios_file = Path("backend/app/data/demo/scenarios.json")
scenarios = json.loads(scenarios_file.read_text(encoding="utf-8"))["scenarios"]

audio_dir = Path("demo_assets/audio")
audio_dir.mkdir(parents=True, exist_ok=True)

files = {
    "A_ordinary": "sample_A.wav",
    "B_red_flag": "sample_B.wav",
    "C_uncertain": "sample_C.wav",
}

for sc in scenarios:
    sid = sc["id"]
    fname = files.get(sid)
    target = audio_dir / fname
    if not target.exists():
        print(f"Synthesizing synthetic demo audio for {sid} -> {fname}")
        tts = gTTS(text=sc["original"], lang="bn")
        mp3_buf = io.BytesIO()
        tts.write_to_fp(mp3_buf)
        mp3_data = mp3_buf.getvalue()

        # Convert MP3 to 16kHz mono WAV using ffmpeg
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", "pipe:0", "-ar", "16000", "-ac", "1", str(target)],
            input=mp3_data,
            capture_output=True,
        )
        if proc.returncode == 0:
            print(f"Successfully created {target} ({target.stat().st_size} bytes)")
        else:
            print(f"Error creating WAV: {proc.stderr.decode(errors='ignore')}")
    else:
        print(f"Existing file: {target} ({target.stat().st_size} bytes)")
