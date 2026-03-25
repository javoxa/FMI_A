#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

# Añadir la raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from frontend.bot.config import Config
from backend.shared.clients.vlm_client import VLMClient
from backend.orchestrator.orchestrator import Orchestrator
from backend.orchestrator.solvers.analytical import AnalyticalSolver
from backend.orchestrator.solvers.numerical import NumericalSolver
from backend.orchestrator.solvers.symbolic import SymbolicSolver
from backend.shared.clients.llm_client import LLMClient
from frontend.bot.src.handlers.image import ImageHandler


# Configurar logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def start(update, context):
    """Comando /start."""
    await update.message.reply_text(
        "🧮 *Bot YoguIA de Potenciales de Schrödinger*\n\n"
        "¡Hola! Soy tu asistente para problemas de mecánica cuántica.\n\n"
        "📸 *Envía una imagen* de un potencial (barrera, pozo, escalón, etc.) y lo analizaré.\n"
        "✍️ Próximamente también aceptaré ecuaciones LaTeX y consultas en lenguaje natural.",
        parse_mode="MarkdownV2"  # Cambiado a MarkdownV2
    )

def main():
    if not Config.TELEGRAM_TOKEN:
        logger.error("❌ No se encontró TELEGRAM_TOKEN. Revisa el archivo .env")
        return

    # Cliente VLM
    vlm_client = VLMClient(Config.VLM_SERVER_URL, Config.VLM_TIMEOUT)

    # Solver analítico y numérico
    solver_analytical = AnalyticalSolver()
    solver_numerical = NumericalSolver()
    # Cliente LLM (opcional, puede ser None si no se configura)
    llm_client = LLMClient(Config.LLM_SERVER_URL) if getattr(Config, 'LLM_SERVER_URL', None) else None

    # Orquestador
    orchestrator = Orchestrator(
        solver_analytical=solver_analytical,
        solver_numerical=solver_numerical,
        llm_client=llm_client
    )

    # Handler de imágenes
    image_handler = ImageHandler(vlm_client, orchestrator)

    # Crear aplicación
    app = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, image_handler.handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, image_handler.handle_energy_value))

    logger.info("🤖 Bot iniciado. Esperando mensajes...")
    app.run_polling()

if __name__ == "__main__":
    main()
