import subprocess, tempfile, os, sys, shutil
from pathlib import Path
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PlaywrightRunner(BaseRunner):
    """Playwright headless chromium E2E UI 測試 Skill Runner。"""

    def _is_html(self, code: str) -> bool:
        stripped = code.strip().lower()
        return stripped.startswith("<!doctype html") or stripped.startswith("<html")

    def run(self, code: str, tests: str, completed_code: dict = None, output_filename: str = "solution.html", export_dir: str = "") -> dict:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            # 0. 若有現有專案目錄，先複製進 tmpdir
            if export_dir and os.path.isdir(export_dir):
                _IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
                _IGNORE_EXTS = {".pyc", ".pyo", ".log", ".jsonl", ".zip"}
                for item in Path(export_dir).rglob("*"):
                    if item.is_file():
                        if any(part in _IGNORE_DIRS for part in item.parts):
                            continue
                        if item.suffix in _IGNORE_EXTS:
                            continue
                        rel = item.relative_to(export_dir)
                        dst = Path(tmpdir) / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dst)

            # 1. 寫入已完成的檔案
            for filename, file_code in (completed_code or {}).items():
                with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                    f.write(file_code)

            # 2. 寫入當前代碼
            actual_filename = output_filename if output_filename else (
                "solution.html" if self._is_html(code) else "solution.py"
            )
            with open(os.path.join(tmpdir, actual_filename), "w", encoding="utf-8") as f:
                f.write(code)

            # 3. 寫入測試
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)

            # 4. 截圖和報告目錄
            screenshots_dir = os.path.join(tmpdir, "screenshots")
            report_path = os.path.join(tmpdir, "report.html")
            os.makedirs(screenshots_dir, exist_ok=True)

            try:
                # 確認 pytest-playwright 可用
                check = subprocess.run(
                    [sys.executable, "-m", "pytest", "--co", "-q", "--browser", "chromium", "test_solution.py"],
                    capture_output=True, text=True, timeout=10, cwd=tmpdir,
                )
                if "unrecognized arguments" in check.stderr or "unrecognized arguments" in check.stdout:
                    return {
                        "success": False,
                        "output": "playwright runner 錯誤: pytest-playwright 未安裝。請執行：pip install pytest-playwright && python -m playwright install chromium",
                        "screenshots_dir": "",
                        "report_path": "",
                    }

                result = subprocess.run(
                    [
                        sys.executable, "-m", "pytest", "test_solution.py",
                        "-v", "--tb=short",
                        "--browser", "chromium",
                        "--screenshot=on",                        # 每個測試截圖
                        "--output", screenshots_dir,              # 截圖存放位置
                        f"--html={report_path}",                  # HTML 報告
                        "--self-contained-html",                   # 報告內嵌資源
                    ],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT * 3,
                    cwd=tmpdir,
                )

                # 把截圖和報告複製到持久目錄（tmpdir 會被清除）
                artifacts_dir = os.path.join(os.getcwd(), "test_artifacts")
                os.makedirs(artifacts_dir, exist_ok=True)

                saved_screenshots = []
                if os.path.isdir(screenshots_dir):
                    dst_screenshots = os.path.join(artifacts_dir, "screenshots")
                    if os.path.exists(dst_screenshots):
                        shutil.rmtree(dst_screenshots)
                    shutil.copytree(screenshots_dir, dst_screenshots)
                    saved_screenshots = [
                        os.path.join(dst_screenshots, f)
                        for f in os.listdir(dst_screenshots)
                        if f.endswith(".png")
                    ]

                saved_report = ""
                if os.path.exists(report_path):
                    saved_report = os.path.join(artifacts_dir, "report.html")
                    shutil.copy2(report_path, saved_report)

                output = result.stdout + result.stderr
                if saved_screenshots:
                    output += f"\n\n📸 截圖已儲存：{len(saved_screenshots)} 張 → {artifacts_dir}/screenshots/"
                if saved_report:
                    output += f"\n📄 HTML 報告：{saved_report}"

                return {
                    "success": result.returncode == 0,
                    "output": output,
                    "screenshots_dir": os.path.join(artifacts_dir, "screenshots") if saved_screenshots else "",
                    "report_path": saved_report,
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: Playwright 測試超過時間限制", "screenshots_dir": "", "report_path": ""}
            except Exception as e:
                return {"success": False, "output": f"playwright runner 錯誤: {e}", "screenshots_dir": "", "report_path": ""}
