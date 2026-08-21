import re, json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import call_llm_with_retry, MAX_RED_LIGHT_ROUNDS
from harness.state import HarnessState
from harness.skills.base_runner import detect_test_type, get_runner

def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "generator.md").read_text(encoding="utf-8")

def call_llm(prompt: str) -> str:
    return call_llm_with_retry(prompt)

def _extract_block(text: str, label: str) -> str:
    m = re.search(rf"```{label}\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if label == "implementation" and blocks:
        return blocks[0].strip()
    if label == "tests":
        if len(blocks) >= 2:
            return blocks[1].strip()
        if len(blocks) == 1:
            # test_writer 只輸出一個 block，直接取（不論標籤是 tests 或 python）
            return blocks[0].strip()
    return ""

def generator_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{completed_steps_summary}}", state["completed_steps_summary"] or "None")
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_cases}}", json.dumps(task["test_cases"], indent=2))
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_llm(prompt)
    return {"current_code": _extract_block(raw, "implementation"),
            "current_tests": _extract_block(raw, "tests")}

def _load_test_writer_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "test_writer.md").read_text(encoding="utf-8")

def call_test_writer_llm(prompt: str) -> str:
    return call_llm_with_retry(prompt)

def test_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_test_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_cases}}", json.dumps(task["test_cases"], indent=2))
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{output_filename}}", task.get("output_filename", "solution.py"))
        .replace("{{red_light_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_test_writer_llm(prompt)
    tests = _extract_block(raw, "tests")
    return {
        "current_tests": tests,
        "current_code": "",
        "tdd_phase": "write_tests",
        "passed": False,
    }

test_writer_node.__test__ = False  # prevent pytest from collecting this as a test

def red_light_check_node(state: HarnessState) -> dict:
    """驗證 test_writer 產出的測試是否為「正確的紅燈」。不呼叫 LLM。"""
    task = state["tasks"][state["current_task_index"]]
    test_type = task.get("test_type", "auto")
    if test_type == "auto":
        test_type = detect_test_type(state["current_tests"])

    runner = get_runner(test_type)
    run_result = runner.run(
        code="",
        tests=state["current_tests"],
        completed_code=state.get("completed_code", {}),
        output_filename=task.get("output_filename", "solution.py"),
        export_dir=state.get("export_dir", ""),
    )
    output = run_result["output"]

    if "SyntaxError" in output:
        return {
            "red_light_round": state["red_light_round"] + 1,
            "evaluator_feedback": f"測試程式有語法錯誤，請修正：{output[:500]}",
        }
    elif run_result["success"]:
        return {
            "tdd_phase": "write_code",
            "red_light_round": 0,
            "evaluator_feedback": "⚠️ 警告：測試在沒有實作代碼的情況下全部通過，測試可能太弱。",
        }
    else:
        return {
            "tdd_phase": "write_code",
            "red_light_round": 0,
            "evaluator_feedback": "",
        }

def _load_code_writer_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "code_writer.md").read_text(encoding="utf-8")

def call_code_writer_llm(prompt: str) -> str:
    return call_llm_with_retry(prompt)

def _format_completed_code(completed_code: dict) -> str:
    """將 completed_code dict 格式化為 prompt 可讀的字串。"""
    if not completed_code:
        return "None"
    parts = []
    for task_id, code in completed_code.items():
        parts.append(f"### Task {task_id} 的代碼\n```python\n{code}\n```")
    return "\n\n".join(parts)


def _load_existing_file(export_dir: str, output_filename: str) -> str:
    """若目標檔案在現有專案中已存在，讀取其內容供 code_writer 參考。"""
    if not export_dir or not output_filename:
        return ""
    target = Path(export_dir) / output_filename
    if target.exists() and target.is_file():
        try:
            return target.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


def code_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    output_filename = task.get("output_filename", "solution.py")
    export_dir = state.get("export_dir", "")

    # 讀取現有檔案內容，讓 code_writer 在既有 code 上修改而非從頭建立
    existing_content = _load_existing_file(export_dir, output_filename)
    existing_file_section = (
        f"## 現有檔案內容（`{output_filename}`）\n\n"
        f"以下是目標檔案目前的完整內容。你必須在此基礎上修改，而不是從頭建立：\n\n"
        f"```python\n{existing_content}\n```\n"
        if existing_content else
        "## 現有檔案內容\n\n（此檔案尚不存在，請從頭建立）\n"
    )

    prompt = (
        _load_code_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{completed_steps_summary}}", state["completed_steps_summary"] or "None")
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{output_filename}}", output_filename)
        .replace("{{current_tests}}", state["current_tests"])
        .replace("{{completed_code}}", _format_completed_code(state.get("completed_code", {})))
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
        .replace("{{existing_file_content}}", existing_file_section)
    )
    raw = call_code_writer_llm(prompt)
    code = _extract_block(raw, "implementation")
    return {
        "current_code": code,
        "tdd_phase": "write_code",
    }



