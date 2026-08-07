from harness.state import HarnessState, Task, TaskResult

def test_task_has_required_fields():
    task: Task = {
        "id": 1,
        "task_description": "do something",
        "dependencies": [],
        "expected_output": "a function",
        "test_cases": [{"input": "x", "expected": "y"}]
    }
    assert task["id"] == 1

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
