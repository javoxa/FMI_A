def safe_float(value):
    try:
        return float(str(value).strip().replace(',', '.'))
    except Exception:
        raise ValueError(f"Cannot convert {value} to float")
