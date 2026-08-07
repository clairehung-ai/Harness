import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from harness.config import MODEL
from harness.state import HarnessState

def _load_prompt() -> str:
    return (Path(__file__).parent.parent / "prompts" / "planner.md").read_text(encoding="utf-8")

def call_llm(prompt: str) -> str:
    return ChatOpenAI(model=MODEL, temperature=0).invoke(prompt).content

def planner_node(state: HarnessState) -> dict:
    raw = call_llm(_load_prompt().replace("{{user_request}}", state["input"]))
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    tasks = json.loads(raw.strip())
    return {"overall_goal": state["input"], "tasks": tasks,
            "current_task_index": 0, "round": 0,
            "evaluator_feedback": "", "completed_steps_summary": ""}
