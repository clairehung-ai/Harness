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
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is True

def test_fail_when_tests_fail():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": False, "output": "AssertionError"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=FAIL_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is False
    assert result["evaluator_feedback"] != ""

def test_increments_round():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state(round=1))
    assert result["round"] == 2

def test_evaluator_routes_to_skill_runner():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["test_type"] = "unit"
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(state)
    mock_runner.run.assert_called_once()
    assert result["passed"] is True

def test_evaluator_auto_detects():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["test_type"] = "auto"
    state["current_code"] = "def add(a, b): return a + b"
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.detect_test_type", return_value="unit") as mock_detect:
        with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
            with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
                result = evaluator_node(state)
    mock_detect.assert_called_once_with(state["current_code"])
    assert result["passed"] is True

def test_evaluator_passes_completed_code_to_runner():
    """evaluator 應把 completed_code 和 output_filename 傳給 runner"""
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["output_filename"] = "services.py"
    state["completed_code"] = {"models.py": "class User: pass"}
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            evaluator_node(state)
    call_kwargs = mock_runner.run.call_args
    assert call_kwargs.kwargs.get("completed_code") == {"models.py": "class User: pass"} or \
           (len(call_kwargs.args) >= 3 and call_kwargs.args[2] == {"models.py": "class User: pass"})

def test_evaluator_missing_test_type_fallbacks():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0].pop("test_type", None)
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.detect_test_type", return_value="unit"):
        with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
            with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
                result = evaluator_node(state)
    assert result["passed"] is True
