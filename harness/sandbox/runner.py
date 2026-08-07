import subprocess, tempfile, os
from harness.config import SANDBOX_TIMEOUT

def run_tests(code: str, tests: str) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "solution.py"), "w") as f:
            f.write(code)
        with open(os.path.join(tmpdir, "test_solution.py"), "w") as f:
            f.write(tests)
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
                capture_output=True, text=True,
                timeout=SANDBOX_TIMEOUT, cwd=tmpdir,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "timeout: exceeded time limit"}
        except Exception as e:
            return {"success": False, "output": f"runner error: {e}"}
