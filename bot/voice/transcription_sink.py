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
        self.is_speaking = False
        self.was_interrupted = False
        self._current_audio = None
        self.current_bot_message = None
        self._processing_task = None
        self._should_process = True
        self.is_interrupting = False

    @property
    def voice_client(self):
        return self._voice_client

    @voice_client.setter 
    def voice_client(self, vc):
        self._voice_client = vc
        if vc and not self._processing_task:
            self._should_process = True
            self._processing_task = asyncio.create_task(self.start_processing())
            self.logger.info("Started processing task")

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        try:
            if user not in self.audio_buffers:
                self.audio_buffers[user] = {"data": [], "interrupted_message": None}
            
            # Always append the audio data
            self.audio_buffers[user]["data"].append(data.pcm)
            
            # Handle interruption if bot is speaking
            if self.is_speaking and not self.is_interrupting:
                self.logger.info(f"Bot was interrupted by user {user}")
                self.is_interrupting = True
                self.was_interrupted = True
                # Store current message before interruption
                self.audio_buffers[user]["interrupted_message"] = self.current_bot_message
                # Force speaking stop to trigger processing
                asyncio.run_coroutine_threadsafe(
                    self.on_voice_member_speaking_stop(user),
                    self._loop
                )
                # Then handle interruption
                asyncio.run_coroutine_threadsafe(
                    self._handle_interruption(),
                    self._loop
                )
                
        except Exception as e:
            self.logger.error(f"Error in write method: {e}")

    async def _handle_interruption(self):
        """Handle interruption in an async context"""
        try:
            self.logger.info("Starting interruption handling")
            
            if self._voice_client and self._voice_client.is_playing():
                self._voice_client.stop()
            if self._current_audio:
                self._current_audio.cleanup()
                self._current_audio = None
            self.is_speaking = False
            
            # Don't cancel the processing task, just let it continue
            if not self._processing_task or self._processing_task.done():
                self._should_process = True
                self._processing_task = asyncio.create_task(self.start_processing())
                self.logger.info("Created new processing task")
            
            self.logger.info("Handled interruption")

        except Exception as e:
            self.logger.error(f"Error in _handle_interruption: {e}")
        finally:
            self.is_interrupting = False
            self.logger.info("Reset is_interrupting flag after handling interruption")

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member):
        try:
            if member in self.audio_buffers and self.audio_buffers[member]["data"]:
                self.logger.info(f"Processing voice stop for member {member}")
                buffer = self.audio_buffers[member].copy()
                audio_data = b''.join(buffer["data"])
                interrupted_message = buffer["interrupted_message"]
                
                # Clear the buffer after copying data
                self.audio_buffers[member] = {"data": [], "interrupted_message": None}
                
                if audio_data:  # Only process if we have audio data
                    future = asyncio.run_coroutine_threadsafe(
                        self.processing_queue.put((
                            member,
                            audio_data,
                            self.was_interrupted,
                            interrupted_message
                        )),
                        self._loop
                    )
                    future.result()
                    self.logger.info(f"Added audio to processing queue for member {member}")
                    self.was_interrupted = False
        except Exception as e:
            self.logger.error(f"Error in on_voice_member_speaking_stop: {e}")

    async def start_processing(self):
        self.logger.info("Starting processing loop")
        while self._should_process:
            try:
                self.logger.info("Waiting for audio data in processing queue")
                member, audio_data, was_interrupted, interrupted_message = await self.processing_queue.get()
                
                if not self._should_process:  # Check if we should still process
                    break
                    
                self.logger.info(f"Processing audio for member {member}")
                await self.process_audio(
                    member,
                    audio_data,
                    was_interrupted,
                    interrupted_message
                )
                self.processing_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in start_processing: {e}")
                await asyncio.sleep(0.1)

    async def process_audio(self, member, audio_data, was_interrupted: bool, interrupted_message: str):
        temp_wav = self.temp_dir / f"audio_{int(time.time())}_{member.id}.wav"
        try:
            if not self._should_process:  # Check if we should still process
                return
                
            self.logger.info(f"Starting transcription for member {member}")
            transcribed_text = await self.audio_service.transcribe(audio_data, temp_wav)
            
            if transcribed_text and self._should_process:
                self.logger.info(f"Transcribed text: {transcribed_text}")
                response = await self.ollama_service.generate_response(
                    member.name, 
                    transcribed_text,
                    was_interrupted,
                    interrupted_message
                )
                
                if response and self._should_process:
                    self.logger.info("Playing response")
                    await self.play_response(response)
        except Exception as e:
            self.logger.error(f"Error in process_audio: {e}")
        finally:
            try:
                temp_wav.unlink(missing_ok=True)
            except Exception as e:
                self.logger.error(f"Error cleaning up temp file: {e}")
            self.is_interrupting = False  # Ensure this flag is reset
            self.logger.info("Reset is_interrupting flag after processing audio")

    async def play_response(self, text: str):
        try:
            if not self._voice_client or not self._voice_client.is_connected():
                self.logger.error("No voice client available or not connected")
                return

            if not self._should_process:
                return

            self.current_bot_message = text
            self.is_speaking = True
            timestamp = int(time.time())
            response_path = self.responses_dir / f"response_{timestamp}.mp3"
            
            await self.tts_service.generate_audio(text, response_path)
            
            if not response_path.exists():
                self.logger.error("Generated audio file is missing")
                return

            if self._voice_client.is_playing():
                self._voice_client.stop()

            self._current_audio = discord.FFmpegPCMAudio(
                str(response_path),
                options='-filter:a volume=0.5'
            )
            
            self._voice_client.play(
                self._current_audio,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._on_playback_finished(e),
                    self._loop
                ).result()
            )
            
        except Exception as e:
            self.logger.error(f"Error in play_response: {e}")
            self.is_speaking = False

    async def _on_playback_finished(self, error):
        try:
            if error:
                self.logger.error(f"Error during audio playback: {error}")
            self.is_speaking = False
            if self._current_audio:
                self._current_audio.cleanup()
                self._current_audio = None
            self.logger.info("Finished playing response")
        except Exception as e:
            self.logger.error(f"Error in _on_playback_finished: {e}")

    def cleanup(self):
        """Only called when actually disconnecting from voice"""
        try:
            self.logger.info("Starting cleanup")
            self._should_process = False
            
            # Stop current playback if any
            if self._voice_client and self._voice_client.is_playing():
                self._voice_client.stop()
            if self._current_audio:
                self._current_audio.cleanup()
                self._current_audio = None
                
            # Cancel processing task if it exists
            if self._processing_task:
                self._processing_task.cancel()
                
            self.audio_buffers.clear()
            self._voice_client = None
            self.is_speaking = False
            self.was_interrupted = False
            self.is_interrupting = False
            self.logger.info("TranscriptionSink cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")