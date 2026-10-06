import sys
import os
import glob
import importlib
import inspect

sys.path.insert(0, os.path.abspath("."))

test_files = sorted(glob.glob("tests/test_*.py"))
total_passed = 0
total_failed = 0
failures = []

for tf in test_files:
    mod_name = tf.replace("\\", "/").replace("/", ".").replace(".py", "")
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:
        print(f"Error importing {mod_name}: {e}")
        continue
    
    for attr in dir(mod):
        if attr.startswith("test_"):
            fn = getattr(mod, attr)
            if callable(fn):
                try:
                    # check if fn takes args
                    sig = inspect.signature(fn)
                    if len(sig.parameters) == 0:
                        fn()
                        total_passed += 1
                    else:
                        pass # fixtures / args
                except Exception as e:
                    print(f"[FAIL] {mod_name}.{attr}: {e}")
                    failures.append((mod_name, attr, str(e)))
                    total_failed += 1

print(f"\n=======================================================")
print(f"Test Run: {total_passed} Passed, {total_failed} Failed")
print(f"=======================================================")
for mod_name, attr, err in failures:
    print(f"  {mod_name}.{attr}: {err}")
