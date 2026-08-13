import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL
from harness.state import HarnessState


def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "planner.md").read_text(encoding="utf-8")


def call_llm(prompt: str) -> str:
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content


def topological_sort(tasks: list) -> list:
    """
    依照 dependencies 欄位做拓撲排序，確保每個 task 在其依賴的 task 之後執行。

    Args:
        tasks: Planner 產出的 task list，每個 task 有 id 和 dependencies

    Returns:
        排序後的 task list

    Raises:
        ValueError: 若存在循環依賴
    """
    id_to_task = {task["id"]: task for task in tasks}
    visited = set()
    result = []

    def visit(task_id: int, visiting: set):
        if task_id in visiting:
            raise ValueError(f"循環依賴：task {task_id} 形成循環")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep_id in id_to_task[task_id].get("dependencies", []):
            if dep_id not in id_to_task:
                raise ValueError(f"task {task_id} 依賴不存在的 task {dep_id}")
            visit(dep_id, visiting)
        visiting.discard(task_id)
        visited.add(task_id)
        result.append(id_to_task[task_id])

    for task in tasks:
        visit(task["id"], set())

    return result


def planner_node(state: HarnessState) -> dict:
    raw = call_llm(_load_prompt().replace("{{user_request}}", state["input"]))
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    tasks = json.loads(raw.strip())
    sorted_tasks = topological_sort(tasks)
    return {"overall_goal": state["input"], "tasks": sorted_tasks,
            "current_task_index": 0, "round": 0,
            "evaluator_feedback": "", "completed_steps_summary": ""}
