import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

def setup_logger(
    log_dir: str = 'logs',
    log_file: str = 'bot.log',
    max_bytes: int = 10*1024*1024,  # 10MB
    backup_count: int = 5,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """Configure and return a logger with both file and console handlers."""
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Set up file handler with rotation
    file_handler = RotatingFileHandler(
        log_path / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(file_level)

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(console_level)

    # Set up root logger
    logger = logging.getLogger('discord_bot')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger