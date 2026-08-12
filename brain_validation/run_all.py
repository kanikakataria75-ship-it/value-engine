import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
tests = sorted(ROOT.glob("test_*.py"))

passed = 0
failed = 0

print("=" * 70)
print("VALUENGINE BRAIN VALIDATION")
print("=" * 70)

for test in tests:
    print(f"\n>>> RUNNING: {test.name}")
    result = subprocess.run(
        [sys.executable, str(test)],
        cwd=ROOT.parent,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("PASS")
        passed += 1
    else:
        print("FAIL")
        failed += 1

    if result.stdout:
        print(result.stdout.strip())

    if result.stderr:
        print("STDERR:")
        print(result.stderr.strip())

print("\n" + "=" * 70)
print("FINAL VALIDATION SUMMARY")
print("=" * 70)
print(f"Total:  {len(tests)}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed == 0:
    print("\nALL BRAIN VALIDATION TESTS PASSED")
    sys.exit(0)
else:
    print("\nSOME TESTS FAILED")
    sys.exit(1)
