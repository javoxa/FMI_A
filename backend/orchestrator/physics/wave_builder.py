from typing import Dict, Any, List
import cmath
from backend.shared.models.ir import IR

class WaveBuilder:
    """
    Construye expresiones analíticas de la función de onda en cada región
    basándose en las relaciones E-V y las condiciones de contorno.
    """

    def __init__(self, mass: float = 1.0, hbar: float = 1.0):
        self.mass = mass
        self.hbar = hbar

    def build(self, ir: IR, energy: float) -> List[Dict[str, Any]]:
        """
        Devuelve una lista de diccionarios, uno por región, con:
        - id
        - x_range
        - wave_type (oscillatory / evanescent)
        - expression (string LaTeX o simbólica)
        """
        regions = ir.potential.regions
        results = []

        # Determinar si la energía incidente está definida
        incident_energy = energy
        for region in regions:
            # Por simplicidad, asumimos la misma energía en todas las regiones
            # (en realidad la energía es constante)
            pass

        # Para cada región, construir expresión según relación E-V
        for i, region in enumerate(regions):
            try:
                V = float(region.value)
            except (ValueError, TypeError):
                V = None

            # Determinar tipo de onda según la relación con la energía incidente
            # Si no hay relación explícita, asumir oscilatoria si E > V, evanescente si E < V
            energy_label = ir.incident_wave.energy if ir.incident_wave.present else "E"
            relation = region.energies.get(energy_label, None)

            if relation is None and V is not None:
                # Inferir relación
                if incident_energy > V:
                    relation = ">"
                elif incident_energy < V:
                    relation = "<"
                else:
                    relation = "="

            # Construir expresión
            if relation == ">":
                k = cmath.sqrt(2 * self.mass * (incident_energy - V)) / self.hbar
                k_val = k.real
                expr = f"ψ_{region.id}(x) = A_{region.id} e^{{i {k_val:.3f} x}} + B_{region.id} e^{{-i {k_val:.3f} x}}"
                wave_type = "oscillatory"
            elif relation == "<":
                kappa = cmath.sqrt(2 * self.mass * (V - incident_energy)) / self.hbar
                kappa_val = kappa.real
                expr = f"ψ_{region.id}(x) = C_{region.id} e^{{{kappa_val:.3f} x}} + D_{region.id} e^{{-{kappa_val:.3f} x}}"
                wave_type = "evanescent"
            else:
                # E = V, onda plana? (solución lineal)
                expr = f"ψ_{region.id}(x) = A_{region.id} + B_{region.id} x"
                wave_type = "linear"

            results.append({
                "id": region.id,
                "x_range": region.x_range,
                "wave_type": wave_type,
                "expression": expr,
                "relation": relation
            })

        return results
