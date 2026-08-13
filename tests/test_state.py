from harness.state import HarnessState, Task, TaskResult

def test_task_has_required_fields():
    task: Task = {
        "id": 1,
        "task_description": "do something",
        "dependencies": [],
        "expected_output": "a function",
        "test_cases": [{"input": "x", "expected": "y"}],
        "test_type": "unit"
    }
    assert task["id"] == 1
    assert task["test_type"] == "unit"

def test_task_result_has_required_fields():
    result: TaskResult = {
        "task_id": 1, "code": "def foo(): pass",
        "tests": "def test_foo(): pass",
        "passed": True, "rating": 5, "feedback": "ok"
    }
    assert result["passed"] is True

def test_harness_state_shape():
    state: HarnessState = {
        "input": "build a calculator",
        "overall_goal": "build a calculator",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": []
    }
    assert state["current_task_index"] == 0

def test_harness_state_has_tdd_fields():
    from harness.state import HarnessState
    state: HarnessState = {
        "input": "test", "overall_goal": "test",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
    }
    assert state["tdd_phase"] == "write_tests"
    assert state["red_light_round"] == 0

def test_config_has_max_red_light_rounds():
    from harness.config import MAX_RED_LIGHT_ROUNDS
    assert MAX_RED_LIGHT_ROUNDS == 2

def test_harness_state_has_completed_code():
    from harness.state import HarnessState
    state: HarnessState = {
        "input": "test", "overall_goal": "test",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests", "red_light_round": 0,
        "completed_code": {},
    }
    assert state["completed_code"] == {}
    assert isinstance(state["completed_code"], dict)
