import torch
import whisper
from pathlib import Path
import wave
import logging

class AudioService:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model("base").to(self.device)
        
    async def transcribe(self, audio_data: bytes, temp_path: Path) -> str:
        try:
            with wave.open(str(temp_path), 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(audio_data)
            
            result = self.model.transcribe(
                str(temp_path),
                fp16=False if self.device == "cpu" else True
            )
            return result['text'].strip()
        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            raise