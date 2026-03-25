import aiohttp
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate(self, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        if not self.base_url:
            logger.warning("LLMClient sin base_url configurada")
            return None
        url = f"{self.base_url}/generate"
        payload = {"prompt": prompt, "max_tokens": max_tokens}
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("text")
                    else:
                        logger.error(f"LLM error {resp.status}: {await resp.text()}")
                        return None
        except Exception as e:
            logger.exception("LLM request failed")
            return None
