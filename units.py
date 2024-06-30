
def scale_to_float(scale: str) -> float:
    if scale.endswith('uV'):
        return float(scale.strip('uV'))/1000000
    elif scale.endswith('mV'):
        return float(scale.strip('mV'))/1000
    elif scale.endswith('V'):
        return float(scale.strip('V'))
    else:
        raise Exception(f"unimplemented scale {scale}")

def float_to_scale(num: float) -> str:
    if num >= 1:
        return f"{num}V"
    elif num >= 0.001:
        return f"{num/1000}mV"
    elif num >= 0.000001:
        return f"{num/1000000}uV"
    else:
        raise Exception(f"unimplemented scale {num}")
