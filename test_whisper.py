import subprocess
import soundfile as sf
from transformers import pipeline

print("Loading pipeline...")
pipe = pipeline("automatic-speech-recognition", model="openai/whisper-tiny")
print("Pipeline loaded!")
