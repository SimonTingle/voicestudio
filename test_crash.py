import sys, os
sys.path.insert(0, os.path.abspath("backend"))
import asyncio
from backend.main import _get_db, _dub_jobs, dub_transcribe, _find_ffmpeg
import httpx

print(f"FFmpeg path: {_find_ffmpeg()}")
try:
    resp = httpx.post("http://localhost:8000/dub/transcribe/a2ea109c")
    print(f"Status: {resp.status_code}")
    print(resp.text)
except Exception as e:
    print(f"Error calling local server: {e}")
