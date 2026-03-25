from typing import Dict, Any, List
from ..models.ir import IR, Region, Potential, Topology, Metadata, IncidentWave
from ..utils.numbers import safe_float


def normalize_ir(ir_dict: Dict[str, Any]) -> IR:
    # Construir IR base
    ir = IR(
        metadata=Metadata(**ir_dict["metadata"]),
        symbols=ir_dict.get("symbols", {}),
        potential=Potential(
            regions=[Region(**r) for r in ir_dict["potential"]["regions"]],
            units=ir_dict["potential"].get("units", {"length": "arbitrary", "energy": "arbitrary"})
        ),
        incident_wave=IncidentWave(**ir_dict.get("incident_wave", {"present": False}))
    )

    # Normalizar IDs a region_1, region_2, ...
    for i, region in enumerate(ir.potential.regions):
        region.id = f"region_{i+1}"

    # --- MAPEO DE incident_wave.region ANTES del default ---
    if ir.incident_wave.region:
        # Intentar convertir formato "R2" -> "region_2"
        if ir.incident_wave.region.startswith("R") and ir.incident_wave.region[1:].isdigit():
            idx = int(ir.incident_wave.region[1:]) - 1
            if 0 <= idx < len(ir.potential.regions):
                ir.incident_wave.region = f"region_{idx+1}"
        # También puede venir como "region_2", lo dejamos igual

    # --- Onda incidente por defecto si no está presente ---
    if not ir.incident_wave.present:
        ir.incident_wave = IncidentWave(
            present=True,
            energy=None,
            region="region_1",
            direction="L->R"
        )
        ir.derived["incident_assumed"] = True

    # Calcular topología y asignar directamente a ir.topology
    topology = _calculate_topology(ir.potential.regions, ir_dict.get("_raw_nodes", {}))
    ir.topology = topology

    # Validaciones físicas (solo warnings)
    _validate_physical_consistency(ir)

    return ir


def _calculate_topology(regions: List[Region], raw_nodes: Dict) -> Topology:
    region_count = len(regions)
    values = []
    for reg in regions:
        try:
            values.append(safe_float(reg.value))
        except ValueError:
            values.append(None)

    has_barrier = has_well = has_step = False
    potential_type = "custom"
    symmetry = None

    if region_count >= 2 and all(v is not None for v in values):
        if region_count == 2 and values[0] != values[1]:
            has_step = True
            potential_type = "step"
        elif region_count == 3:
            left, middle, right = values
            if left == right:
                symmetry = "symmetric" if left == right else "asymmetric"
                if middle > left:
                    has_barrier = True
                    potential_type = "barrier"
                elif middle < left:
                    has_well = True
                    potential_type = "well"

    return Topology(
        region_count=region_count,
        has_barrier=has_barrier,
        has_well=has_well,
        has_step=has_step,
        potential_type=potential_type,
        symmetry=symmetry
    )


def _validate_physical_consistency(ir: IR):
    warnings = []

    def can_float(x):
        try:
            float(x)
            return True
        except:
            return False

    regions = ir.potential.regions

    for i in range(1, len(regions)):
        prev_end = regions[i-1].x_range[1]
        curr_start = regions[i].x_range[0]

        if not (can_float(prev_end) and can_float(curr_start)):
            warnings.append(f"Non-numeric boundary encountered: {prev_end}, {curr_start}")
            continue

        try:
            if float(prev_end) != float(curr_start):
                warnings.append(f"Regions not contiguous: {prev_end} != {curr_start}")
        except ValueError:
            warnings.append(f"Invalid numeric boundary: {prev_end} or {curr_start}")

    if ir.incident_wave.present:
        region_ids = [r.id for r in regions]
        if ir.incident_wave.region not in region_ids:
            warnings.append(f"Incident wave region '{ir.incident_wave.region}' not found")

    if warnings:
        ir.derived["warnings"] = warnings
