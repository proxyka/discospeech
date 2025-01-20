import json
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    discord_token: str
    elevenlabs_api_key: str
    voice_id: str
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    temp_dir: Path = Path(__file__).parent.parent / 'temp'
    responses_dir: Path = Path(__file__).parent.parent / 'responses'
    cleanup_responses: bool = False
    tts_service: str = "bark"

    @classmethod
    def load(cls, path: str) -> 'Config':
        with open(path) as f:
            data = json.load(f)
        return cls(**data)