def escape_md(text: str) -> str:
    """Escapa caracteres especiales según MarkdownV2 de Telegram."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return ''.join("\\" + c if c in escape_chars else c for c in text)


def format_full_response(ir, solution) -> str:
    lines = []

    # --- Topología ---
    topology = ir.topology
    if topology:
        pt = topology.potential_type or "genérico"
        lines.append(escape_md(f"🔬 *Potencial detectado:* {pt}"))
        if topology.symmetry:
            lines.append(escape_md(f"   Simetría: {topology.symmetry}"))
    else:
        lines.append(escape_md("🔬 *Potencial detectado:* (desconocido)"))

    # --- Estructura ---
    lines.append(escape_md("\n📐 *Estructura:*"))
    for region in ir.potential.regions:
        line = f"   {region.id}: {str(region.x_range[0])} → {str(region.x_range[1])}   V={region.value}"
        lines.append(escape_md(line))
        if region.energies:
            rel_str = ", ".join([f"{e}{rel}" for e, rel in region.energies.items()])
            lines.append(escape_md(f"      Energías: {rel_str}"))

    # --- Solución ---
    lines.append(escape_md("\n🌊 *Solución:*"))

    if solution.get("type") == "analytical":
        lines.append(escape_md("   Tipo: analítica"))
        if "parameters" in solution:
            params = ", ".join([f"{k}={v}" for k, v in solution["parameters"].items()])
            lines.append(escape_md(f"   Parámetros: {params}"))
        if "latex" in solution:
            for key, latex in solution["latex"].items():
                lines.append(escape_md(f"   {latex}"))
        if "coefficients" in solution:
            lines.append(escape_md(f"   R = {solution['coefficients'].get('R', '?')}"))
            lines.append(escape_md(f"   T = {solution['coefficients'].get('T', '?')}"))

    elif solution.get("type") == "numerical":
        lines.append(escape_md(f"   Tipo: numérica"))
        lines.append(escape_md(f"   Energía: {solution.get('energy', '?')}"))
        if "coefficients" in solution:
            lines.append(escape_md(f"   R = {solution['coefficients']['R']:.4f}"))
            lines.append(escape_md(f"   T = {solution['coefficients']['T']:.4f}"))
        for reg in solution.get("regions", []):
            if reg.get("wavefunction"):
                lines.append(escape_md(f"   {reg['id']}: {reg['wavefunction']}"))

    elif solution.get("type") == "symbolic":
        lines.append(escape_md("   Tipo: solución simbólica"))
        inc = solution.get("incident_wave", {})
        lines.append(escape_md(f"   Energía incidente: {inc.get('energy', '?')} (simbólica)"))
        lines.append(escape_md(f"   Dirección: {inc.get('direction', '?')}"))
        for reg in solution.get("regions", []):
            # Línea sin asteriscos
            line = f"   Región {reg['id']}: {reg['x_range'][0]} → {reg['x_range'][1]}, V={reg['V']}"
            lines.append(escape_md(line))
            lines.append(escape_md(f"      Tipo: {reg['wave_type']}"))
            lines.append(escape_md(f"      Forma: {reg['form']}"))
            if reg.get('comment'):
                # Nota sin asteriscos
                lines.append(escape_md(f"      Nota: {reg['comment']}"))
        warnings = solution.get("warnings", [])
        if warnings:
            lines.append(escape_md("\n⚠️ *Advertencias:*"))
            for w in warnings:
                lines.append(escape_md(f"   - {w}"))

    elif solution.get("type") == "llm_fallback":
        lines.append(escape_md(f"   {solution.get('message', 'Respuesta del LLM:')}"))
        if "llm_response" in solution:
            lines.append(escape_md(f"\n{solution['llm_response']}"))

    else:
        lines.append(escape_md(f"   {solution.get('message', 'Solución no disponible')}"))

    # --- Advertencias de validación del IR ---
    warnings = ir.derived.get("warnings", [])
    if warnings:
        lines.append(escape_md("\n⚠️ *Advertencias de validación:*"))
        for w in warnings:
            lines.append(escape_md(f"   - {w}"))

    # Unir con saltos de línea y devolver (todo ya escapado individualmente)
    return "\n".join(lines)
