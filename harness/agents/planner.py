import json
import re
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL, LLM_BASE_URL, LLM_API_KEY, LLM_MAX_TOKENS
from harness.state import HarnessState


def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "planner.md").read_text(encoding="utf-8")


def call_llm(prompt: str) -> str:
    return ChatOpenAI(
        model=MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY, temperature=0, max_tokens=LLM_MAX_TOKENS
    ).invoke(prompt).content


def _extract_json_array(text: str) -> str:
    """從可能含有多餘文字的輸出中，抽取第一個完整的 JSON array（括號匹配）。"""
    start = text.find("[")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape_next = False
    for i, c in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def _fix_json_commas(text: str) -> str:
    """修復模型輸出中遺漏逗號的情況，例如 `}]"key"` 應為 `}],"key"`。"""
    import re
    # '}]"' or '}]  "' 之間缺少逗號
    text = re.sub(r'(\]|\})\s*"(\w)', r'\1,"\2', text)
    return text


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
    # 最多重試 3 次，直到 JSON 解析成功
    last_error = None
    for attempt in range(3):
        raw = call_llm(_load_prompt().replace("{{user_request}}", state["input"]))
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = _fix_json_commas(_extract_json_array(raw.strip()))
        try:
            tasks = json.loads(raw)
            sorted_tasks = topological_sort(tasks)
            return {"overall_goal": state["input"], "tasks": sorted_tasks,
                    "current_task_index": 0, "round": 0,
                    "evaluator_feedback": "", "completed_steps_summary": ""}
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue
    raise ValueError(f"Planner 無法產出有效 JSON（重試 3 次）：{last_error}")



