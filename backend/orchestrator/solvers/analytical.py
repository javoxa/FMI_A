import logging
from typing import Dict, Any
import math

from backend.shared.models.ir import IR

logger = logging.getLogger(__name__)


class AnalyticalSolver:
    """
    Solver analítico para potenciales estándar.
    """

    async def solve(self, ir: IR) -> Dict[str, Any]:
        """Resuelve analíticamente según el tipo de potencial"""
        potential_type = ir.topology.potential_type

        if potential_type == "barrier":
            return self._solve_barrier(ir)
        elif potential_type == "well":
            return self._solve_well(ir)
        elif potential_type == "step":
            return self._solve_step(ir)
        else:
            return {
                "type": "analytical",
                "status": "not_supported",
                "message": f"Potencial {potential_type} no soportado en solver analítico"
            }

    def _solve_barrier(self, ir: IR) -> Dict[str, Any]:
        """Solución para barrera rectangular"""
        regions = ir.potential.regions

        # Extraer parámetros
        try:
            V0 = float(regions[1].value)
            a = float(regions[0].x_range[1])
            b = float(regions[1].x_range[1])
            width = b - a
        except (ValueError, IndexError) as e:
            return {
                "type": "analytical",
                "status": "error",
                "message": f"Faltan parámetros numéricos: {e}",
                "required_parameters": ["V0", "width"]
            }

        # Obtener energía incidente
        energy = None
        if ir.incident_wave.present:
            energy_str = ir.incident_wave.energy
            # Buscar valor de energía en las relaciones
            for region in regions:
                if energy_str in region.energies:
                    # En este punto deberíamos tener un valor numérico
                    pass

        return {
            "type": "analytical",
            "potential_type": "barrier",
            "parameters": {
                "V0": V0,
                "width": width
            },
            "coefficients": {
                "R": "|r|^2",
                "T": "|t|^2"
            },
            "formulas": {
                "transmission": "T = 1 / (1 + (V0^2 * sinh^2(κa)) / (4E(V0-E))) para E < V0",
                "reflection": "R = 1 - T"
            },
            "latex": {
                "T": r"T = \frac{1}{1 + \frac{V_0^2 \sinh^2(\kappa a)}{4E(V_0 - E)}}",
                "kappa": r"\kappa = \sqrt{\frac{2m(V_0 - E)}{\hbar^2}}"
            }
        }

    def _solve_well(self, ir: IR) -> Dict[str, Any]:
        """Solución para pozo cuadrado"""
        regions = ir.potential.regions

        try:
            V0 = abs(float(regions[1].value))  # profundidad
            a = float(regions[0].x_range[1])
            b = float(regions[1].x_range[1])
            width = b - a
        except (ValueError, IndexError) as e:
            return {
                "type": "analytical",
                "status": "error",
                "message": f"Faltan parámetros numéricos: {e}",
                "required_parameters": ["V0", "width"]
            }

        return {
            "type": "analytical",
            "potential_type": "well",
            "parameters": {
                "V0": V0,
                "width": width
            },
            "states": {
                "bound": "Estados ligados: solución trascendental tan(k a/2) = κ/k o cot(k a/2) = -κ/k",
                "scattering": "Para E > 0: análogo a barrera con V0 negativo"
            },
            "latex": {
                "kappa": r"\kappa = \sqrt{\frac{2m|V_0 - E|}{\hbar^2}}",
                "k": r"k = \sqrt{\frac{2mE}{\hbar^2}}"
            }
        }

    def _solve_step(self, ir: IR) -> Dict[str, Any]:
        """Solución para escalón de potencial"""
        regions = ir.potential.regions

        try:
            V0 = float(regions[1].value) if len(regions) > 1 else 0
        except (ValueError, IndexError) as e:
            return {
                "type": "analytical",
                "status": "error",
                "message": f"Faltan parámetros numéricos: {e}"
            }

        return {
            "type": "analytical",
            "potential_type": "step",
            "parameters": {
                "V0": V0
            },
            "coefficients": {
                "R": "((k1 - k2)/(k1 + k2))^2",
                "T": "4k1 k2/(k1 + k2)^2"
            },
            "latex": {
                "R": r"R = \left(\frac{k_1 - k_2}{k_1 + k_2}\right)^2",
                "T": r"T = \frac{4k_1 k_2}{(k_1 + k_2)^2}",
                "k1": r"k_1 = \sqrt{\frac{2mE}{\hbar^2}}",
                "k2": r"k_2 = \sqrt{\frac{2m(E - V_0)}{\hbar^2}}"
            }
        }
