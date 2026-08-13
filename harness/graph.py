from langgraph.graph import StateGraph, END
from harness.state import HarnessState, TaskResult
from harness.agents.planner import planner_node
from harness.agents.generator import test_writer_node, red_light_check_node, code_writer_node
from harness.agents.evaluator import evaluator_node
from harness.config import MAX_ROUNDS, MAX_RED_LIGHT_ROUNDS


def route_after_red_light_check(state: HarnessState) -> str:
    """條件邊：red_light_check 後決定走 test_writer 還是 code_writer。"""
    if state["red_light_round"] > 0 and state["red_light_round"] < MAX_RED_LIGHT_ROUNDS:
        return "test_writer"
    return "code_writer"


def route_after_evaluator(state: HarnessState) -> str:
    if state["passed"] or state["round"] >= MAX_ROUNDS:
        return "advance_task"
    return "code_writer"


def advance_task(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    status = "PASSED" if state["passed"] else "FORCED"
    summary = f"{state['completed_steps_summary']}\n- Task {task['id']}: {task['task_description']} [{status}]".strip()
    result: TaskResult = {
        "task_id": task["id"], "code": state["current_code"],
        "tests": state["current_tests"], "passed": state["passed"],
        "rating": 0, "feedback": state["evaluator_feedback"],
    }
    return {
        "current_task_index": state["current_task_index"] + 1,
        "round": 0, "evaluator_feedback": "",
        "current_code": "", "current_tests": "",
        "passed": False, "completed_steps_summary": summary,
        "task_results": list(state["task_results"]) + [result],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
    }


def route_after_advance(state: HarnessState) -> str:
    if state["current_task_index"] >= len(state["tasks"]):
        return END
    return "test_writer"


def build_graph():
    g = StateGraph(HarnessState)
    g.add_node("planner", planner_node)
    g.add_node("test_writer", test_writer_node)
    g.add_node("red_light_check", red_light_check_node)
    g.add_node("code_writer", code_writer_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("advance_task", advance_task)

    g.set_entry_point("planner")
    g.add_edge("planner", "test_writer")
    g.add_edge("test_writer", "red_light_check")
    g.add_conditional_edges("red_light_check", route_after_red_light_check,
                             {"test_writer": "test_writer", "code_writer": "code_writer"})
    g.add_edge("code_writer", "evaluator")
    g.add_conditional_edges("evaluator", route_after_evaluator,
                             {"advance_task": "advance_task", "code_writer": "code_writer"})
    g.add_conditional_edges("advance_task", route_after_advance,
                             {"test_writer": "test_writer", END: END})
    return g.compile()
