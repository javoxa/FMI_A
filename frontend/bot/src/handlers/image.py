import logging
from telegram import Update
from telegram.ext import ContextTypes

from frontend.bot.config import Config
from frontend.bot.src.utils import image_to_base64, validate_image_size
from backend.shared.clients.vlm_client import VLMClient
from backend.shared.parsers.vlm_parser import vlm_json_to_ir
from backend.shared.parsers.normalizer import normalize_ir
from backend.orchestrator.orchestrator import Orchestrator
from frontend.bot.src.formatters import format_full_response

logger = logging.getLogger(__name__)

class ImageHandler:
    def __init__(self, vlm_client: VLMClient, orchestrator: Orchestrator):
        self.vlm_client = vlm_client
        self.orchestrator = orchestrator
        self.user_context = {}

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        logger.info(f"📸 Foto recibida de usuario {user_id}")

        photo = update.message.photo[-1]
        file = await photo.get_file()
        if not validate_image_size(file.file_size, Config.MAX_IMAGE_SIZE_MB):
            await update.message.reply_text(f"❌ Imagen demasiado grande. Máx {Config.MAX_IMAGE_SIZE_MB} MB")
            return

        image_bytes = await file.download_as_bytearray()
        image_base64 = image_to_base64(image_bytes)

        msg = await update.message.reply_text("🔍 Analizando el potencial...")

        try:
            vlm_result = await self.vlm_client.analyze_potential(image_base64, str(user_id))
            if not vlm_result:
                await msg.edit_text("❌ No se pudo analizar la imagen.")
                return

            ir_dict = vlm_json_to_ir(vlm_result)
            ir = normalize_ir(ir_dict)

            solution = await self.orchestrator.solve(ir)

            if solution.get("status") == "missing_energy":
                self.user_context[user_id] = {"ir": ir}
                # ✅ Quitamos backticks en el mensaje
                await msg.edit_text(
                    f"🔢 Falta valor numérico de energía.\n"
                    f"Energías disponibles: {', '.join(solution['available_energies'])}.\n"
                    f"Por favor, envía un número (ej. 5.0) o E1 = 5.0."
                )
                return

            formatted = format_full_response(ir, solution)
            await msg.edit_text(formatted, parse_mode="MarkdownV2")

        except Exception as e:
            logger.exception("Error en handler")
            await msg.edit_text(f"❌ Error: {str(e)[:200]}")

    async def handle_energy_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()

        if user_id not in self.user_context:
            await update.message.reply_text("No hay consulta pendiente. Envía una imagen primero.")
            return

        try:
            if "=" in text:
                _, value_str = text.split("=", 1)
                energy = float(value_str.strip())
            else:
                energy = float(text)
        except Exception:
            # ✅ Quitamos backticks
            await update.message.reply_text("❌ Formato inválido. Envía un número (ej. 5.0) o E1 = 5.0.")
            return

        ir = self.user_context[user_id]["ir"]
        solution = await self.orchestrator.solve_with_energy(ir, energy)

        formatted = format_full_response(ir, solution)
        await update.message.reply_text(formatted, parse_mode="MarkdownV2")

        del self.user_context[user_id]
