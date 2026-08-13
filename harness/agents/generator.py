import re, json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL
from harness.state import HarnessState

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
