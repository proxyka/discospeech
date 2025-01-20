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
        self.conversation_history = []
        self.max_history = 60  # Keep last 60 exchanges

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

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []

    async def generate_response(self, speaker_name: str, text: str) -> str:
        try:
            if not text.strip():
                return ""

            # Base system and current message
            messages = [
                {
                    "role": "system", 
                    "content": "You are an AI in a voice chat. Respond naturally and casualy like you would speak with a bunch of friend(s)."
                }
            ]
            
            # Add conversation history
            messages.extend(self.conversation_history)
            
            # Add current message
            user_message = {
                "role": "user", 
                "content": f"{speaker_name}: {text}"
            }
            messages.append(user_message)
            
            # Generate response
            response = await self._make_chat_request(messages)
            response = response.strip()
            
            # Limit response length
            if len(response) > 500:
                response = response[:497] + "..."
            
            # Update history
            self.conversation_history.append(user_message)
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Maintain history size
            if len(self.conversation_history) > self.max_history * 2:  # *2 because each exchange has 2 messages
                self.conversation_history = self.conversation_history[-self.max_history * 2:]
                
            return response
            
        except Exception as e:
            self.logger.error(f"Ollama response generation error: {e}")
            return "Sorry, I couldn't process that request."