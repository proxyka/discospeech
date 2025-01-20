# https://github.com/elevenlabs/elevenlabs-python

import logging
from pathlib import Path
from elevenlabs import Voice, VoiceSettings, play
from elevenlabs.client import ElevenLabs, AsyncElevenLabs

class TTSService:
    def __init__(self, api_key: str, voice_id: str, logger: logging.Logger):
        self.logger = logger
        self.eleven = AsyncElevenLabs(api_key=api_key)
        self.voice_id = voice_id

    async def generate_audio(self, text: str, output_path: Path) -> Path:
        try:
            audio_stream = await self.eleven.generate(
                text=text,
                voice=Voice(
                    voice_id=self.voice_id,
                    settings=VoiceSettings(stability=0.71, similarity_boost=0.5, style=0.0, use_speaker_boost=False)
                ),
                model="eleven_flash_v2", # https://elevenlabs.io/docs/developer-guides/models
                stream=True,
            )
            
            with open(output_path, 'wb') as f:
                async for chunk in audio_stream:
                    f.write(chunk)
            return output_path
        except Exception as e:
            self.logger.error(f"TTS error: {e}")
            raise