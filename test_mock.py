import sys, types
sys.modules['torchcodec'] = types.ModuleType('torchcodec')
import torchaudio
from transformers import pipeline
print("Loading Whisper...")
pipe = pipeline("automatic-speech-recognition", model="openai/whisper-tiny")
print("Whisper loaded successfully!")
