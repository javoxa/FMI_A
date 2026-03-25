 #!/usr/bin/env python3
"""
Script de ejecución unificado para el bot de Schrödinger.
Permite ejecutar el bot con diferentes modos y configuraciones.
"""

import os
import sys
import argparse
import logging
import asyncio
from pathlib import Path
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# Añadir el directorio raíz al PYTHONPATH
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Carga variables de entorno desde .env si existe"""
    try:
        from dotenv import load_dotenv
        env_path = ROOT_DIR / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Variables de entorno cargadas desde {env_path}")
        else:
            logger.warning("⚠️  Archivo .env no encontrado. Usando variables del sistema.")
    except ImportError:
        logger.warning("⚠️  python-dotenv no instalado. Las variables de entorno deben estar definidas.")

def run_bot():
    """Ejecuta el bot de Telegram"""
    try:
        from frontend.bot.main import main as bot_main
        logger.info("🚀 Iniciando bot de Telegram...")
        bot_main()
    except ImportError as e:
        logger.error(f"❌ Error importando el bot: {e}")
        logger.error("Asegúrate de que la estructura de directorios es correcta y que las dependencias están instaladas.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error ejecutando el bot: {e}")
        sys.exit(1)

def run_vlm_server():
    """Ejecuta el servidor VLM directamente (para pruebas)"""
    try:
        from backend.vlm.src.vlm_server import app
        import uvicorn

        host = os.getenv("VLM_HOST", "0.0.0.0")
        port = int(os.getenv("VLM_PORT", "8001"))

        logger.info(f"🚀 Iniciando servidor VLM en {host}:{port}...")
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError as e:
        logger.error(f"❌ Error importando el servidor VLM: {e}")
        sys.exit(1)

def run_llm_server():
    """Ejecuta el servidor LLM (cuando esté implementado)"""
    logger.info("🔄 Servidor LLM aún no implementado")
    # from backend.llm.src.inference_server import app
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8002)

def run_all_servers():
    """Ejecuta todos los servidores (para desarrollo)"""
    import multiprocessing
    import time

    def run_vlm():
        run_vlm_server()

    def run_llm():
        run_llm_server()

    def run_bot_process():
        # Esperar un poco a que los servidores inicien
        time.sleep(5)
        run_bot()

    processes = []

    # VLM server
    p_vlm = multiprocessing.Process(target=run_vlm, name="VLM-Server")
    p_vlm.start()
    processes.append(p_vlm)
    logger.info("✅ Proceso VLM iniciado")

    # LLM server (comentado hasta que exista)
    # p_llm = multiprocessing.Process(target=run_llm, name="LLM-Server")
    # p_llm.start()
    # processes.append(p_llm)
    # logger.info("✅ Proceso LLM iniciado")

    # Bot
    p_bot = multiprocessing.Process(target=run_bot_process, name="Telegram-Bot")
    p_bot.start()
    processes.append(p_bot)
    logger.info("✅ Proceso Bot iniciado")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("🛑 Recibida señal de interrupción. Deteniendo procesos...")
        for p in processes:
            p.terminate()
            p.join()

def check_dependencies():
    """Verifica que las dependencias principales estén instaladas"""
    try:
        import telegram
        import aiohttp
        import dotenv
        logger.info("✅ Dependencias principales OK")
    except ImportError as e:
        logger.error(f"❌ Falta dependencia: {e}")
        logger.info("Ejecuta: pip install -r frontend/requirements.txt")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta el bot de Schrödinger y sus componentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python run.py bot              # Ejecuta solo el bot
  python run.py vlm               # Ejecuta solo el servidor VLM
  python run.py all                # Ejecuta bot + VLM (útil para desarrollo)
  python run.py bot --env prod     # Carga .env.prod en lugar de .env
        """
    )

    parser.add_argument(
        "component",
        choices=["bot", "vlm", "llm", "all"],
        help="Componente a ejecutar"
    )

    parser.add_argument(
        "--env",
        default=".env",
        help="Archivo de entorno a cargar (por defecto .env)"
    )

    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Saltar verificación de dependencias"
    )

    args = parser.parse_args()

    # Cargar variables de entorno
    if args.env:
        env_file = ROOT_DIR / args.env
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            logger.info(f"✅ Usando archivo de entorno: {env_file}")

    # Verificar dependencias (opcional)
    if not args.skip_checks:
        if not check_dependencies():
            sys.exit(1)

    # Ejecutar componente solicitado
    if args.component == "bot":
        run_bot()
    elif args.component == "vlm":
        run_vlm_server()
    elif args.component == "llm":
        run_llm_server()
    elif args.component == "all":
        run_all_servers()

if __name__ == "__main__":
    main()
