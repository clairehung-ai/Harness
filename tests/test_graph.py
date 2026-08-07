from harness.graph import build_graph, advance_task, route_after_evaluator
from harness.state import HarnessState
from harness.config import MAX_ROUNDS

def make_state(**kwargs) -> HarnessState:
    base: HarnessState = {
        "input": "build add", "overall_goal": "build add",
        "tasks": [
            {"id": 1, "task_description": "implement add", "dependencies": [],
             "expected_output": "add fn", "test_cases": [{"input": "1,2", "expected": "3"}]},
            {"id": 2, "task_description": "implement sub", "dependencies": [1],
             "expected_output": "sub fn", "test_cases": [{"input": "3,1", "expected": "2"}]},
        ],
        "current_task_index": 0, "completed_steps_summary": "",
        "current_code": "def add(a,b): return a+b",
        "current_tests": "from solution import add\ndef test_add(): assert add(1,2)==3",
        "evaluator_feedback": "", "passed": True, "round": 1, "task_results": [],
    }
    base.update(kwargs)
    return base

def test_route_pass_advances():
    assert route_after_evaluator(make_state(passed=True, round=1)) == "advance_task"

def test_route_fail_retries():
    assert route_after_evaluator(make_state(passed=False, round=1)) == "generator"

def test_route_max_rounds_forces_advance():
    assert route_after_evaluator(make_state(passed=False, round=MAX_ROUNDS)) == "advance_task"

def test_advance_task_increments_index():
    result = advance_task(make_state(current_task_index=0))
    assert result["current_task_index"] == 1
    assert result["round"] == 0
    assert result["evaluator_feedback"] == ""

def test_advance_task_updates_summary():
    result = advance_task(make_state(current_task_index=0))
    assert "implement add" in result["completed_steps_summary"]

def test_build_graph_returns_compiled_graph():
    assert build_graph() is not None
