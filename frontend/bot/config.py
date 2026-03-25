import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    VLM_SERVER_URL = os.getenv("VLM_SERVER_URL", "http://vlm:8001")
    VLM_TIMEOUT = int(os.getenv("VLM_TIMEOUT", 120))
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", 10))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", "")  # opcional, puede estar vacío
