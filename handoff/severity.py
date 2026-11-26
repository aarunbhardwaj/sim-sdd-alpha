RANKS = {"info": 0, "warning": 1, "critical": 2}


def severity_rank(value: str) -> int:
    """Rank a declared handoff severity. Unknown values are rejected."""
    if value not in RANKS:
        raise ValueError("invalid severity")
    return RANKS[value]
