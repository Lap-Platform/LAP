"""LAP core package — parser, compiler, converter, and utilities."""


# Backward-compatible aliases (lazy to avoid import side effects)
def __getattr__(name):
    if name == "parse_doclean":
        from lap.core.parser import parse_lap
        return parse_lap
    if name == "doclean_to_openapi":
        from lap.core.converter import lap_to_openapi
        return lap_to_openapi
    raise AttributeError(f"module 'lap.core' has no attribute {name!r}")
