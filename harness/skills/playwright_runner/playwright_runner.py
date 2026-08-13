import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PlaywrightRunner(BaseRunner):
    """Playwright headless chromium E2E UI 測試 Skill Runner。"""

    def _is_html(self, code: str) -> bool:
        stripped = code.strip().lower()
        return stripped.startswith("<!doctype html") or stripped.startswith("<html")

    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.html") -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 寫入所有已完成的檔案
            for filename, file_code in (completed_code or {}).items():
                with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                    f.write(file_code)
            # 2. 寫入當前代碼（HTML 或 Python）
            actual_filename = output_filename if output_filename else (
                "solution.html" if self._is_html(code) else "solution.py"
            )
            with open(os.path.join(tmpdir, actual_filename), "w", encoding="utf-8") as f:
                f.write(code)
            # 3. 寫入測試
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                # Check pytest-playwright is available
                check = subprocess.run(
                    [sys.executable, "-m", "pytest", "--co", "-q", "--browser", "chromium", "test_solution.py"],
                    capture_output=True, text=True, timeout=10, cwd=tmpdir,
                )
                if "unrecognized arguments" in check.stderr or "unrecognized arguments" in check.stdout:
                    return {
                        "success": False,
                        "output": "playwright runner 錯誤: pytest-playwright 未安裝在當前 Python 環境。請執行：pip install pytest-playwright && python -m playwright install chromium"
                    }
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
