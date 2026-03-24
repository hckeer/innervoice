"""
rag/llm_client_async.py

Async LLM client with:
- Connection pooling
- Exponential backoff + jitter
- Timeout handling
- Graceful fallbacks
"""

import os
import asyncio
import random
import logging
from typing import Optional, List, Dict
from groq import AsyncGroq, APIError, RateLimitError, APITimeoutError
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AsyncLLMClient:
    """Async LLM client with robust error handling."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        max_retries: int = 3,
        timeout: float = 30.0
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.client = AsyncGroq(api_key=self.api_key, timeout=self.timeout)
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 200,
    ) -> str:
        """
        Generate response with retry logic and fallback.
        
        Args:
            messages: List of {role, content} dicts
            temperature: Sampling temperature
            max_tokens: Max response tokens
            
        Returns:
            Generated text or fallback message
        """
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                content = response.choices[0].message.content
                if not content or not content.strip():
                    logger.warning("Empty response from LLM")
                    return self._fallback_response()
                
                return content.strip()
                
            except RateLimitError as e:
                wait_time = self._exponential_backoff(attempt)
                logger.warning(f"Rate limit hit (attempt {attempt+1}/{self.max_retries}), waiting {wait_time:.2f}s")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("Rate limit exceeded after retries")
                    return self._fallback_response()
            
            except APITimeoutError as e:
                logger.warning(f"Timeout (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self._exponential_backoff(attempt))
                    continue
                else:
                    logger.error("Timeout after retries")
                    return self._fallback_response()
            
            except APIError as e:
                logger.error(f"API error (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self._exponential_backoff(attempt))
                    continue
                else:
                    return self._fallback_response()
            
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                return self._fallback_response()
        
        return self._fallback_response()
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate backoff time with jitter."""
        base_delay = 2 ** attempt
        jitter = random.uniform(0, 0.3 * base_delay)
        return min(base_delay + jitter, 30.0)  # Cap at 30s
    
    def _fallback_response(self) -> str:
        """Return natural fallback when API fails."""
        fallbacks = [
            "I'm thinking about that... give me a moment?",
            "Hmm, let me gather my thoughts on that.",
            "That's interesting... tell me more about what you mean?",
            "I want to give you a thoughtful response, but I'm having trouble right now. Can you rephrase?",
        ]
        return random.choice(fallbacks)
    
    async def close(self):
        """Close client connections."""
        if hasattr(self.client, 'close'):
            await self.client.close()


# Sync wrapper for backward compatibility
class LLMClient:
    """Synchronous wrapper for AsyncLLMClient."""
    
    def __init__(self, *args, **kwargs):
        self.async_client = AsyncLLMClient(*args, **kwargs)
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Sync generate method."""
        return asyncio.run(self.async_client.generate(messages, **kwargs))
