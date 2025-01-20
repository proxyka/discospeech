import discord
from discord.ext import commands, voice_recv
from .services import AudioService, TTSService, OllamaService
from .voice import TranscriptionSink
import logging
import asyncio
import sys

class DiscordBot(commands.Bot):
    def __init__(self, config, logger: logging.Logger):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        
        self.config = config
        self.logger = logger
        
        # Ensure correct event loop policy for Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        self.audio_service = AudioService(logger)
        self.tts_service = TTSService(
            config.elevenlabs_api_key,
            config.voice_id,
            logger
        )
        self.ollama_service = OllamaService(
            config.ollama_host,
            config.ollama_model,
            logger
        )
        
        # Create directories
        config.temp_dir.mkdir(exist_ok=True)
        config.responses_dir.mkdir(exist_ok=True)
        
        # Setup events and commands
        self.setup_events()
        self.setup_commands()

    def setup_events(self):
        @self.event
        async def on_ready():
            self.logger.info(f'Bot logged in as {self.user.name}')

    def setup_commands(self):
        @self.command()
        async def join(ctx):
            if not ctx.author.voice:
                await ctx.send("You must be in a voice channel!")
                return
                    
            try:
                vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
                sink = TranscriptionSink(
                    self.audio_service,
                    self.tts_service,
                    self.ollama_service,
                    self.config.temp_dir,
                    self.logger,
                    self.config
                )
                sink.voice_client = vc  # This will start the processing task
                vc.listen(sink)
                await ctx.send("Joined and listening!")
            except Exception as e:
                self.logger.error(f"Error joining channel: {e}")
                await ctx.send(f"Error: {e}")

        @self.command()
        async def leave(ctx):
            if ctx.voice_client:
                ctx.voice_client.stop()
                await ctx.voice_client.disconnect()
                await ctx.send("Left voice channel!")

    def run(self):
        try:
            super().run(self.config.discord_token)
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            raise