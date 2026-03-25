import base64
import json
import logging
from typing import Union, Dict, Any

logger = logging.getLogger(__name__)

def image_to_base64(image_bytes: bytes) -> str:
    """Convierte bytes de imagen a string base64."""
    return base64.b64encode(image_bytes).decode('utf-8')

def validate_image_size(file_size: int, max_mb: int) -> bool:
    """Verifica que el tamaño del archivo no exceda el límite en MB."""
    return file_size <= max_mb * 1024 * 1024

def format_vlm_response(data: Union[Dict[str, Any], str]) -> str:
    """
    Convierte la respuesta del VLM en un mensaje legible para Telegram.
    Si data es un string, se muestra tal cual.
    Si es un diccionario, se formatea según la estructura esperada.
    """
    if isinstance(data, str):
        return f"📄 Análisis del potencial:\n\n{data}"

    # Caso especial cuando el VLM devolvió texto no JSON
    if isinstance(data, dict) and "raw" in data:
        return f"📄 Respuesta del VLM (texto):\n\n{data['raw']}"

    lines = []
    try:
        # Nodos (puntos clave)
        nodes = data.get('nodes', {})
        x_axis = nodes.get('x_axis', [])
        potentials = nodes.get('potentials', [])
        if x_axis:
            lines.append("📍 *Posiciones en x*: " + ', '.join(x_axis))
        if potentials:
            lines.append("⚡ *Valores de potencial*: " + ', '.join(potentials))

        # Segmentos
        segments = data.get('segments', [])
        if segments:
            lines.append("\n📐 *Segmentos del potencial:*")
            for i, seg in enumerate(segments, 1):
                bounds = seg.get('boundary', ['?', '?'])
                v_local = seg.get('V_local', '?')
                relations = seg.get('relations', {})
                rel_str = ', '.join([f"{k}{v}" for k, v in relations.items()])
                lines.append(f"  {i}. [{bounds[0]}, {bounds[1]}]  V={v_local}  → {rel_str}")

        # Onda piloto
        wave = data.get('wave', {})
        if wave.get('present'):
            lines.append("\n🌊 *Onda piloto:* Presente")
            lines.append(f"   - Segmento incidente: {wave.get('incident_segment', '?')}")
            lines.append(f"   - Dirección: {wave.get('direction', '?')}")
            lines.append(f"   - Energía: {wave.get('energy', '?')}")
        else:
            lines.append("\n🌊 *Onda piloto:* No presente")

        return "\n".join(lines) if lines else "✅ Análisis completado (sin detalles)."

    except Exception as e:
        logger.error(f"Error formateando respuesta VLM: {e}")
        return f"*Respuesta del VLM (sin formato):*\n```json\n{json.dumps(data, indent=2)}\n```"
