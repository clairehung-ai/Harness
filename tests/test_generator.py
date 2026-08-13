from unittest.mock import patch
from harness.agents.generator import generator_node, test_writer_node
from harness.state import HarnessState

def make_state(test_type: str = "unit") -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}],
                        "test_type": test_type}],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "", "current_tests": "",
            "evaluator_feedback": "", "passed": False,
            "round": 0, "task_results": []}

MOCK = "```implementation\ndef add(a, b):\n    return a + b\n```\n\n```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"

def test_returns_code_and_tests():
    with patch("harness.agents.generator.call_llm", return_value=MOCK):
        result = generator_node(make_state())
    assert "def add" in result["current_code"]
    assert "def test_add" in result["current_tests"]

def test_strips_fences():
    with patch("harness.agents.generator.call_llm", return_value=MOCK):
        result = generator_node(make_state())
    assert "```" not in result["current_code"]
    assert "```" not in result["current_tests"]

def test_test_type_injected_into_prompt():
    """確認 test_type 被正確注入 prompt"""
    captured_prompt = []
    def capture_llm(prompt: str) -> str:
        captured_prompt.append(prompt)
        return MOCK
    with patch("harness.agents.generator.call_llm", side_effect=capture_llm):
        generator_node(make_state(test_type="api"))
    assert "api" in captured_prompt[0]
    assert "{{test_type}}" not in captured_prompt[0]

def test_test_type_defaults_to_unit_when_missing():
    """task 沒有 test_type 時，預設注入 unit"""
    state = make_state()
    state["tasks"][0].pop("test_type", None)
    captured_prompt = []
    def capture_llm(prompt: str) -> str:
        captured_prompt.append(prompt)
        return MOCK
    with patch("harness.agents.generator.call_llm", side_effect=capture_llm):
        generator_node(state)
    assert "unit" in captured_prompt[0]

MOCK_TESTS_ONLY = "```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"

def test_test_writer_returns_tests_only():
    """test_writer_node 只產出 current_tests，不產出 current_code"""
    with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS_ONLY):
        result = test_writer_node(make_state())
    assert "def test_add" in result["current_tests"]
    assert result["current_code"] == ""
    assert result["tdd_phase"] == "write_tests"
    assert result["passed"] is False

def test_test_writer_strips_fences():
    with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS_ONLY):
        result = test_writer_node(make_state())
    assert "```" not in result["current_tests"]

def test_test_writer_injects_red_light_feedback():
    """red_light_feedback 被注入 prompt"""
    state = make_state()
    state["evaluator_feedback"] = "SyntaxError on line 3"
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_TESTS_ONLY
    with patch("harness.agents.generator.call_test_writer_llm", side_effect=capture):
        test_writer_node(state)
    assert "SyntaxError on line 3" in captured[0]
