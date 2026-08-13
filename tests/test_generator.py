from unittest.mock import patch
from harness.agents.generator import generator_node, test_writer_node, red_light_check_node, code_writer_node
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

def test_red_light_check_correct_red_light():
    """ImportError = 正確紅燈，進入 write_code"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    state["red_light_round"] = 0
    mock_run = {"success": False, "output": "ImportError: No module named 'solution'"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["tdd_phase"] == "write_code"
    assert result["red_light_round"] == 0
    assert result["evaluator_feedback"] == ""

def test_red_light_check_syntax_error():
    """SyntaxError = tests 寫壞，增加 red_light_round"""
    state = make_state()
    state["current_tests"] = "def test_bad(\n    pass\n"
    state["red_light_round"] = 0
    mock_run = {"success": False, "output": "SyntaxError: invalid syntax"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["red_light_round"] == 1
    assert "SyntaxError" in result["evaluator_feedback"]
    assert "tdd_phase" not in result

def test_red_light_check_weak_tests():
    """所有測試通過（弱測試），記錄警告並繼續"""
    state = make_state()
    state["current_tests"] = "def test_always_pass():\n    assert True\n"
    state["red_light_round"] = 0
    mock_run = {"success": True, "output": "1 passed"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["tdd_phase"] == "write_code"
    assert result["red_light_round"] == 0
    assert "警告" in result["evaluator_feedback"]

MOCK_CODE_ONLY = "```implementation\ndef add(a, b):\n    return a + b\n```"

def test_code_writer_returns_code_only():
    """code_writer_node 只產出 current_code，不改 current_tests"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE_ONLY):
        result = code_writer_node(state)
    assert "def add" in result["current_code"]
    assert result["tdd_phase"] == "write_code"
    assert "current_tests" not in result  # 不改動 current_tests

def test_code_writer_injects_current_tests_into_prompt():
    """current_tests 被注入 prompt"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add(): assert add(1,2)==3\n"
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_CODE_ONLY
    with patch("harness.agents.generator.call_code_writer_llm", side_effect=capture):
        code_writer_node(state)
    assert "from solution import add" in captured[0]
    assert "{{current_tests}}" not in captured[0]

def test_code_writer_strips_fences():
    state = make_state()
    state["current_tests"] = "def test_f(): pass\n"
    with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE_ONLY):
        result = code_writer_node(state)
    assert "```" not in result["current_code"]
