# =============================================================================
# FILE PURPOSE:
# Simulates a Digital Signal Processing (DSP) audio gain stage and amplitude limiter.
# Demonstrates saturating float arithmetic [-1.0, 1.0] preventing digital clipping
# wraparound, distortion, and floating-point numeric spikes without expensive per-sample calls.
#
# DUAL RUN STEPS:
# -----------------------------------------------------------------------------
# 🔴 [REGULAR / UNMODIFIED PYTHON]
# Run Command:
#     python3 examples/02_signal_processing.py
# Expected Failure / Behavior:
#     Standard Python amplifies signal linearly without physical DAC constraints:
#     - Peak amplitude exceeds 1.0 (reaches +1.80 and -1.65)
#     - Causes digital clipping and loud acoustic distortion on downstream hardware
#     - Requires min(1.0, max(-1.0, sample)) called in an inner tight loop.
#
# 🟢 [CLAMPPVM UPGRADED RUNTIME]
# Run Command:
#     clamp-python examples/02_signal_processing.py
# Expected Success Output:
#     ClampPVM saturates signal values at [-1.0, 1.0] directly in the VM:
#     - 0.90 * 2.0 -> 1.00 (Hard ceiling limiter applied natively)
#     - -0.85 * 2.0 -> -1.00 (Hard floor limiter applied natively)
#     - Execution executes with native C-level speed and zero code clutter.
# =============================================================================

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from clamp_pvm import is_clamp_pvm_supported, clamp_scope, get_stats, reset_stats

def process_audio_buffer(samples, gain, is_clamped: bool):
    output = []
    for s in samples:
        amplified = s * gain
        output.append(amplified)
    return output

def main():
    print("=" * 70)
    print("  EXAMPLE 02: DSP Signal Processing & Audio Hard Limiter")
    print("=" * 70)

    # Synthetic waveform buffer with peaks
    raw_samples = [0.15, 0.45, 0.85, 0.95, 0.20, -0.30, -0.80, -0.92, -0.10, 0.50]
    gain_factor = 1.8  # +5.1 dB boost that pushes peaks past +/- 1.0

    print(f"Input Samples: {raw_samples[:5]} ... (len={len(raw_samples)})")
    print(f"Applying Gain Factor: {gain_factor}x\n")

    if not is_clamp_pvm_supported():
        print("[!] Running under standard Python (Unmodified).")
        t0 = time.perf_counter()
        processed = process_audio_buffer(raw_samples, gain_factor, is_clamped=False)
        dt = (time.perf_counter() - t0) * 1000
        
        print(f"Output Samples: {[round(x, 2) for x in processed]}")
        peaks = [x for x in processed if x > 1.0 or x < -1.0]
        print(f"Distortion Alert: {len(peaks)} samples exceeded +/- 1.0 limit!")
        print(f"Max Amplitude: {max(processed):.2f} (Clipping occurred!)")
        return

    # Under ClampPVM
    print("[+] Running under ClampPVM Runtime with [-1.0, 1.0] Clamping.")
    reset_stats()
    
    t0 = time.perf_counter()
    with clamp_scope(min_val=-1.0, max_val=1.0):
        processed = process_audio_buffer(raw_samples, gain_factor, is_clamped=True)
    dt = (time.perf_counter() - t0) * 1000

    print(f"Output Samples: {[round(x, 2) for x in processed]}")
    stats = get_stats()
    print(f"\nProcessing Time: {dt:.4f} ms")
    print(f"Hard Limiter Events: {stats['clamped_count']} samples saturated cleanly.")
    
    # Assert physical safety constraints
    for x in processed:
        assert -1.0 <= x <= 1.0, f"Sample {x} violated [-1.0, 1.0] DAC limit!"
    
    print("SUCCESS: Audio stream stayed strictly within [-1.0, 1.0] bounds.")

if __name__ == "__main__":
    main()
