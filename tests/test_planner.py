from unittest.mock import patch
from harness.agents.planner import planner_node
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
