import logging
from typing import Dict, Any
from backend.shared.models.ir import IR

logger = logging.getLogger(__name__)

class SymbolicSolver:
    """
    Solver simbólico para casos donde no hay valores numéricos de energía
    o los potenciales son simbólicos. Devuelve la estructura general de las
    funciones de onda y advertencias.
    """

    async def solve(self, ir: IR) -> Dict[str, Any]:
        regions = ir.potential.regions
        incident = ir.incident_wave

        # Determinar la energía incidente (simbólica)
        energy_label = incident.energy if incident.present else "E"
        if not incident.present:
            energy_label = "E"
            incident_region = "region_1"
            direction = "L->R"
        else:
            incident_region = incident.region
            direction = incident.direction

        regions_solution = []
        for region in regions:
            # Obtener la relación E-V para esta región (si existe)
            relation = None
            if energy_label in region.energies:
                relation = region.energies[energy_label]
            else:
                relation = "unknown"

            # Forma general según relación
            if relation == ">":
                form = f"ψ_{region.id}(x) = A e^{{i k x}} + B e^{{-i k x}}"
                wave_type = "oscillatory"
                comment = "con k = √(2m(E-V))/ħ"
            elif relation == "<":
                form = f"ψ_{region.id}(x) = C e^{{κ x}} + D e^{{-κ x}}"
                wave_type = "evanescent"
                comment = "con κ = √(2m(V-E))/ħ"
            elif relation == "=":
                form = f"ψ_{region.id}(x) = A x + B"
                wave_type = "linear"
                comment = ""
            else:
                form = f"ψ_{region.id}(x) = forma desconocida (falta relación E-V)"
                wave_type = "unknown"
                comment = "No se ha podido determinar si E > V o E < V"

            regions_solution.append({
                "id": region.id,
                "x_range": region.x_range,
                "V": region.value,
                "wave_type": wave_type,
                "form": form,
                "comment": comment,
                "relation": relation
            })

        # Construir advertencias
        warnings = []
        # Verificar si hay energías simbólicas
        has_symbolic_energy = any(
            label for reg in regions
            for label in reg.energies.keys()
            if not self._is_numeric(label)
        )
        if has_symbolic_energy:
            warnings.append("Energías simbólicas detectadas. No se pueden calcular coeficientes numéricos sin valores concretos.")
        if not incident.present:
            warnings.append("Se asumió onda incidente desde la izquierda (L->R) con energía E (simbólica).")
        # Si hay potenciales simbólicos
        has_symbolic_potential = any(
            not self._is_numeric(region.value)
            for region in regions
        )
        if has_symbolic_potential:
            warnings.append("Potencial simbólico detectado. Se usan formas generales.")

        # Si hay valores numéricos de potencial pero energía simbólica
        has_numeric_potential = all(self._is_numeric(region.value) for region in regions)
        if has_numeric_potential and has_symbolic_energy:
            warnings.append("Potencial numérico pero energía simbólica. Las formas de onda son generales; introduzca un valor numérico para E para obtener coeficientes.")

        return {
            "type": "symbolic",
            "regions": regions_solution,
            "incident_wave": {
                "energy": energy_label,
                "region": incident_region,
                "direction": direction
            },
            "warnings": warnings,
            "message": "Solución simbólica: formas generales de la función de onda según relación E-V."
        }

    def _is_numeric(self, s: str) -> bool:
        try:
            float(s)
            return True
        except:
            return False
