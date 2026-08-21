import json
import re
import os
from pathlib import Path
from harness.config import call_llm_with_retry
from harness.state import HarnessState

# 掃描時忽略的目錄和檔案
_IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", "tests", "dist", "build", ".venv", "venv"}
_IGNORE_EXTS = {".pyc", ".pyo", ".log", ".jsonl", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".ico"}
_CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".txt", ".toml"}
_PREVIEW_LINES = 15  # 每個檔案預覽幾行


def _scan_project_structure(export_dir: str) -> str:
    """掃描現有專案目錄，產生結構描述供 Planner 參考。

    回傳格式：
    - 目錄樹（只列檔名）
    - 每個程式碼檔案的前 N 行預覽

    若 export_dir 不存在或是空目錄，回傳空字串。
    """
    root = Path(export_dir)
    if not root.exists() or not root.is_dir():
        return ""

    # 收集所有相關檔案（排除忽略清單）
    files = []
    for item in sorted(root.rglob("*")):
        # 跳過忽略目錄
        if any(part in _IGNORE_DIRS for part in item.parts):
            continue
        if item.is_file() and item.suffix in _CODE_EXTS:
            files.append(item)

    if not files:
        return ""

    lines = ["## 現有專案結構\n"]
    lines.append(f"目標目錄：`{export_dir}`\n")
    lines.append("```")

    # 目錄樹
    for f in files:
        rel = f.relative_to(root)
        lines.append(str(rel).replace("\\", "/"))
    lines.append("```\n")

    # 每個檔案的前幾行預覽
    lines.append("### 現有檔案內容預覽\n")
    for f in files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        try:
            content_lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            preview = content_lines[:_PREVIEW_LINES]
            lines.append(f"**{rel}**（前 {len(preview)} 行）：")
            lines.append("```")
            lines.extend(preview)
            lines.append("```\n")
        except Exception:
            lines.append(f"**{rel}**：（無法讀取）\n")

    return "\n".join(lines)



def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "planner.md").read_text(encoding="utf-8")


def call_llm(prompt: str) -> str:
    return call_llm_with_retry(prompt)


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
    base_prompt = _load_prompt()

    # 掃描現有專案結構並注入 prompt
    export_dir = state.get("export_dir", "")
    project_context = ""
    if export_dir:
        project_context = _scan_project_structure(export_dir)

    if project_context:
        prompt_with_context = base_prompt.replace(
            "## 使用者需求",
            f"{project_context}\n---\n\n## 使用者需求"
        ).replace("{{user_request}}", state["input"])
    else:
        prompt_with_context = base_prompt.replace("{{user_request}}", state["input"])

    # 最多重試 3 次，直到 JSON 解析成功
    last_error = None
    for attempt in range(3):
        raw = call_llm(prompt_with_context)
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



