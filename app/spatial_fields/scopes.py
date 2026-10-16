"""Stable publication scopes for independently switchable field models."""


def model_scope(base_scope: str, model_key: str, *, primary_model: str) -> str:
    """Keep the primary scope backward compatible and isolate other models."""
    return base_scope if model_key == primary_model else f"{base_scope}:{model_key}"

