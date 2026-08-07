from unittest.mock import patch
from harness.agents.evaluator import evaluator_node
from harness.state import HarnessState

def make_state(round=1) -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}]}],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "def add(a,b): return a+b",
            "current_tests": "from solution import add\ndef test_add():\n    assert add(1,2)==3\n",
            "evaluator_feedback": "", "passed": False,
            "round": round, "task_results": []}

PASS_JSON = '{"is_success": true, "rating": 5, "feedback": "All good"}'
FAIL_JSON = '{"is_success": false, "rating": 2, "feedback": "Missing error handling"}'

def test_pass_when_tests_pass():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": True, "output": "1 passed"}):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is True

def test_fail_when_tests_fail():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": False, "output": "AssertionError"}):
        with patch("harness.agents.evaluator.call_llm", return_value=FAIL_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is False
    assert result["evaluator_feedback"] != ""

def test_increments_round():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": True, "output": "1 passed"}):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state(round=1))
    assert result["round"] == 2
