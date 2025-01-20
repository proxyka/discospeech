import asyncio
import sys
from bot.bot import DiscordBot
from bot.config import Config
from bot.logger import setup_logger

def setup_event_loop():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def main():
    setup_event_loop()
    logger = setup_logger()
    config = Config.load('config.json')
    bot = DiscordBot(config, logger)
    bot.run()

if __name__ == "__main__":
    main()