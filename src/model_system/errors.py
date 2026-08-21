class ModelSystemError(RuntimeError):
    """Base error for deterministic 3D operations."""


class UnsafeModelError(ModelSystemError):
    """Raised when an input model violates safety limits."""


class ModelingToolUnavailableError(ModelSystemError):
    """Raised when an optional modeling backend is unavailable."""
