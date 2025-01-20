import json
from discord.ext import voice_recv
import asyncio
import logging
from ..services import AudioService, TTSService, OllamaService
from pathlib import Path
import time
import discord

class TranscriptionSink(voice_recv.AudioSink):
    def __init__(self, 
                 audio_service: AudioService, 
                 tts_service: TTSService,
                 ollama_service: OllamaService,
                 temp_dir: Path, 
                 logger: logging.Logger,
                 config):
        super().__init__()
        self.audio_service = audio_service
        self.tts_service = tts_service
        self.ollama_service = ollama_service
        self.temp_dir = temp_dir
        self.responses_dir = temp_dir.parent / 'responses'
        self.responses_dir.mkdir(exist_ok=True)
        self.logger = logger
        self.audio_buffers = {}
        self.processing_queue = asyncio.Queue()
        self._voice_client = None
        self._loop = asyncio.get_event_loop()
        self.config = config

    @property
    def voice_client(self):
        return self._voice_client

    @voice_client.setter 
    def voice_client(self, vc):
        self._voice_client = vc

    def wants_opus(self) -> bool:
        return False
        
    def cleanup(self):
        self.audio_buffers.clear()
        self._voice_client = None
        self.logger.info("TranscriptionSink cleanup complete")

    def write(self, user, data):
        if user not in self.audio_buffers:
            self.audio_buffers[user] = []
        self.audio_buffers[user].append(data.pcm)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member):
        if member in self.audio_buffers:
            audio_data = b''.join(self.audio_buffers[member])
            self.audio_buffers[member] = []
            asyncio.run_coroutine_threadsafe(
                self.processing_queue.put((member, audio_data)),
                self._loop
            )

    async def start_processing(self):
        while True:
            try:
                member, audio_data = await self.processing_queue.get()
                await self.process_audio(member, audio_data)
                self.processing_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing audio queue: {e}")

    async def process_audio(self, member, audio_data):
        temp_wav = self.temp_dir / f"audio_{int(time.time())}_{member.id}.wav"
        try:
            transcribed_text = await self.audio_service.transcribe(audio_data, temp_wav)
            if transcribed_text:
                response = await self.ollama_service.generate_response(member.name, transcribed_text)
                if response:
                    await self.play_response(response)
        finally:
            try:
                temp_wav.unlink(missing_ok=True)
            except Exception as e:
                self.logger.error(f"Error cleaning up temp file: {e}")

    async def play_response(self, text: str):
        if not self._voice_client or not self._voice_client.is_connected():
            self.logger.error("Voice client not connected - cannot play response")
            return

        try:
            # Generate unique filename
            timestamp = int(time.time())
            response_path = self.responses_dir / f"response_{timestamp}.mp3"
            
            # Generate audio file
            await self.tts_service.generate_audio(text, response_path)
            
            # Verify file exists and has content
            if not response_path.exists() or response_path.stat().st_size == 0:
                self.logger.error("Generated audio file is empty or missing")
                return
                
            # Wait for any existing audio to finish
            while self._voice_client.is_playing():
                await asyncio.sleep(0.1)
                
            # Play audio
            audio_source = discord.FFmpegPCMAudio(
                str(response_path),
                options='-filter:a volume=0.8'
            )
            self._voice_client.play(
                audio_source, 
                after=lambda e: self.logger.error(f"Error playing audio: {e}") if e else None
            )
            self.logger.info(f"Playing response through voice client at 80% volume")
            
            # Wait for audio to finish before cleanup
            while self._voice_client.is_playing():
                await asyncio.sleep(0.1)
                
            # Cleanup file after playing
            try:
                # Unlink file if cleanup_responses is true
                if self.config.get('cleanup_responses', False):
                    response_path.unlink(missing_ok=True)
            except Exception as e:
                self.logger.error(f"Error cleaning up response file: {e}")
                
        except Exception as e:
            self.logger.error(f"Error playing response: {e}")