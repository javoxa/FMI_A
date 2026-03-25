import logging
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
import cmath

from backend.shared.models.ir import IR
from backend.shared.utils.numbers import safe_float

logger = logging.getLogger(__name__)

class NumericalSolver:
    def __init__(self, mass: float = 1.0, hbar: float = 1.0):
        self.mass = mass
        self.hbar = hbar

    async def solve(self, ir: IR, energy: Optional[float] = None) -> Dict[str, Any]:
        if energy is None:
            energy = self._extract_energy(ir)
            if energy is None:
                return {
                    "type": "numerical",
                    "status": "missing_energy",
                    "message": "Se necesita un valor numérico de energía",
                    "available_energies": self._list_available_energies(ir)
                }

        regions = ir.potential.regions
        k_list, widths = self._compute_wave_numbers(regions, energy)
        if k_list is None:
            return {
                "type": "numerical",
                "status": "missing_parameters",
                "message": "Faltan valores numéricos de potencial"
            }

        R, T, r, t = self._transfer_matrix_method(k_list, widths)

        direction = ir.incident_wave.direction if ir.incident_wave.present else "L->R"

        wavefunctions = self._build_wavefunctions(ir, k_list, r, t, direction)

        return {
            "type": "numerical",
            "energy": energy,
            "direction": direction,
            "coefficients": {"R": float(R), "T": float(T), "r": complex(r), "t": complex(t)},
            "wave_numbers": {
                f"k_{i+1}": float(k.real) if abs(k.imag) < 1e-10 else f"{k.real:.3f} + {k.imag:.3f}i"
                for i, k in enumerate(k_list)
            },
            "regions": [
                {
                    "id": r.id,
                    "type": "propagating" if k.imag == 0 else "evanescent",
                    "wavefunction": wavefunctions[i] if wavefunctions else None
                }
                for i, (r, k) in enumerate(zip(regions, k_list))
            ]
        }

    def _extract_energy(self, ir: IR) -> Optional[float]:
        if ir.incident_wave.present and ir.incident_wave.energy:
            try:
                return safe_float(ir.incident_wave.energy)
            except ValueError:
                pass
        for region in ir.potential.regions:
            for energy_label in region.energies.keys():
                try:
                    return safe_float(energy_label)
                except ValueError:
                    continue
        return None

    def _list_available_energies(self, ir: IR) -> List[str]:
        energies = set()
        for region in ir.potential.regions:
            energies.update(region.energies.keys())
        if ir.incident_wave.energy:
            energies.add(ir.incident_wave.energy)
        return list(energies)

    def _compute_wave_numbers(self, regions, energy: float):
        k_list = []
        widths = []
        for region in regions:
            try:
                V = safe_float(region.value)
            except ValueError:
                return None, None
            diff = energy - V
            if diff >= 0:
                k = cmath.sqrt(2 * self.mass * diff) / self.hbar
            else:
                k = 1j * cmath.sqrt(2 * self.mass * (-diff)) / self.hbar
            k_list.append(k)

            start = region.x_range[0]
            end = region.x_range[1]
            if start == '-inf' or end == 'inf':
                width = float('inf')
            else:
                try:
                    width = safe_float(end) - safe_float(start)
                except ValueError:
                    width = 0.0
            widths.append(width)
        return k_list, widths

    def _transfer_matrix_method(self, k_list: List[complex], widths: List[float]) -> Tuple[float, float, complex, complex]:
        def transfer_matrix(k1, k2):
            return np.array([
                [(k1 + k2) / (2 * k1), (k1 - k2) / (2 * k1)],
                [(k1 - k2) / (2 * k1), (k1 + k2) / (2 * k1)]
            ], dtype=complex)

        def propagation_matrix(k, width):
            if np.isinf(width):
                return np.eye(2, dtype=complex)
            return np.array([
                [np.exp(1j * k * width), 0],
                [0, np.exp(-1j * k * width)]
            ], dtype=complex)

        n = len(k_list)
        M_total = np.eye(2, dtype=complex)

        for i in range(n - 1):
            if i > 0 and not np.isinf(widths[i]):
                P = propagation_matrix(k_list[i], widths[i])
                M_total = M_total @ P
            M = transfer_matrix(k_list[i], k_list[i+1])
            M_total = M_total @ M

        if n > 1 and not np.isinf(widths[n-1]):
            P_last = propagation_matrix(k_list[n-1], widths[n-1])
            M_total = M_total @ P_last

        r = M_total[1, 0] / M_total[0, 0]
        t = 1 / M_total[0, 0]
        R = abs(r)**2
        T = abs(t)**2

        if R + T > 1.01:
            logger.warning(f"R+T = {R+T} > 1")
        return R, T, r, t

    def _build_wavefunctions(self, ir, k_list, r, t, direction):
        regions = ir.potential.regions
        n = len(regions)
        wavefunctions = []
        incident_idx = None
        if ir.incident_wave.present and ir.incident_wave.region:
            for i, reg in enumerate(regions):
                if reg.id == ir.incident_wave.region:
                    incident_idx = i
                    break
        for i, reg in enumerate(regions):
            k = k_list[i]
            if i == 0:
                A = 1.0 if (direction == "L->R" and i == incident_idx) else 0.0
                B = r if i == incident_idx else 0.0
            elif i == n-1:
                A = t
                B = 0.0
            else:
                A = B = 0.0
            if k.imag == 0:
                expr = f"ψ_{reg.id}(x) = {A:.3f} e^{{{k.real:.3f} i x}} + {B:.3f} e^{{-{k.real:.3f} i x}}"
            else:
                kappa = -k.imag
                expr = f"ψ_{reg.id}(x) = {A:.3f} e^{{{kappa:.3f} x}} + {B:.3f} e^{{-{kappa:.3f} x}}"
            wavefunctions.append(expr)
        return wavefunctions
