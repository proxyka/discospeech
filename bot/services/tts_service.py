# https://github.com/elevenlabs/elevenlabs-python

import logging
from pathlib import Path
from elevenlabs import Voice, VoiceSettings, play
from elevenlabs.client import ElevenLabs, AsyncElevenLabs
from bark import SAMPLE_RATE, generate_audio, preload_models
import scipy.io.wavfile
import numpy as np

class TTSService:
    def __init__(self, api_key: str, voice_id: str, logger: logging.Logger, config):
        self.logger = logger
        self.eleven = AsyncElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.tts_service = config.tts_service

    async def generate_audio(self, text: str, output_path: Path) -> Path:
        if self.tts_service == "elevenlabs":
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
        elif self.tts_service == "bark":
            try:
                # Generate audio using Bark
                audio_array = generate_audio(text, history_prompt="v2/en_speaker_6")
                
                # Convert to int16 format
                audio_array = (audio_array * 32767).astype(np.int16)
                
                # Save the audio file
                scipy.io.wavfile.write(output_path, SAMPLE_RATE, audio_array)
                
                return output_path
            except Exception as e:
                self.logger.error(f"Bark TTS error: {str(e)}")
                raise
        else:
            self.logger.error(f"TTS error: No tts service or incorrect tts service defined in config")
            raise