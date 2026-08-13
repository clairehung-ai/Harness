import re, json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL, MAX_RED_LIGHT_ROUNDS
from harness.state import HarnessState
from harness.skills.base_runner import detect_test_type, get_runner

def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "generator.md").read_text(encoding="utf-8")

def call_llm(prompt: str) -> str:
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content

def _extract_block(text: str, label: str) -> str:
    m = re.search(rf"```{label}\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if label == "implementation" and blocks:
        return blocks[0].strip()
    if label == "tests" and len(blocks) >= 2:
        return blocks[1].strip()
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
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content

def test_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_test_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_cases}}", json.dumps(task["test_cases"], indent=2))
        .replace("{{test_type}}", task.get("test_type", "unit"))
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
    run_result = runner.run(code="", tests=state["current_tests"])
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
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content

def code_writer_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    prompt = (
        _load_code_writer_prompt()
        .replace("{{overall_goal}}", state["overall_goal"])
        .replace("{{completed_steps_summary}}", state["completed_steps_summary"] or "None")
        .replace("{{task_description}}", task["task_description"])
        .replace("{{expected_output}}", task["expected_output"])
        .replace("{{test_type}}", task.get("test_type", "unit"))
        .replace("{{current_tests}}", state["current_tests"])
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_code_writer_llm(prompt)
    code = _extract_block(raw, "implementation")
    return {
        "current_code": code,
        "tdd_phase": "write_code",
    }
