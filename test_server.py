import sys, os
sys.path.insert(0, os.path.abspath("backend"))

from backend.main import _get_db, _dub_jobs, dub_transcribe, _find_ffmpeg
import asyncio

async def test():
    print(f"FFmpeg path: {_find_ffmpeg()}")
    try:
        await dub_transcribe("312a7661")
    except Exception as e:
        import traceback
        traceback.print_exc()

import warnings
warnings.filterwarnings("ignore")
asyncio.run(test())
