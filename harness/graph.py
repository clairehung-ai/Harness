from langgraph.graph import StateGraph, END
from harness.state import HarnessState, TaskResult
from harness.agents.planner import planner_node
from harness.agents.generator import generator_node
from harness.agents.evaluator import evaluator_node
from harness.config import MAX_ROUNDS

def route_after_evaluator(state: HarnessState) -> str:
    if state["passed"] or state["round"] >= MAX_ROUNDS:
        return "advance_task"
    return "generator"

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
    }

def route_after_advance(state: HarnessState) -> str:
    if state["current_task_index"] >= len(state["tasks"]):
        return END
    return "generator"

def build_graph():
    g = StateGraph(HarnessState)
    g.add_node("planner", planner_node)
    g.add_node("generator", generator_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("advance_task", advance_task)
    g.set_entry_point("planner")
    g.add_edge("planner", "generator")
    g.add_edge("generator", "evaluator")
    g.add_conditional_edges("evaluator", route_after_evaluator,
                             {"advance_task": "advance_task", "generator": "generator"})
    g.add_conditional_edges("advance_task", route_after_advance,
                             {"generator": "generator", END: END})
    return g.compile()
