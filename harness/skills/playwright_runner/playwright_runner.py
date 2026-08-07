import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PlaywrightRunner(BaseRunner):
    """Playwright headless chromium E2E UI 測試 Skill Runner。"""

    def _is_html(self, code: str) -> bool:
        stripped = code.strip().lower()
        return stripped.startswith("<!doctype html") or stripped.startswith("<html")

    def run(self, code: str, tests: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = "solution.html" if self._is_html(code) else "solution.py"
            with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                f.write(code)
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short", "--browser", "chromium"],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT * 3,
                    cwd=tmpdir,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: Playwright 測試超過時間限制"}
            except Exception as e:
                return {"success": False, "output": f"playwright runner 錯誤: {e}"}
