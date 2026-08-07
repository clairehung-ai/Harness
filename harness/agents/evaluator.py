import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL
from harness.state import HarnessState
from harness.sandbox.runner import run_tests

def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "evaluator.md").read_text(encoding="utf-8")

def call_llm(prompt: str) -> str:
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content

def evaluator_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    run_result = run_tests(state["current_code"], state["current_tests"])
    test_passed = run_result["success"]
    test_output = run_result["output"]

    prompt = (
        _load_prompt()
        .replace("{{task_description}}", task["task_description"])
        .replace("{{test_result}}", "passed" if test_passed else "failed")
        .replace("{{test_output}}", test_output[:2000])
        .replace("{{code}}", state["current_code"])
    )
    raw = call_llm(prompt).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    eval_result = json.loads(raw.strip())
    passed = test_passed and eval_result.get("is_success", False)
    feedback = eval_result.get("feedback", "")
    if not test_passed:
        feedback = f"Tests failed: {test_output[:500]}\n{feedback}"

    return {"passed": passed, "evaluator_feedback": feedback, "round": state["round"] + 1}
