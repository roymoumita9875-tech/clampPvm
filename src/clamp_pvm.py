# =============================================================================
# FILE PURPOSE:
# High-level Python SDK and context manager for ClampPVM saturating arithmetic.
# Provides Pythonic context managers (clamp_scope), configuration helpers,
# telemetry metrics formatters, and fallback simulation for standard Python runtimes.
# Usage: from clamp_pvm import clamp_scope, get_stats, is_clamp_pvm_supported
# =============================================================================

import sys
from contextlib import contextmanager
from typing import Tuple, Dict, Any, Optional

def is_clamp_pvm_supported() -> bool:
    """Check if the current Python interpreter has native ClampPVM VM extensions."""
    return hasattr(sys, "set_clamp_mode") and hasattr(sys, "set_clamp_bounds")

def set_mode(enabled: bool) -> None:
    """Enable or disable VM-level saturating arithmetic."""
    if is_clamp_pvm_supported():
        sys.set_clamp_mode(enabled)
    else:
        raise RuntimeError("ClampPVM native extensions not found in current Python interpreter.")

def get_mode() -> bool:
    """Return whether VM-level saturating arithmetic is currently active."""
    if is_clamp_pvm_supported():
        return sys.get_clamp_mode()
    return False

def set_bounds(min_val: float, max_val: float) -> None:
    """Set lower and upper numeric bounds for saturating arithmetic."""
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) must be <= max_val ({max_val})")
    if is_clamp_pvm_supported():
        sys.set_clamp_bounds(min_val, max_val)
    else:
        raise RuntimeError("ClampPVM native extensions not found in current Python interpreter.")

def get_bounds() -> Tuple[float, float]:
    """Retrieve current (min_val, max_val) bounds tuple."""
    if is_clamp_pvm_supported():
        return sys.get_clamp_bounds()
    return (0.0, 100.0)

def get_stats() -> Dict[str, Any]:
    """Return telemetry dictionary {'clamped_count': int}."""
    if is_clamp_pvm_supported():
        return sys.get_clamp_stats()
    return {"clamped_count": 0}

def reset_stats() -> None:
    """Reset the telemetry counter to zero."""
    if is_clamp_pvm_supported():
        sys.reset_clamp_stats()

@contextmanager
def clamp_scope(min_val: float = 0.0, max_val: float = 100.0):
    """
    Context manager that temporarily enables ClampPVM saturating arithmetic
    within the specified [min_val, max_val] interval, restoring previous
    mode and bounds upon exit.
    
    Example:
        with clamp_scope(0, 100):
            sensor_reading = raw_reading + delta  # Saturated automatically
    """
    if not is_clamp_pvm_supported():
        raise RuntimeError(
            "ClampPVM runtime required. Run this script using 'clamp-python'."
        )
    
    prev_mode = get_mode()
    prev_bounds = get_bounds()
    
    try:
        set_bounds(min_val, max_val)
        set_mode(True)
        yield
    finally:
        set_mode(prev_mode)
        set_bounds(prev_bounds[0], prev_bounds[1])

class ClampContext:
    """Object-oriented controller for ClampPVM runtime configuration."""
    
    def __init__(self, min_val: float = 0.0, max_val: float = 100.0):
        self.min_val = min_val
        self.max_val = max_val

    def __enter__(self):
        self.prev_mode = get_mode() if is_clamp_pvm_supported() else False
        self.prev_bounds = get_bounds() if is_clamp_pvm_supported() else (0.0, 100.0)
        if is_clamp_pvm_supported():
            set_bounds(self.min_val, self.max_val)
            set_mode(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if is_clamp_pvm_supported():
            set_mode(self.prev_mode)
            set_bounds(self.prev_bounds[0], self.prev_bounds[1])
