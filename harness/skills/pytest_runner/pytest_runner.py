import subprocess, tempfile, os, sys, shutil
from pathlib import Path
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT

# 複製現有專案時忽略的目錄
_IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", "dist", "build"}
_IGNORE_EXTS = {".pyc", ".pyo", ".log", ".jsonl", ".zip"}


class PytestRunner(BaseRunner):
    """pytest Skill Runner，支援 unit / api / integration 三種模式。"""

    VALID_MODES = ("unit", "api", "integration")

    def __init__(self, mode: str = "unit"):
        if mode not in self.VALID_MODES:
            raise ValueError(f"不支援的模式：{mode}，合法值為 {self.VALID_MODES}")
        self.mode = mode

    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.py", export_dir: str = "") -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 0. 若有現有專案目錄，先把現有檔案複製進 tmpdir（讓測試可以 import 現有 code）
            if export_dir and os.path.isdir(export_dir):
                for item in Path(export_dir).rglob("*"):
                    if item.is_file():
                        # 跳過忽略的目錄和副檔名
                        if any(part in _IGNORE_DIRS for part in item.parts):
                            continue
                        if item.suffix in _IGNORE_EXTS:
                            continue
                        rel = item.relative_to(export_dir)
                        dst = Path(tmpdir) / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dst)

            # 1. 寫入所有已完成的檔案（覆蓋現有檔案，確保用最新生成版本）
            for filename, file_code in (completed_code or {}).items():
                dst = os.path.join(tmpdir, filename)
                os.makedirs(os.path.dirname(dst), exist_ok=True) if os.path.dirname(dst) else None
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(file_code)

            # 2. 寫入當前代碼（用 output_filename，覆蓋）
            dst = os.path.join(tmpdir, output_filename)
            if os.path.dirname(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(code)

            # 3. 寫入測試
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
