import logging
import json
import hashlib
from typing import Dict, Any, Optional
from enum import Enum

from backend.shared.models.ir import IR
from backend.shared.utils.numbers import safe_float

logger = logging.getLogger(__name__)

class SolutionType(Enum):
    ANALYTICAL = "analytical"
    NUMERICAL = "numerical"
    SYMBOLIC = "symbolic"
    LLM_FALLBACK = "llm_fallback"

class Orchestrator:
    def __init__(self, cache=None, solver_analytical=None, solver_numerical=None, solver_symbolic=None, llm_client=None):
        self.cache = cache or {}
        self.solver_analytical = solver_analytical
        self.solver_numerical = solver_numerical
        self.solver_symbolic = solver_symbolic
        self.llm_client = llm_client

    async def solve(self, ir: IR) -> Dict[str, Any]:
        ir_hash = self._hash_ir(ir)

        if ir_hash in self.cache:
            logger.info(f"Cache hit for {ir_hash[:8]}")
            return self.cache[ir_hash]

        decision = self._decide(ir)

        logger.info("decision", extra={
            "ir_hash": ir_hash,
            "decision": decision.value,
            "potential_type": ir.topology.potential_type if ir.topology else None,
            "region_count": len(ir.potential.regions),
            "has_incident": ir.incident_wave.present
        })

        if decision == SolutionType.ANALYTICAL:
            result = await self._solve_analytical(ir)
        elif decision == SolutionType.NUMERICAL:
            result = await self._solve_numerical(ir, energy=None)
        elif decision == SolutionType.SYMBOLIC:
            result = await self._solve_symbolic(ir)
        else:
            result = await self._fallback_llm(ir)

        self.cache[ir_hash] = result
        return result

    async def solve_with_energy(self, ir: IR, energy: float) -> Dict[str, Any]:
        return await self._solve_numerical(ir, energy=energy)

    def _decide(self, ir: IR) -> SolutionType:
        # 1. Si no hay onda incidente, ya se asumió por defecto en normalize_ir,
        #    pero por si acaso aún no tiene, preferimos simbólico (no podemos calcular scattering)
        if not ir.incident_wave.present:
            return SolutionType.SYMBOLIC

        # 2. Si no hay ninguna energía numérica (solo etiquetas E1, E2, ...) → simbólico
        if not self._has_numeric_energy(ir):
            return SolutionType.SYMBOLIC

        # 3. Si algún valor de potencial es simbólico (ej. V0) → simbólico
        if self._is_symbolic(ir):
            return SolutionType.SYMBOLIC

        # 4. Tipos analíticos conocidos
        pt = ir.topology.potential_type if ir.topology else None
        if pt in ["barrier", "well", "step"]:
            return SolutionType.ANALYTICAL

        # 5. Si todo es numérico y no es potencial conocido → numérico
        return SolutionType.NUMERICAL

    def _has_numeric_energy(self, ir: IR) -> bool:
        """Verifica si hay alguna energía con valor numérico en el IR."""
        # Revisar energía incidente
        if ir.incident_wave.energy:
            try:
                safe_float(ir.incident_wave.energy)
                return True
            except ValueError:
                pass
        # Revisar energías en las relaciones
        for region in ir.potential.regions:
            for energy_label in region.energies.keys():
                try:
                    safe_float(energy_label)
                    return True
                except ValueError:
                    continue
        return False

    def _is_symbolic(self, ir: IR) -> bool:
        for region in ir.potential.regions:
            try:
                safe_float(region.value)
            except ValueError:
                return True
        return False

    async def _solve_analytical(self, ir: IR) -> Dict[str, Any]:
        if self.solver_analytical is None:
            return {"type": "error", "message": "Solver analítico no configurado"}
        return await self.solver_analytical.solve(ir)

    async def _solve_numerical(self, ir: IR, energy: Optional[float] = None) -> Dict[str, Any]:
        if self.solver_numerical is None:
            return {"type": "error", "message": "Solver numérico no configurado"}
        return await self.solver_numerical.solve(ir, energy=energy)

    async def _solve_symbolic(self, ir: IR) -> Dict[str, Any]:
        if self.solver_symbolic is None:
            from .solvers.symbolic import SymbolicSolver
            self.solver_symbolic = SymbolicSolver()
        return await self.solver_symbolic.solve(ir)

    async def _fallback_llm(self, ir: IR) -> Dict[str, Any]:
        if self.llm_client is None:
            return {
                "type": "llm_fallback",
                "message": "LLM no disponible. Proporcione valores numéricos."
            }
        physical = self._build_physical_structure(ir)
        prompt = self._build_llm_prompt(physical)
        response = await self.llm_client.generate(prompt)
        return {
            "type": "llm_fallback",
            "llm_response": response,
            "physical_structure": physical
        }

    def _build_physical_structure(self, ir: IR) -> Dict:
        energy_label = ir.incident_wave.energy if ir.incident_wave.present else None
        regions_info = []
        for region in ir.potential.regions:
            relation = None
            if energy_label and energy_label in region.energies:
                relation = region.energies[energy_label]
            if relation is None and energy_label:
                try:
                    V = safe_float(region.value)
                    E = safe_float(energy_label)
                    if E > V:
                        relation = ">"
                    elif E < V:
                        relation = "<"
                    else:
                        relation = "="
                except (ValueError, TypeError):
                    pass
            wave_type = "oscillatory" if relation == ">" else "evanescent" if relation == "<" else "linear" if relation == "=" else "unknown"
            regions_info.append({
                "id": region.id,
                "x_range": region.x_range,
                "V": region.value,
                "wave_type": wave_type,
                "relation": relation
            })
        return {
            "regions": regions_info,
            "incident_wave": {
                "energy": ir.incident_wave.energy,
                "region": ir.incident_wave.region,
                "direction": ir.incident_wave.direction
            },
            "topology": ir.topology.model_dump() if ir.topology else {},
            "symbols": ir.symbols
        }

    def _build_llm_prompt(self, physical_structure: Dict) -> str:
        return f"""
Eres un físico cuántico. A continuación se describe la estructura física de un potencial unidimensional.

Estructura:
{json.dumps(physical_structure, indent=2)}

Tu tarea es:
1. Explicar en lenguaje natural la configuración del potencial.
2. Escribir la función de onda en cada región usando las formas adecuadas (oscilatoria o evanescente) según la relación E-V.
3. Indicar las condiciones de contorno que se aplican.
4. Si es posible, dar expresiones simbólicas para los coeficientes de reflexión y transmisión en términos de los parámetros (E, V0, anchos, etc.).

No realices deducciones numéricas a menos que los valores sean explícitamente numéricos.
"""

    def _hash_ir(self, ir: IR) -> str:
        # Excluir timestamp de metadata y todo el campo derived
        exclude = {"metadata": {"timestamp"}, "derived": True}
        data = ir.model_dump(mode='json', exclude=exclude)
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
