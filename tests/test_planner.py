from unittest.mock import patch
from harness.agents.planner import planner_node, topological_sort
from harness.state import HarnessState

def make_state(user_input="build an add function") -> HarnessState:
    return {"input": user_input, "overall_goal": "", "tasks": [],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "", "current_tests": "", "evaluator_feedback": "",
            "passed": False, "round": 0, "task_results": []}

MOCK = '[{"id":1,"task_description":"implement add","dependencies":[],"expected_output":"add fn","test_cases":[{"input":"1,2","expected":"3"}]}]'

def test_planner_returns_tasks():
    with patch("harness.agents.planner.call_llm", return_value=MOCK):
        result = planner_node(make_state())
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["id"] == 1
    assert result["current_task_index"] == 0

def test_planner_sets_overall_goal():
    with patch("harness.agents.planner.call_llm", return_value=MOCK):
        result = planner_node(make_state())
    assert result["overall_goal"] == "build an add function"

# --- topological_sort 測試 ---

def make_task(id, deps=None, desc=""):
    return {"id": id, "task_description": desc or f"task {id}",
            "dependencies": deps or [], "expected_output": "",
            "output_filename": "solution.py", "test_cases": [], "test_type": "unit"}

def test_topological_sort_no_deps():
    tasks = [make_task(1), make_task(2), make_task(3)]
    result = topological_sort(tasks)
    assert [t["id"] for t in result] == [1, 2, 3]

def test_topological_sort_linear_deps():
    """Task 3 依賴 2，Task 2 依賴 1 → 順序必須是 1, 2, 3"""
    tasks = [make_task(3, [2]), make_task(1), make_task(2, [1])]
    result = topological_sort(tasks)
    ids = [t["id"] for t in result]
    assert ids.index(1) < ids.index(2)
    assert ids.index(2) < ids.index(3)

def test_topological_sort_diamond_deps():
    """Task 4 依賴 2 和 3，Task 2 和 3 都依賴 1"""
    tasks = [make_task(4, [2, 3]), make_task(2, [1]), make_task(3, [1]), make_task(1)]
    result = topological_sort(tasks)
    ids = [t["id"] for t in result]
    assert ids.index(1) < ids.index(2)
    assert ids.index(1) < ids.index(3)
    assert ids.index(2) < ids.index(4)
    assert ids.index(3) < ids.index(4)

def test_topological_sort_already_correct_order():
    tasks = [make_task(1), make_task(2, [1]), make_task(3, [2])]
    result = topological_sort(tasks)
    ids = [t["id"] for t in result]
    assert ids.index(1) < ids.index(2) < ids.index(3)

def test_topological_sort_raises_on_cycle():
    import pytest
    tasks = [make_task(1, [2]), make_task(2, [1])]
    with pytest.raises(ValueError, match="循環依賴"):
        topological_sort(tasks)

def test_topological_sort_raises_on_missing_dep():
    import pytest
    tasks = [make_task(1, [99])]
    with pytest.raises(ValueError, match="不存在的 task 99"):
        topological_sort(tasks)

def test_planner_sorts_tasks_by_dependency():
    """planner_node 應回傳依賴排序後的 tasks"""
    mock = '[{"id":3,"task_description":"t3","dependencies":[2],"expected_output":"","output_filename":"solution.py","test_cases":[],"test_type":"unit"},{"id":1,"task_description":"t1","dependencies":[],"expected_output":"","output_filename":"solution.py","test_cases":[],"test_type":"unit"},{"id":2,"task_description":"t2","dependencies":[1],"expected_output":"","output_filename":"solution.py","test_cases":[],"test_type":"unit"}]'
    with patch("harness.agents.planner.call_llm", return_value=mock):
        result = planner_node(make_state())
    ids = [t["id"] for t in result["tasks"]]
    assert ids.index(1) < ids.index(2)
    assert ids.index(2) < ids.index(3)
