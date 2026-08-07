import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PytestRunner(BaseRunner):
    """pytest Skill Runner，支援 unit / api / integration 三種模式。"""

    VALID_MODES = ("unit", "api", "integration")

    def __init__(self, mode: str = "unit"):
        if mode not in self.VALID_MODES:
            raise ValueError(f"不支援的模式：{mode}，合法值為 {self.VALID_MODES}")
        self.mode = mode

    def run(self, code: str, tests: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "solution.py"), "w", encoding="utf-8") as f:
                f.write(code)
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT, cwd=tmpdir,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: 測試執行超過時間限制"}
            except Exception as e:
                return {"success": False, "output": f"runner 錯誤: {e}"}
