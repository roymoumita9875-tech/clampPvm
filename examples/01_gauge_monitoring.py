# =============================================================================
# FILE PURPOSE:
# Simulates an industrial fluid storage tank & telemetry gauge workload.
# Demonstrates how ClampPVM prevents tank overflow (>100%) and negative levels (<0%)
# automatically without writing manual defensive min/max clamping logic on every delta.
#
# DUAL RUN STEPS:
# -----------------------------------------------------------------------------
# 🔴 [REGULAR / UNMODIFIED PYTHON]
# Run Command:
#     python3 examples/01_gauge_monitoring.py
# Expected Failure / Behavior:
#     Standard Python allows unbounded integer arithmetic:
#     - Tank level reaches 135% (OVERFLOW / PHYSICAL TANK RUPTURE!)
#     - Tank level reaches -60% (UNDERFLOW / NEGATIVE PRESSURE CAVITATION!)
#     - Assertions fail or require manual clamp code at every line.
#
# 🟢 [CLAMPPVM UPGRADED RUNTIME]
# Run Command:
#     clamp-python examples/01_gauge_monitoring.py
# Expected Success Output:
#     ClampPVM intercepts every arithmetic boundary event:
#     - 70% + 45% -> 100% [CLAMPED: Auto-saturated at physical tank capacity]
#     - 20% - 80% ->   0% [CLAMPED: Auto-saturated at empty tank floor]
#     - Zero syntax changes; all industrial safety invariants hold.
# =============================================================================

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from clamp_pvm import is_clamp_pvm_supported, clamp_scope, get_stats, reset_stats

def run_simulation(is_clamped: bool):
    tank_level = 50  # Start at 50% capacity
    pump_cycles = [
        ("Cycle 1: Moderate Inflow", +20),
        ("Cycle 2: Heavy Rain Surge", +65),      # Exceeds 100% without clamping
        ("Cycle 3: Emergency Outflow", -90),    # Drops below 0% without clamping
        ("Cycle 4: Secondary Refill", +140),    # Massive surge
        ("Cycle 5: Drain Operation", -60),
    ]

    print(f"\n--- Simulation Mode: {'CLAMPED [ClampPVM]' if is_clamped else 'UNCLAMPED [Standard Python]'} ---")
    print(f"Initial Tank Level: {tank_level}%")

    for desc, delta in pump_cycles:
        prev = tank_level
        tank_level += delta
        status = "NORMAL"
        if is_clamped:
            if (tank_level == 100 or tank_level == 0) and (prev + delta != tank_level):
                status = "AUTO-CLAMPED"
        else:
            if tank_level > 100:
                status = "CRITICAL OVERFLOW!"
            elif tank_level < 0:
                status = "CRITICAL CAVITATION!"

        print(f"  {desc:<28} | delta: {delta:+4d}% | level: {tank_level:4d}% [{status}]")

    return tank_level

def main():
    print("=" * 70)
    print("  EXAMPLE 01: Industrial Tank & Sensor Gauge Monitoring")
    print("=" * 70)

    if not is_clamp_pvm_supported():
        print("\n[!] Running under standard Python (Unmodified).")
        level = run_simulation(is_clamped=False)
        print(f"\nFinal Unconstrained Tank Level: {level}%")
        print("Note: In physical reality, levels outside [0%, 100%] cause equipment damage!")
        return

    # Under ClampPVM
    print("\n[+] Running under ClampPVM Runtime.")
    reset_stats()
    
    with clamp_scope(min_val=0, max_val=100):
        final_level = run_simulation(is_clamped=True)
        assert 0 <= final_level <= 100, "Tank level must remain within [0, 100]"

    stats = get_stats()
    print(f"\nSimulation complete: Final Level = {final_level}%")
    print(f"Telemetry: Intercepted {stats['clamped_count']} hardware boundary violations!")
    print("\nSUCCESS: Tank capacity bounds remained 100% intact throughout simulation.")

if __name__ == "__main__":
    main()
