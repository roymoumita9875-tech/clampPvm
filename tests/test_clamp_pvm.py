# =============================================================================
# FILE PURPOSE:
# Automated regression test suite for Flavor #7: ClampPVM saturating arithmetic.
# Validates bounds enforcement, integer/float type stability, in-place operators,
# string/collection non-interference, error handling, telemetry, and context scoping.
# Usage: clamp-python tests/test_clamp_pvm.py
# =============================================================================

import sys
import os
import unittest

# Ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from clamp_pvm import (
    is_clamp_pvm_supported,
    set_mode,
    get_mode,
    set_bounds,
    get_bounds,
    get_stats,
    reset_stats,
    clamp_scope,
)

class TestClampPVM(unittest.TestCase):

    def setUp(self):
        self.assertTrue(
            is_clamp_pvm_supported(),
            "ClampPVM requires running under the modified 'clamp-python' interpreter."
        )
        set_mode(False)
        set_bounds(0, 100)
        reset_stats()

    def tearDown(self):
        set_mode(False)
        reset_stats()

    def test_default_unclamped_mode(self):
        """Confirm that when clamp mode is False, arithmetic is standard CPython."""
        self.assertFalse(get_mode())
        self.assertEqual(80 + 50, 130)
        self.assertEqual(15 - 40, -25)
        self.assertEqual(25 * 6, 150)
        self.assertEqual(get_stats()["clamped_count"], 0)

    def test_basic_integer_clamping(self):
        """Test integer upper and lower bound saturation [0, 100]."""
        set_bounds(0, 100)
        set_mode(True)
        self.assertTrue(get_mode())

        # Upper bound saturation
        self.assertEqual(80 + 50, 100)
        self.assertEqual(25 * 6, 100)

        # Lower bound saturation
        self.assertEqual(15 - 40, 0)
        self.assertEqual(-10 + -20, 0)

        # Within bounds unaltered
        self.assertEqual(20 + 35, 55)

        stats = get_stats()
        self.assertGreaterEqual(stats["clamped_count"], 4)

    def test_inplace_arithmetic(self):
        """Verify that +=, -=, and *= are properly intercepted and clamped."""
        set_bounds(0, 100)
        set_mode(True)

        x = 80
        x += 50
        self.assertEqual(x, 100)

        y = 15
        y -= 40
        self.assertEqual(y, 0)

        z = 25
        z *= 6
        self.assertEqual(z, 100)

    def test_float_arithmetic(self):
        """Verify float saturation and type stability."""
        set_bounds(0.0, 100.0)
        set_mode(True)

        f_high = 80.5 + 45.5
        self.assertEqual(f_high, 100.0)
        self.assertIsInstance(f_high, float)

        f_low = 10.5 - 50.5
        self.assertEqual(f_low, 0.0)
        self.assertIsInstance(f_low, float)

    def test_custom_negative_bounds(self):
        """Verify custom symmetrical bounds e.g. [-50, 50]."""
        set_bounds(-50, 50)
        set_mode(True)
        self.assertEqual(get_bounds(), (-50, 50))

        self.assertEqual(40 + 30, 50)
        self.assertEqual(-30 - 30, -50)
        self.assertEqual(10 * 10, 50)

    def test_non_numeric_types_unaffected(self):
        """Verify strings, lists, and tuples are never clamped."""
        set_bounds(0, 10)
        set_mode(True)

        s = "Hello " + "World"
        self.assertEqual(s, "Hello World")

        lst = [1, 2, 3] + [4, 5, 6]
        self.assertEqual(lst, [1, 2, 3, 4, 5, 6])

    def test_input_validation(self):
        """Verify invalid bounds raise proper Python exceptions."""
        with self.assertRaises(ValueError):
            set_bounds(100, 50)  # min > max

        with self.assertRaises(TypeError):
            sys.set_clamp_bounds("invalid", 100)

    def test_context_manager(self):
        """Verify clamp_scope() temporary scoping and state restoration."""
        self.assertFalse(get_mode())

        with clamp_scope(10, 50):
            self.assertTrue(get_mode())
            self.assertEqual(get_bounds(), (10, 50))
            self.assertEqual(5 + 2, 10)     # Clamped to min
            self.assertEqual(40 + 30, 50)   # Clamped to max

        # Restored automatically
        self.assertFalse(get_mode())
        self.assertEqual(5 + 2, 7)

    def test_telemetry_reset(self):
        """Verify telemetry counter incrementing and reset."""
        set_bounds(0, 100)
        set_mode(True)
        reset_stats()
        self.assertEqual(get_stats()["clamped_count"], 0)

        _ = 90 + 90
        _ = 10 - 50
        self.assertEqual(get_stats()["clamped_count"], 2)

        reset_stats()
        self.assertEqual(get_stats()["clamped_count"], 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
