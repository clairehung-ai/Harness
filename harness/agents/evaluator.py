import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL
from harness.state import HarnessState
from harness.skills.base_runner import detect_test_type, get_runner


def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "evaluator.md").read_text(encoding="utf-8")


def call_llm(prompt: str) -> str:
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content


def evaluator_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]

    # 1. 決定 test_type
    test_type = task.get("test_type", "auto")
    if test_type == "auto":
        test_type = detect_test_type(state["current_code"])

    # 2. 選擇 Skill Runner 並執行測試
    runner = get_runner(test_type)
    run_result = runner.run(state["current_code"], state["current_tests"])
    test_passed = run_result["success"]
    test_output = run_result["output"]

    # 3. LLM 品質評估
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

    try:
        eval_result = json.loads(raw.strip())
    except json.JSONDecodeError:
        eval_result = {"is_success": False, "rating": 1, "feedback": f"LLM returned unparseable JSON: {raw[:200]}"}

    passed = test_passed and eval_result.get("is_success", False)
    feedback = eval_result.get("feedback", "")
    if not test_passed:
        feedback = f"Tests failed: {test_output[:500]}\n{feedback}"

    return {"passed": passed, "evaluator_feedback": feedback, "round": state["round"] + 1}
