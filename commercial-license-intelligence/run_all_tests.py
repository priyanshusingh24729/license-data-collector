"""
run_all_tests.py
----------------
Runs pytest-style and unittest-style tests directly in Python.
"""

import sys
import os
import inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def run_tests():
    from tests import (
        test_installation_csv_pipeline,
        test_backend_quality_step22,
        test_bulk_upload_pipeline,
        test_apple_and_linux_data_quality,
        test_data_accuracy_elevation,
    )

    modules = [
        test_apple_and_linux_data_quality,
        test_backend_quality_step22,
        test_installation_csv_pipeline,
        test_bulk_upload_pipeline,
        test_data_accuracy_elevation,
    ]
    total_passed = 0
    total_failed = 0

    for mod in modules:
        print(f"\nRunning tests in {mod.__name__}...")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if inspect.isclass(obj) and attr_name.startswith("Test") and getattr(obj, "__module__", "") == mod.__name__:
                instance = obj()
                for m_name in dir(instance):
                    if m_name.startswith("test_"):
                        fn = getattr(instance, m_name)
                        if callable(fn):
                            try:
                                fn()
                                print(f"  [PASS] {attr_name}.{m_name}")
                                total_passed += 1
                            except Exception as e:
                                print(f"  [FAIL] {attr_name}.{m_name}: {e}")
                                total_failed += 1
            elif attr_name.startswith("test_") and callable(obj):
                try:
                    obj()
                    print(f"  [PASS] {attr_name}")
                    total_passed += 1
                except Exception as e:
                    print(f"  [FAIL] {attr_name}: {e}")
                    total_failed += 1

    print(f"\n=======================================================")
    print(f"Test Summary: {total_passed} Passed, {total_failed} Failed")
    print(f"=======================================================\n")

if __name__ == "__main__":
    run_tests()
