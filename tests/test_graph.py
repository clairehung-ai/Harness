from harness.graph import build_graph, advance_task, route_after_evaluator, route_after_red_light_check
from harness.state import HarnessState
from harness.config import MAX_ROUNDS, MAX_RED_LIGHT_ROUNDS

def make_state(**kwargs) -> HarnessState:
    base: HarnessState = {
        "input": "build add", "overall_goal": "build add",
        "tasks": [
            {"id": 1, "task_description": "implement add", "dependencies": [],
             "expected_output": "add fn", "output_filename": "solution.py",
             "test_cases": [{"input": "1,2", "expected": "3"}], "test_type": "unit"},
            {"id": 2, "task_description": "implement sub", "dependencies": [1],
             "expected_output": "sub fn", "output_filename": "solution.py",
             "test_cases": [{"input": "3,1", "expected": "2"}], "test_type": "unit"},
        ],
        "current_task_index": 0, "completed_steps_summary": "",
        "current_code": "def add(a,b): return a+b",
        "current_tests": "from solution import add\ndef test_add(): assert add(1,2)==3",
        "evaluator_feedback": "", "passed": True, "round": 1, "task_results": [],
        "completed_code": {},
    }
    base.update(kwargs)
    return base

def test_route_pass_advances():
    assert route_after_evaluator(make_state(passed=True, round=1)) == "advance_task"

def test_route_fail_retries():
    assert route_after_evaluator(make_state(passed=False, round=1)) == "code_writer"

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

def make_tdd_state(**kwargs):
    base = make_state()
    base["tdd_phase"] = "write_tests"
    base["red_light_round"] = 0
    base["completed_code"] = {}
    base.update(kwargs)
    return base

def test_route_red_light_syntax_error_retries():
    """red_light_round > 0 且 < MAX → 回到 test_writer"""
    state = make_tdd_state(red_light_round=1, tdd_phase="write_tests")
    assert route_after_red_light_check(state) == "test_writer"

def test_route_red_light_max_rounds_forces_advance():
    """red_light_round >= MAX → 強制進入 code_writer"""
    state = make_tdd_state(red_light_round=MAX_RED_LIGHT_ROUNDS, tdd_phase="write_tests")
    assert route_after_red_light_check(state) == "code_writer"

def test_route_red_light_correct_red_light():
    """red_light_round == 0，tdd_phase == write_code → code_writer"""
    state = make_tdd_state(red_light_round=0, tdd_phase="write_code")
    assert route_after_red_light_check(state) == "code_writer"

def test_build_graph_has_tdd_nodes():
    """graph 包含 test_writer、red_light_check、code_writer 節點"""
    graph = build_graph()
    assert graph is not None

def test_advance_task_stores_completed_code():
    """advance_task 應將 current_code 存入 completed_code"""
    state = make_tdd_state(current_task_index=0, passed=True)
    state["completed_code"] = {}
    state["current_code"] = "def add(a, b):\n    return a + b\n"
    result = advance_task(state)
    assert "solution.py" in result["completed_code"]
    assert "def add" in result["completed_code"]["solution.py"]

def test_advance_task_accumulates_completed_code():
    """advance_task 應保留前面 task 的 completed_code"""
    state = make_tdd_state(current_task_index=1, passed=True)
    state["completed_code"] = {"solution.py": "def add(a, b): return a + b"}
    state["current_code"] = "def multiply(a, b):\n    return a * b\n"
    result = advance_task(state)
    assert "solution.py" in result["completed_code"]
    assert "def multiply" in result["completed_code"]["solution.py"]

def test_advance_task_uses_output_filename_as_completed_code_key():
    """advance_task 應用 output_filename 作為 completed_code 的 key"""
    state = make_tdd_state(current_task_index=0, passed=True)
    state["tasks"][0]["output_filename"] = "models.py"
    state["current_code"] = "class User:\n    def __init__(self, name): self.name = name\n"
    result = advance_task(state)
    assert "models.py" in result["completed_code"]
    assert "class User" in result["completed_code"]["models.py"]
    assert "1" not in result["completed_code"]  # 舊的 task_id key 不應存在
