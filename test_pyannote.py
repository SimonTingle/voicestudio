import torch
import torchaudio
from pyannote.audio import Pipeline
import numpy as np
import soundfile as sf

# Try to mock the pipeline
class Mock: pass
