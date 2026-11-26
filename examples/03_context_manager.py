# =============================================================================
# FILE PURPOSE:
# Demonstrates scoped temporary saturating arithmetic using the clamp_scope()
# context manager. Shows how a single application can run standard unbounded
# math globally while confining saturating arithmetic to safety-critical algorithms.
#
# DUAL RUN STEPS:
# -----------------------------------------------------------------------------
# 🔴 [REGULAR / UNMODIFIED PYTHON]
# Run Command:
#     python3 examples/03_context_manager.py
# Expected Failure / Behavior:
#     Standard Python lacks sys.set_clamp_mode; raises RuntimeError:
#     RuntimeError: ClampPVM native extensions not found in current Python interpreter.
#
# 🟢 [CLAMPPVM UPGRADED RUNTIME]
# Run Command:
#     clamp-python examples/03_context_manager.py
# Expected Success Output:
#     - Global math executes with standard unbounded Python semantics (80 + 50 = 130).
#     - Entering 'with clamp_scope(0, 100):' isolates the safety block (80 + 50 -> 100).
#     - Exiting the block restores standard arithmetic automatically.
# =============================================================================

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from clamp_pvm import is_clamp_pvm_supported, clamp_scope, get_stats, reset_stats

def main():
    print("=" * 70)
    print("  EXAMPLE 03: Scoped Clamp Context Manager Demo")
    print("=" * 70)

    if not is_clamp_pvm_supported():
        print("\n[!] Regular / Unmodified Environment:")
        print("    Native VM hooks are missing.")
        try:
            with clamp_scope(0, 100):
                pass
        except RuntimeError as e:
            print(f"    Expected Failure: {e}")
            print("    Run this example with 'clamp-python' to see scoped saturation in action!")
            return

    # Phase 1: Normal Python Unclamped Arithmetic
    print("\nPhase 1: Standard Global Execution (Outside Context Manager)")
    global_calc = 150 + 200
    print(f"  150 + 200 = {global_calc} (Unbounded standard integer math)")
    assert global_calc == 350
    assert not sys.get_clamp_mode()

    # Phase 2: Scoped Hardware Actuator Calculation
    print("\nPhase 2: Entering 'with clamp_scope(min_val=0, max_val=100):'")
    reset_stats()
    with clamp_scope(min_val=0, max_val=100):
        assert sys.get_clamp_mode() is True
        print("  [Inside Scope] Actuator Servo Angle Calculations:")
        
        target_angle = 75
        command_delta = +60
        new_angle = target_angle + command_delta
        print(f"    target ({target_angle}°) + delta ({command_delta:+}°) = {new_angle}° (Auto-clamped to MAX 100°)")
        assert new_angle == 100

        reverse_delta = -150
        floor_angle = new_angle + reverse_delta
        print(f"    angle ({new_angle}°) + delta ({reverse_delta:+}°) = {floor_angle}° (Auto-clamped to MIN 0°)")
        assert floor_angle == 0

    # Phase 3: Immediate Restoration
    print("\nPhase 3: Exited Scope (Automatic Mode & Bounds Restoration)")
    assert not sys.get_clamp_mode()
    post_calc = 150 + 200
    print(f"  150 + 200 = {post_calc} (Unbounded arithmetic safely restored)")
    assert post_calc == 350

    stats = get_stats()
    print(f"\nFinal Telemetry: {stats['clamped_count']} hardware clamp events captured.")
    print("SUCCESS: Context scoping cleanly isolated without side-effects.")

if __name__ == "__main__":
    main()
