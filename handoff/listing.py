def clamp_limit(limit: int) -> int:
    """Keep list limits inside the spec range of 1 to 100."""
    return max(1, min(limit, 100))
