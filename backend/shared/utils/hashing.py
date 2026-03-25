import hashlib
import json
from typing import Dict, Any
from ..models.ir import IR


def hash_ir(ir: IR) -> str:
    """Genera un hash SHA256 del IR para cache y deduplicación"""
    # Convertir a diccionario con ordenamiento para consistencia
    ir_dict = ir.model_dump(mode='json', exclude={'metadata': {'timestamp'}})
    canonical = json.dumps(ir_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_potential_structure(ir: IR) -> str:
    """Hash solo de la estructura del potencial (excluye energías y onda incidente)"""
    structure = {
        "regions": [
            {
                "x_range": r.x_range,
                "value": r.value
            }
            for r in ir.potential.regions
        ]
    }
    canonical = json.dumps(structure, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
