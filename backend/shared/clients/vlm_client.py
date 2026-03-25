import aiohttp
import asyncio
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class VLMClient:
    """Cliente asíncrono para el servidor VLM."""

    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def analyze_potential(self, image_b64: str, user_id: str):
        # 🟢 Endpoint correcto
        url = f"{self.base_url}/vlm/analyze"

        # 🟢 Campos correctos según AnalyzeRequest
        payload = {
            "image_base64": image_b64,
            "user_id": user_id
        }

        for retry in range(8):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(url, json=payload) as response:

                        if response.status == 200:
                            data = await response.json()

                            # El servidor devuelve {"json_output": "..."}
                            if "json_output" in data:
                                try:
                                    return json.loads(data["json_output"])
                                except json.JSONDecodeError:
                                    logger.warning("El VLM devolvió texto no JSON, se envuelve en 'raw'")
                                    return {"raw": data["json_output"]}

                            return data

                        else:
                            logger.error(f"VLM error {response.status}: {await response.text()}")
                            return None

            except Exception:
                logger.warning(f"VLM no disponible. Reintentando {retry+1}/8...")
                await asyncio.sleep(5)

        logger.error("No se pudo conectar al VLM después de múltiples intentos.")
        return None
