 
#!/usr/bin/env python3
"""
Servidor de inferencia para Idefics2-8B fine-tuneado (VLM)
Con control de concurrencia, backpressure y soporte multimodal
"""
import os
import logging
import asyncio
import time
import base64
import json
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Optional

import torch
from PIL import Image
from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import (
    AutoProcessor,
    Idefics2ForConditionalGeneration,
    BitsAndBytesConfig
)
from peft import PeftModel
import uvicorn

# =====================================================
# CONFIGURACIÓN (variables de entorno)
# =====================================================
MODEL_ID = os.getenv("MODEL_ID", "HuggingFaceM4/idefics2-8b")
ADAPTER_PATH = os.getenv("ADAPTER_PATH", "idefics2-bot-institucional-finetune/checkpoints/finetune_step_300")
DEVICE = os.getenv("DEVICE", "cuda:0")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8001))  # Puerto diferente al servidor LLM
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 4))  # Modelo grande, pocos concurrentes
QUEUE_TIMEOUT = float(os.getenv("QUEUE_TIMEOUT", 30.0))
MODEL_TIMEOUT = float(os.getenv("MODEL_TIMEOUT", 120.0))  # Más tiempo para VLM
KEEP_ALIVE_TIMEOUT = int(os.getenv("KEEP_ALIVE_TIMEOUT", 120))
MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", 1024 * 1024 * 10))  # 10 MB

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("vlm-server")

# =====================================================
# CONTROL DE CONCURRENCIA
# =====================================================
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
request_queue = asyncio.Queue(maxsize=MAX_CONCURRENT_REQUESTS * 2)

# =====================================================
# LIFESPAN: CARGA DEL MODELO
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Inicializando Idefics2-8B con fine-tuning...")

    # 1. Configuración de cuantización 4-bit (igual que en entrenamiento)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    # 2. Cargar procesador y modelo base
    app.state.processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        do_image_splitting=False  # Importante: igual que en entrenamiento
    )
    base_model = Idefics2ForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=torch.bfloat16
    )

    # 3. Cargar adaptador LoRA
    app.state.model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    app.state.model.eval()
    logger.info("✅ Modelo listo.")

    yield

    # Liberar recursos (opcional)
    del app.state.model
    del app.state.processor
    torch.cuda.empty_cache()
    logger.info("🛑 Recursos liberados.")

