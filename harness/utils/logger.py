"""
harness/utils/logger.py — 每個 task 完成後寫入 JSONL 記錄。

每次 run_harness() 產生一個 harness_run_<timestamp>.jsonl 檔案。
每行是一個 task 的完整執行記錄，方便 debug 和分析。
"""
import json
import os
from datetime import datetime


def init_run_log(log_dir: str = ".") -> str:
    """
    初始化一個新的 run log 檔案，回傳路徑。

    Args:
        log_dir: 存放 log 的目錄，預設為當前目錄

    Returns:
        log 檔案的完整路徑，例如 "./harness_run_20260807_103000.jsonl"
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"harness_run_{timestamp}.jsonl"
    return os.path.join(log_dir, filename)


def log_task_result(log_path: str, state: dict, task: dict) -> None:
    """
    把一個 task 的執行結果追加寫入 JSONL log 檔案。

    Args:
        log_path: log 檔案路徑（由 init_run_log 產生）
        state: HarnessState dict
        task: 當前 task dict
    """
    if not log_path:
        return

    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task.get("id"),
        "task_description": task.get("task_description", ""),
        "output_filename": task.get("output_filename", "solution.py"),
        "test_type": task.get("test_type", "unit"),
        "passed": state.get("passed", False),
        "forced": not state.get("passed", False),
        "round": state.get("round", 0),
        "tdd_phase": state.get("tdd_phase", ""),
        "red_light_round": state.get("red_light_round", 0),
        "current_tests": state.get("current_tests", ""),
        "current_code": state.get("current_code", ""),
        "evaluator_feedback": state.get("evaluator_feedback", ""),
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
