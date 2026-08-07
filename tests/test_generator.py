from unittest.mock import patch
from harness.agents.generator import generator_node
from harness.state import HarnessState

def make_state() -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}]}],
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
