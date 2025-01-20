import elevenlabs
import logging
from pathlib import Path

class TTSService:
    def __init__(self, api_key: str, voice_id: str, logger: logging.Logger):
        self.logger = logger
        elevenlabs.set_api_key(api_key)
        self.voice = elevenlabs.Voice(voice_id=voice_id)

    async def generate_audio(self, text: str, output_path: Path) -> Path:
        try:
            audio = elevenlabs.generate(
                text=text,
                voice=self.voice,
                stream=True
            )
            
            with open(output_path, 'wb') as f:
                for chunk in audio:
                    f.write(chunk)
            return output_path
        except Exception as e:
            self.logger.error(f"TTS error: {e}")
            raise