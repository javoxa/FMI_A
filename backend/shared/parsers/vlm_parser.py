from typing import Dict, Any
from datetime import datetime
from ..models.ir import IR, Metadata, Potential, Region, IncidentWave, Topology

def vlm_json_to_ir(vlm_data: Dict[str, Any]) -> Dict[str, Any]:
    segments = vlm_data.get("segments", [])
    wave = vlm_data.get("wave", {})
    nodes = vlm_data.get("nodes", {})

    region_ids = [f"R{i+1}" for i in range(len(segments))]

    regions = []
    symbols = {}
    symbol_counter = 0

    for i, seg in enumerate(segments):
        boundary = seg.get("boundary", ["-inf", "inf"])
        v_local = seg.get("V_local")

        if v_local is None:
            symbol_name = f"V{symbol_counter}"
            symbols[symbol_name] = f"region_{region_ids[i]}"
            v_local = symbol_name
            symbol_counter += 1
        else:
            try:
                v_local = str(float(v_local))
            except (ValueError, TypeError):
                v_local = str(v_local)

        regions.append({
            "id": region_ids[i],
            "x_range": boundary,
            "value": v_local,
            "energies": seg.get("relations", {})
        })

    incident_segment = wave.get("incident_segment")
    incident_wave = {
        "present": wave.get("present", False),
        "energy": wave.get("energy"),
        "region": region_ids[incident_segment - 1] if incident_segment and incident_segment <= len(region_ids) else None,
        "direction": wave.get("direction")
    }

    x_axis = nodes.get("x_axis", [])
    potentials = nodes.get("potentials", [])

    return {
        "metadata": {
            "source": "vlm",
            "timestamp": datetime.now(),
            "confidence": None,
            "potential_type": None,
            "version": "1.0"
        },
        "symbols": symbols,
        "potential": {
            "regions": regions,
            "units": {"length": "arbitrary", "energy": "arbitrary"}
        },
        "topology": {
            "region_count": len(regions),
            "has_barrier": False,
            "has_well": False,
            "has_step": False,
            "potential_type": None,
            "symmetry": None
        },
        "incident_wave": incident_wave,
        "_raw_nodes": {"x_axis": x_axis, "potentials": potentials}
    }
