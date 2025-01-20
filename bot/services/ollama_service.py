from ollama import Client as OllamaClient
import logging
from typing import List, Dict
import asyncio
from aiohttp import ClientError

class OllamaService:
    def __init__(self, host: str, model: str, logger: logging.Logger):
        self.client = OllamaClient(host=host)
        self.model = model
        self.logger = logger
        self.max_retries = 3
        self.retry_delay = 1

    async def _make_chat_request(self, messages: List[Dict[str, str]], attempt: int = 0) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages
            )
            return response['message']['content']
        except ClientError as e:
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                return await self._make_chat_request(messages, attempt + 1)
            raise

    async def generate_response(self, speaker_name: str, text: str) -> str:
        try:
            if not text.strip():
                return ""

            messages = [
                {
                    "role": "system", 
                    "content": "Respond like an unhelpful zoomer in tiktok comments."
                },
                {
                    "role": "user", 
                    "content": f"{speaker_name}: {text}"
                }
            ]
            
            response = await self._make_chat_request(messages)
            
            # Format and clean response
            response = response.strip()
            if len(response) > 500:  # Limit response length
                response = response[:497] + "..."
                
            return response
            
        except Exception as e:
            self.logger.error(f"Ollama response generation error: {e}")
            return "Sorry, I couldn't process that request."