import sys
import os
import unittest

sys.path.insert(0, os.path.abspath("."))

loader = unittest.TestLoader()
start_dir = "tests"
suite = loader.discover(start_dir, pattern="test_*.py")

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print(f"\nRan {result.testsRun} tests.")
print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
