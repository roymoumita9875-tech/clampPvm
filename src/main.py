# =============================================================================
# FILE PURPOSE:
# Central entry point and architecture manifest for Flavor #7: ClampPVM.
# Contains a complete codebase directory map in comments followed by a runnable
# quick-start demo showcasing bounded arithmetic, telemetry metrics, and scoping.
# Usage: clamp-python src/main.py
# =============================================================================

"""
================================================================================
CLAMPPVM CODEBASE DIRECTORY MAP
================================================================================
.
├── COMPARISON.md               # Visual before-and-after breakdown with line-by-line diffs
├── README.md                   # Complete documentation, architecture diagrams, benchmarks
├── .gitignore                  # Git exclusions (build caches, binaries, virtualenvs)
│
├── dist/                       # Packaged SDK distribution artifacts
│   └── clamp-pvm-sdk.tar.gz    # Compressed runtime tarball (~94 MB) for laptop installation
│
├── src/                        # Core runtime sources and SDK wrappers
│   ├── main.py                 # [This File] Central codebase map and quick-start demo
│   ├── clamp_pvm.py            # High-level Python SDK with clamp_scope() context manager
│   ├── clamp.c                 # CPython runtime C source for saturating arithmetic engine
│   └── pycore_clamp.h          # CPython internal header defining runtime state & protos
│
├── scripts/                    # Build, installation, and patching automation
│   ├── build.sh                # End-to-end configure, make regen-cases, and compilation
│   ├── install.sh              # Extracts SDK to /opt/clamp-pvm and creates clamp-python link
│   └── patch_cpython.py        # Automated source patcher modifying upstream CPython files
│
├── tests/                      # Automated test verification suite
│   └── test_clamp_pvm.py       # Full regression test covering bounds, floats, in-place, errors
│
└── examples/                   # Runnable real-world domain demonstrations
    ├── 01_gauge_monitoring.py  # Industrial fluid tank level monitoring (0% - 100%)
    ├── 02_signal_processing.py # Audio DSP clipping & amplitude limiter simulation
    └── 03_context_manager.py   # Scoped temporary clamping using Python 'with' blocks
================================================================================
"""

import sys
import os

# Add src/ to path if running directly
sys.path.insert(0, os.path.dirname(__file__))
from clamp_pvm import is_clamp_pvm_supported, clamp_scope, get_stats, reset_stats

def main():
    print("=" * 70)
    print("  ClampPVM: Saturating / Clamped Arithmetic Runtime Demo")
    print("=" * 70)
    print(f"Interpreter: {sys.executable}")
    print(f"Version:     {sys.version}")
    print(f"Native ClampPVM Supported: {is_clamp_pvm_supported()}")

    if not is_clamp_pvm_supported():
        print("\n[!] WARNING: Running on standard Python interpreter.")
        print("    Native VM clamping requires the ClampPVM interpreter.")
        print("    Execute using: /usr/local/bin/clamp-python src/main.py")
        sys.exit(1)

    # 1. Default Unclamped Behavior
    print("\n[1] Default Mode (Clamping Disabled):")
    print(f"    sys.get_clamp_mode():   {sys.get_clamp_mode()}")
    print(f"    sys.get_clamp_bounds(): {sys.get_clamp_bounds()}")
    val_unclamped = 80 + 50
    print(f"    Math: 80 + 50 = {val_unclamped} (Standard Python arithmetic)")
    assert val_unclamped == 130

    # 2. Context-Managed Clamping
    print("\n[2] Scoped Saturating Arithmetic Mode [0, 100]:")
    reset_stats()
    with clamp_scope(0, 100):
        print(f"    Inside clamp_scope: mode={sys.get_clamp_mode()}, bounds={sys.get_clamp_bounds()}")
        
        # Upper bound saturation
        high_res = 80 + 50
        print(f"    80 + 50 -> {high_res}  (Saturated to MAX bound 100)")
        assert high_res == 100

        # Lower bound saturation
        low_res = 15 - 40
        print(f"    15 - 40 -> {low_res}    (Saturated to MIN bound 0)")
        assert low_res == 0

        # Multiplication saturation
        mult_res = 25 * 6
        print(f"    25 * 6  -> {mult_res}  (Saturated to MAX bound 100)")
        assert mult_res == 100

        # In-place operators
        gauge = 80
        gauge += 50
        print(f"    gauge = 80; gauge += 50 -> {gauge} (In-place += saturated to 100)")
        assert gauge == 100

        # Float values
        temp = 85.5 + 45.2
        print(f"    85.5 + 45.2 -> {temp} ({type(temp).__name__}, saturated to 100.0)")
        assert temp == 100.0

    # 3. Post-Scope Verification
    print("\n[3] Outside Scope (Automatic Mode Restoration):")
    print(f"    sys.get_clamp_mode(): {sys.get_clamp_mode()} (Restored to False)")
    restored_res = 80 + 50
    print(f"    80 + 50 = {restored_res} (Normal arithmetic resumes)")
    assert restored_res == 130

    # 4. Telemetry
    stats = get_stats()
    print(f"\n[4] Interception Telemetry: {stats}")
    print(f"    Total saturation events intercepted: {stats.get('clamped_count', 0)}")
    assert stats.get('clamped_count', 0) >= 5

    print("\n" + "=" * 70)
    print("  QUICK-START DEMO COMPLETE: ALL CHECKS PASSED (Exit Code 0)")
    print("=" * 70)

if __name__ == "__main__":
    main()
