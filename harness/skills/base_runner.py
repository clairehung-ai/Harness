from abc import ABC, abstractmethod


class BaseRunner(ABC):
    """所有測試 Skill Runner 的抽象基底類別。"""

    @abstractmethod
    def run(self, code: str, tests: str) -> dict:
        """
        執行測試並回傳結果。
        Returns: {"success": bool, "output": str}
        """
        ...


def detect_test_type(code: str) -> str:
    """
    根據代碼內容自動偵測測試類型。
    優先順序：e2e_ui > api > integration > unit
    """
    if any(s in code for s in ["playwright", "from playwright", "Page"]):
        return "e2e_ui"
    if any(s in code for s in ["from fastapi", "FastAPI(", "from flask", "Flask("]):
        return "api"
    integration_signals = ["sqlite3", "sqlalchemy", "open(", "csv"]
    if any(s in code for s in integration_signals) and code.count("import ") >= 2:
        return "integration"
    return "unit"


def get_runner(test_type: str) -> "BaseRunner":
    """根據 test_type 回傳對應 Runner，未知類型 fallback 到 unit。"""
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.playwright_runner.playwright_runner import PlaywrightRunner

    if test_type == "e2e_ui":
        return PlaywrightRunner()
    elif test_type in ("unit", "api", "integration"):
        return PytestRunner(mode=test_type)
    else:
        return PytestRunner(mode="unit")
