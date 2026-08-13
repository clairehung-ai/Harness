import json
import os
import tempfile
from harness.utils.logger import init_run_log, log_task_result


def test_init_run_log_creates_jsonl_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = init_run_log(tmpdir)
    assert path.endswith(".jsonl")
    assert "harness_run_" in path


def test_log_task_result_writes_entry():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = init_run_log(tmpdir)
        task = {
            "id": 1,
            "task_description": "implement add",
            "output_filename": "solution.py",
            "test_type": "unit",
        }
        state = {
            "passed": True,
            "round": 1,
            "tdd_phase": "write_code",
            "red_light_round": 0,
            "current_tests": "def test_add(): assert add(1,2)==3",
            "current_code": "def add(a,b): return a+b",
            "evaluator_feedback": "",
        }
        log_task_result(path, state, task)

        with open(path, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f]

    assert len(entries) == 1
    entry = entries[0]
    assert entry["task_id"] == 1
    assert entry["task_description"] == "implement add"
    assert entry["output_filename"] == "solution.py"
    assert entry["passed"] is True
    assert entry["forced"] is False
    assert entry["round"] == 1
    assert "def add" in entry["current_code"]
    assert "timestamp" in entry


def test_log_task_result_appends_multiple_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = init_run_log(tmpdir)
        task1 = {"id": 1, "task_description": "t1", "output_filename": "a.py", "test_type": "unit"}
        task2 = {"id": 2, "task_description": "t2", "output_filename": "b.py", "test_type": "unit"}
        state = {"passed": True, "round": 1, "tdd_phase": "write_code",
                 "red_light_round": 0, "current_tests": "", "current_code": "", "evaluator_feedback": ""}
        log_task_result(path, state, task1)
        log_task_result(path, state, task2)

        with open(path, encoding="utf-8") as f:
            entries = [json.loads(line) for line in f]

    assert len(entries) == 2
    assert entries[0]["task_id"] == 1
    assert entries[1]["task_id"] == 2


def test_log_task_result_empty_path_does_nothing():
    """log_path 為空字串時不應拋出例外"""
    task = {"id": 1, "task_description": "t", "output_filename": "s.py", "test_type": "unit"}
    state = {"passed": False, "round": 0, "tdd_phase": "write_tests",
             "red_light_round": 0, "current_tests": "", "current_code": "", "evaluator_feedback": ""}
    log_task_result("", state, task)  # 不應拋出


def test_forced_true_when_not_passed():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = init_run_log(tmpdir)
        task = {"id": 1, "task_description": "t", "output_filename": "s.py", "test_type": "unit"}
        state = {"passed": False, "round": 3, "tdd_phase": "write_code",
                 "red_light_round": 0, "current_tests": "", "current_code": "", "evaluator_feedback": "too bad"}
        log_task_result(path, state, task)

        with open(path, encoding="utf-8") as f:
            entry = json.loads(f.readline())

    assert entry["forced"] is True
    assert entry["passed"] is False