# =====================================================
# APP FASTAPI
# =====================================================
app = FastAPI(
    title="VLM Server - Idefics2 (Potenciales Schrödinger)",
    version="1.0",
    lifespan=lifespan
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# =====================================================
# MODELOS DE DATOS
# =====================================================
class AnalyzeRequest(BaseModel):
    image_base64: str
    user_id: str = "anonymous"
    max_new_tokens: int = 512
    temperature: Optional[float] = None  # None = determinista (do_sample=False)

class AnalyzeResponse(BaseModel):
    json_output: str  # El JSON generado como string
    processing_time: float
    model: str = MODEL_ID

# =====================================================
# MIDDLEWARE DE CONTROL DE CARGA
# =====================================================
@app.middleware("http")
async def load_control_middleware(request: Request, call_next):
    """Control de carga y backpressure real (igual que en servidor vLLM)"""
    if request_queue.qsize() >= request_queue.maxsize:
        logger.warning(f"🚨 Cola llena ({request_queue.qsize()}/{request_queue.maxsize}). Rechazando solicitud.")
        return JSONResponse(
            status_code=503,
            content={"error": "Servicio temporalmente saturado. Intenta nuevamente en unos minutos."}
        )

    start_time = time.time()
    try:
        task = asyncio.current_task()
        await asyncio.wait_for(request_queue.put(task), QUEUE_TIMEOUT)

        acquired = await asyncio.wait_for(semaphore.acquire(), QUEUE_TIMEOUT)
        if not acquired:
            raise asyncio.TimeoutError("Timeout adquiriendo recurso")

        try:
            response = await call_next(request)
        finally:
            semaphore.release()
            if not request_queue.empty():
                request_queue.get_nowait()
                request_queue.task_done()

        return response

    except asyncio.TimeoutError:
        logger.error("⏰ Timeout en cola de espera")
        return JSONResponse(
            status_code=504,
            content={"error": "Tiempo de espera excedido. Intenta nuevamente."}
        )
    except Exception as e:
        logger.error(f"❌ Error en middleware: {e}")
        raise

# =====================================================
# ENDPOINT PRINCIPAL: ANALIZAR IMAGEN
# =====================================================
@app.post("/vlm/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Recibe imagen en base64 y devuelve la descripción geométrica del potencial"""
    start_time = time.time()

    # Validar tamaño de imagen (aproximado)
    if len(request.image_base64) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Imagen demasiado grande (max 10MB)")

    try:
        # Decodificar imagen base64 a PIL
        image_bytes = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        # Redimensionar como en entrenamiento (448x448)
        image = image.resize((448, 448))
        logger.info(f"📸 Imagen recibida de usuario {request.user_id}, tamaño {image.size}")

    except Exception as e:
        logger.error(f"Error decodificando imagen: {e}")
        raise HTTPException(status_code=400, detail="Imagen inválida o corrupta")

    # Prompt exacto usado en entrenamiento
    prompt_text = (
        "Extract the spatial structure of the potential. Identify all labeled points on the x-axis (like a, b, ...) "
        "and on the y-axis (like V0, 0, ...). Then divide the x-axis into segments between these points (including -inf and inf). "
        "For each segment, report its boundaries, the potential value label, and for each energy level (E1, E2, ...) whether it is "
        "greater than (>), less than (<), or equal to the potential in that segment. Also indicate the wave if present: its incident "
        "segment and direction (L->R or R->L)."
    )

    messages = [
        {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}
    ]

    # Aplicar template de chat (igual que en entrenamiento)
    text = app.state.processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = app.state.processor(text=text, images=[image], return_tensors="pt").to(DEVICE)

    # Configurar parámetros de generación
    if request.temperature is not None:
        do_sample = True
        temperature = request.temperature
    else:
        do_sample = False
        temperature = None

    try:
        async def generate():
            # Ejecutar model.generate en un hilo separado para no bloquear el event loop
            loop = asyncio.get_event_loop()
            generated_ids = await loop.run_in_executor(
                None,
                lambda: app.state.model.generate(
                    **inputs,
                    max_new_tokens=request.max_new_tokens,
                    do_sample=do_sample,
                    temperature=temperature,
                    top_p=None if not do_sample else 0.9,  # Valor por defecto si muestreo
                )
            )
            return generated_ids

        # Aplicar timeout global
        generated_ids = await asyncio.wait_for(generate(), MODEL_TIMEOUT)

    except asyncio.TimeoutError:
        logger.error(f"⏰ Timeout en generación para usuario {request.user_id}")
        raise HTTPException(status_code=504, detail="Tiempo de generación excedido")
    except Exception as e:
        logger.error(f"❌ Error en generación: {e}")
        raise HTTPException(status_code=500, detail=f"Error en inferencia: {str(e)}")

    # Decodificar
    output = app.state.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # Extraer respuesta del asistente (después de "Assistant:")
    if "Assistant:" in output:
        output = output.split("Assistant:")[-1].strip()

    # Intentar extraer JSON válido
    json_output = None
    try:
        start = output.find('{')
        end = output.rfind('}') + 1
        if start != -1 and end > start:
            json_str = output[start:end]
            # Validar que sea JSON
            json.loads(json_str)
            json_output = json_str
        else:
            logger.warning(f"No se encontró JSON en la respuesta para usuario {request.user_id}")
            json_output = output  # Devolvemos el texto completo como fallback
    except json.JSONDecodeError:
        logger.warning(f"JSON inválido en respuesta para usuario {request.user_id}")
        json_output = output

    processing_time = time.time() - start_time
    logger.info(f"✅ Usuario {request.user_id} procesado en {processing_time:.2f}s")

    return AnalyzeResponse(
        json_output=json_output,
        processing_time=processing_time
    )

# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/health")
async def health_check():
    queue_load = request_queue.qsize() / request_queue.maxsize * 100 if request_queue.maxsize > 0 else 0
    semaphore_load = (MAX_CONCURRENT_REQUESTS - semaphore._value) / MAX_CONCURRENT_REQUESTS * 100

    status = "healthy" if queue_load < 80 and semaphore_load < 90 else "degraded"

    return {
        "status": status,
        "model": MODEL_ID,
        "adapter": ADAPTER_PATH,
        "queue_size": request_queue.qsize(),
        "queue_max": request_queue.maxsize,
        "queue_load_percent": round(queue_load, 1),
        "concurrent_requests": MAX_CONCURRENT_REQUESTS - semaphore._value,
        "max_concurrent": MAX_CONCURRENT_REQUESTS,
        "semaphore_load_percent": round(semaphore_load, 1),
        "device": DEVICE,
        "timestamp": time.time()
    }

# =====================================================
# ENDPOINT PARA SUBIDA DIRECTA DE ARCHIVO (opcional)
# =====================================================
@app.post("/vlm/analyze/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    max_new_tokens: int = Form(512),
    temperature: Optional[float] = Form(None)
):
    """Alternativa que recibe la imagen como multipart/form-data"""
    try:
        contents = await file.read()
        image_base64 = base64.b64encode(contents).decode("utf-8")
        # Reutilizar el mismo endpoint
        req = AnalyzeRequest(
            image_base64=image_base64,
            user_id=user_id,
            max_new_tokens=max_new_tokens,
            temperature=temperature
        )
        return await analyze(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando archivo: {e}")

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    logger.info(f"🔧 Configuración: MAX_CONCURRENT_REQUESTS={MAX_CONCURRENT_REQUESTS}, MODEL_ID={MODEL_ID}")
    logger.info(f"🔌 Iniciando servidor en {HOST}:{PORT}")
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        timeout_keep_alive=KEEP_ALIVE_TIMEOUT,
        workers=1  # Siempre 1 worker con modelos de GPU
    )
