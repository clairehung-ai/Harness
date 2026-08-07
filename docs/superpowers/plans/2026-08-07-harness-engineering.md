# Harness Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-based multi-agent system (Planner, Generator, Evaluator) that takes a software engineering request, breaks it into tasks with test cases, generates code + tests per task, and iteratively improves via a feedback loop until all tasks pass.

**Architecture:** LangGraph drives orchestration as a state machine with conditional edges. Three LLM agents (Planner, Generator, Evaluator) operate on a shared HarnessState. The retry loop runs per-task: Generator retries with Evaluator feedback up to MAX_ROUNDS, then Orchestrator advances.

**Tech Stack:** Python 3.11+, LangGraph, LangChain, OpenAI API, pytest, subprocess (sandbox runner)

## Global Constraints

- Python >= 3.11
- All agent outputs must be valid JSON where specified
- MAX_ROUNDS = 3 (configurable in config.py)
- SANDBOX_TIMEOUT = 10 seconds
- All LLM calls use the model specified in config.py (default: gpt-4o)
- Tests use pytest
- Each agent prompt lives in prompts/ as a .md file, loaded at runtime

---

## File Map

```
harness/
├── config.py
├── state.py
├── graph.py
├── main.py
├── agents/
│   ├── __init__.py
│   ├── planner.py
│   ├── generator.py
│   └── evaluator.py
├── prompts/
│   ├── planner.md
│   ├── generator.md
│   └── evaluator.md
├── sandbox/
│   ├── __init__.py
│   └── runner.py
└── tests/
    ├── test_state.py
    ├── test_planner.py
    ├── test_generator.py
    ├── test_evaluator.py
    ├── test_runner.py
    ├── test_graph.py
    └── test_smoke.py
```

---

### Task 1: Project Scaffold + Config + State

**Files:**
- Create: `harness/__init__.py`
- Create: `harness/config.py`
- Create: `harness/state.py`
- Create: `harness/agents/__init__.py`
- Create: `harness/sandbox/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_state.py`
- Create: `requirements.txt`

**Interfaces:**
- Produces: `HarnessState`, `Task`, `TaskResult` TypedDicts; `MAX_ROUNDS`, `MODEL`, `SANDBOX_TIMEOUT` from config

- [ ] **Step 1: Create requirements.txt**

```
langgraph>=0.2
langchain-openai>=0.1
openai>=1.0
pytest>=8.0
```

- [ ] **Step 2: Write failing test**

Create `tests/test_state.py`:

```python
from harness.state import HarnessState, Task, TaskResult

def test_task_has_required_fields():
    task: Task = {
        "id": 1,
        "task_description": "do something",
        "dependencies": [],
        "expected_output": "a function",
        "test_cases": [{"input": "x", "expected": "y"}]
    }
    assert task["id"] == 1

def test_task_result_has_required_fields():
    result: TaskResult = {
        "task_id": 1, "code": "def foo(): pass",
        "tests": "def test_foo(): pass",
        "passed": True, "rating": 5, "feedback": "ok"
    }
    assert result["passed"] is True

def test_harness_state_shape():
    state: HarnessState = {
        "input": "build a calculator",
        "overall_goal": "build a calculator",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": []
    }
    assert state["current_task_index"] == 0
```

- [ ] **Step 3: Run test - verify it fails**

```
pytest tests/test_state.py -v
```

Expected: ImportError (module not found)

- [ ] **Step 4: Create scaffold files**

`harness/__init__.py` — empty  
`harness/agents/__init__.py` — empty  
`harness/sandbox/__init__.py` — empty  
`tests/__init__.py` — empty

`harness/config.py`:
```python
MAX_ROUNDS: int = 3
MODEL: str = "gpt-4o"
SANDBOX_TIMEOUT: int = 10
```

`harness/state.py`:
```python
from typing import TypedDict

class TestCase(TypedDict):
    input: str
    expected: str

class Task(TypedDict):
    id: int
    task_description: str
    dependencies: list[int]
    expected_output: str
    test_cases: list[TestCase]

class TaskResult(TypedDict):
    task_id: int
    code: str
    tests: str
    passed: bool
    rating: int
    feedback: str

class HarnessState(TypedDict):
    input: str
    overall_goal: str
    tasks: list[Task]
    current_task_index: int
    completed_steps_summary: str
    current_code: str
    current_tests: str
    evaluator_feedback: str
    passed: bool
    round: int
    task_results: list[TaskResult]
```

- [ ] **Step 5: Run test - verify it passes**

```
pytest tests/test_state.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```
git init
git add .
git commit -m "feat: project scaffold, config, and state types"
```

---

### Task 2: Sandbox Runner

**Files:**
- Create: `harness/sandbox/runner.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Consumes: `SANDBOX_TIMEOUT` from `harness.config`
- Produces: `run_tests(code: str, tests: str) -> dict` with keys `"success": bool`, `"output": str`

- [ ] **Step 1: Write failing tests**

Create `tests/test_runner.py`:

```python
from harness.sandbox.runner import run_tests

def test_passing_code():
    code = "def add(a, b):\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is True

def test_failing_code():
    code = "def add(a, b):\n    return a - b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False

def test_syntax_error_code():
    code = "def add(a, b)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False

def test_timeout_enforced():
    code = "import time\ndef add(a, b):\n    time.sleep(30)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = run_tests(code, tests)
    assert result["success"] is False
```

- [ ] **Step 2: Run - verify fails**

```
pytest tests/test_runner.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement runner.py**

Create `harness/sandbox/runner.py`:

```python
import subprocess, tempfile, os
from harness.config import SANDBOX_TIMEOUT

def run_tests(code: str, tests: str) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "solution.py"), "w") as f:
            f.write(code)
        with open(os.path.join(tmpdir, "test_solution.py"), "w") as f:
            f.write(tests)
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
                capture_output=True, text=True,
                timeout=SANDBOX_TIMEOUT, cwd=tmpdir,
            )
            return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "timeout: exceeded time limit"}
        except Exception as e:
            return {"success": False, "output": f"runner error: {e}"}
```

- [ ] **Step 4: Run - verify passes**

```
pytest tests/test_runner.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add harness/sandbox/runner.py tests/test_runner.py
git commit -m "feat: sandbox runner with subprocess pytest execution"
```

---

### Task 3: Planner Agent

**Files:**
- Create: `harness/prompts/planner.md`
- Create: `harness/agents/planner.py`
- Create: `tests/test_planner.py`

**Interfaces:**
- Produces: `planner_node(state: HarnessState) -> dict` returning `{"overall_goal", "tasks", "current_task_index": 0, "round": 0, "evaluator_feedback": "", "completed_steps_summary": ""}`
- Produces: `call_llm(prompt: str) -> str` (separated for mocking in tests)

- [ ] **Step 1: Create planner prompt**

Create `harness/prompts/planner.md`:

```
# Role: Expert Project Planner

You are an expert project planner for software engineering tasks. Break the user request into atomic tasks.

## Constraints:
- Output a valid JSON array of task objects only. No markdown fences.
- Each task must have: "id" (int), "task_description" (str), "dependencies" (array of ints), "expected_output" (str), "test_cases" (array of {input, expected}).

## User Request:
{{user_request}}

## Your Output (JSON array only):
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_planner.py`:

```python
from unittest.mock import patch
from harness.agents.planner import planner_node
from harness.state import HarnessState

def make_state(user_input="build an add function") -> HarnessState:
    return {"input": user_input, "overall_goal": "", "tasks": [],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "", "current_tests": "", "evaluator_feedback": "",
            "passed": False, "round": 0, "task_results": []}

MOCK = '[{"id":1,"task_description":"implement add","dependencies":[],"expected_output":"add fn","test_cases":[{"input":"1,2","expected":"3"}]}]'

def test_planner_returns_tasks():
    with patch("harness.agents.planner.call_llm", return_value=MOCK):
        result = planner_node(make_state())
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["id"] == 1
    assert result["current_task_index"] == 0

def test_planner_sets_overall_goal():
    with patch("harness.agents.planner.call_llm", return_value=MOCK):
        result = planner_node(make_state())
    assert result["overall_goal"] == "build an add function"
```

- [ ] **Step 3: Run - verify fails**

```
pytest tests/test_planner.py -v
```

Expected: ImportError

- [ ] **Step 4: Implement planner.py**

Create `harness/agents/planner.py`:

```python
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
```

- [ ] **Step 5: Run - verify passes**

```
pytest tests/test_planner.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```
git add harness/agents/planner.py harness/prompts/planner.md tests/test_planner.py
git commit -m "feat: planner agent with JSON task output"
```

---

### Task 4: Generator Agent

**Files:**
- Create: `harness/prompts/generator.md`
- Create: `harness/agents/generator.py`
- Create: `tests/test_generator.py`

**Interfaces:**
- Produces: `generator_node(state: HarnessState) -> dict` returning `{"current_code": str, "current_tests": str}`
- Produces: `call_llm(prompt: str) -> str`
- Code/tests are raw Python strings (no markdown fences)

- [ ] **Step 1: Create generator prompt**

Create `harness/prompts/generator.md`:

```
# Role: Diligent Code Generator

You are a skilled software developer writing code for one atomic task.

## Context:
- Overall Project Goal: {{overall_goal}}
- Previous Steps Completed: {{completed_steps_summary}}

## Current Task:
- Task Description: {{task_description}}
- Expected Output: {{expected_output}}
- Test Cases (write tests covering ALL of these):
{{test_cases}}

## Feedback from previous attempt (if any):
{{evaluator_feedback}}

## Instructions:
1. Write implementation code for this task only.
2. Write pytest test code covering all test cases. Tests must import from `solution` module.
3. If feedback exists, address it.
4. Output exactly two fenced blocks in this order:
   - ```implementation ... ``` — implementation code
   - ```tests ... ``` — pytest test code

## Your Output:
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_generator.py`:

```python
from unittest.mock import patch
from harness.agents.generator import generator_node
from harness.state import HarnessState

def make_state() -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}]}],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "", "current_tests": "",
            "evaluator_feedback": "", "passed": False,
            "round": 0, "task_results": []}

MOCK = "```implementation\ndef add(a, b):\n    return a + b\n```\n\n```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"

def test_returns_code_and_tests():
    with patch("harness.agents.generator.call_llm", return_value=MOCK):
        result = generator_node(make_state())
    assert "def add" in result["current_code"]
    assert "def test_add" in result["current_tests"]

def test_strips_fences():
    with patch("harness.agents.generator.call_llm", return_value=MOCK):
        result = generator_node(make_state())
    assert "```" not in result["current_code"]
    assert "```" not in result["current_tests"]
```

- [ ] **Step 3: Run - verify fails**

```
pytest tests/test_generator.py -v
```

Expected: ImportError

- [ ] **Step 4: Implement generator.py**

Create `harness/agents/generator.py`:

```python
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
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_llm(prompt)
    return {"current_code": _extract_block(raw, "implementation"),
            "current_tests": _extract_block(raw, "tests")}
```

- [ ] **Step 5: Run - verify passes**

```
pytest tests/test_generator.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```
git add harness/agents/generator.py harness/prompts/generator.md tests/test_generator.py
git commit -m "feat: generator agent with code+test extraction"
```

---

### Task 5: Evaluator Agent

**Files:**
- Create: `harness/prompts/evaluator.md`
- Create: `harness/agents/evaluator.py`
- Create: `tests/test_evaluator.py`

**Interfaces:**
- Consumes: `run_tests(code, tests) -> dict` from `harness.sandbox.runner`
- Produces: `evaluator_node(state: HarnessState) -> dict` returning `{"passed": bool, "evaluator_feedback": str, "round": int}`
- Produces: `call_llm(prompt: str) -> str`

- [ ] **Step 1: Create evaluator prompt**

Create `harness/prompts/evaluator.md`:

```
# Role: Meticulous Quality Assurance Engineer

You evaluate code quality after test execution.

## Input:
- Task Description: {{task_description}}
- Test Execution: {{test_result}}
- Test Output: {{test_output}}
- Code:
```python
{{code}}
```

## Criteria:
1. Correctness: fulfills the task description
2. Robustness: handles edge cases and errors
3. Completeness: produces expected output artifact

## Output (JSON only, no fences):
{"is_success": bool, "rating": 1-5, "feedback": "actionable string", "suggested_changes": "optional snippet"}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_evaluator.py`:

```python
from unittest.mock import patch
from harness.agents.evaluator import evaluator_node
from harness.state import HarnessState

def make_state(round=1) -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}]}],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "def add(a,b): return a+b",
            "current_tests": "from solution import add\ndef test_add():\n    assert add(1,2)==3\n",
            "evaluator_feedback": "", "passed": False,
            "round": round, "task_results": []}

PASS_JSON = '{"is_success": true, "rating": 5, "feedback": "All good"}'
FAIL_JSON = '{"is_success": false, "rating": 2, "feedback": "Missing error handling"}'

def test_pass_when_tests_pass():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": True, "output": "1 passed"}):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is True

def test_fail_when_tests_fail():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": False, "output": "AssertionError"}):
        with patch("harness.agents.evaluator.call_llm", return_value=FAIL_JSON):
            result = evaluator_node(make_state())
    assert result["passed"] is False
    assert result["evaluator_feedback"] != ""

def test_increments_round():
    with patch("harness.agents.evaluator.run_tests", return_value={"success": True, "output": "1 passed"}):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(make_state(round=1))
    assert result["round"] == 2
```

- [ ] **Step 3: Run - verify fails**

```
pytest tests/test_evaluator.py -v
```

Expected: ImportError

- [ ] **Step 4: Implement evaluator.py**

Create `harness/agents/evaluator.py`:

```python
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
```

- [ ] **Step 5: Run - verify passes**

```
pytest tests/test_evaluator.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```
git add harness/agents/evaluator.py harness/prompts/evaluator.md tests/test_evaluator.py
git commit -m "feat: evaluator agent with test execution and LLM quality check"
```

---

### Task 6: LangGraph Orchestrator

**Files:**
- Create: `harness/graph.py`
- Create: `tests/test_graph.py`

**Interfaces:**
- Consumes: `planner_node`, `generator_node`, `evaluator_node`, `HarnessState`, `MAX_ROUNDS`
- Produces:
  - `build_graph() -> CompiledGraph`
  - `route_after_evaluator(state: HarnessState) -> str` returns `"advance_task"` or `"generator"`
  - `advance_task(state: HarnessState) -> dict`

- [ ] **Step 1: Write failing tests**

Create `tests/test_graph.py`:

```python
from harness.graph import build_graph, advance_task, route_after_evaluator
from harness.state import HarnessState
from harness.config import MAX_ROUNDS

def make_state(**kwargs) -> HarnessState:
    base: HarnessState = {
        "input": "build add", "overall_goal": "build add",
        "tasks": [
            {"id": 1, "task_description": "implement add", "dependencies": [],
             "expected_output": "add fn", "test_cases": [{"input": "1,2", "expected": "3"}]},
            {"id": 2, "task_description": "implement sub", "dependencies": [1],
             "expected_output": "sub fn", "test_cases": [{"input": "3,1", "expected": "2"}]},
        ],
        "current_task_index": 0, "completed_steps_summary": "",
        "current_code": "def add(a,b): return a+b",
        "current_tests": "from solution import add\ndef test_add(): assert add(1,2)==3",
        "evaluator_feedback": "", "passed": True, "round": 1, "task_results": [],
    }
    base.update(kwargs)
    return base

def test_route_pass_advances():
    assert route_after_evaluator(make_state(passed=True, round=1)) == "advance_task"

def test_route_fail_retries():
    assert route_after_evaluator(make_state(passed=False, round=1)) == "generator"

def test_route_max_rounds_forces_advance():
    assert route_after_evaluator(make_state(passed=False, round=MAX_ROUNDS)) == "advance_task"

def test_advance_task_increments_index():
    result = advance_task(make_state(current_task_index=0))
    assert result["current_task_index"] == 1
    assert result["round"] == 0
    assert result["evaluator_feedback"] == ""

def test_advance_task_updates_summary():
    result = advance_task(make_state(current_task_index=0))
    assert "implement add" in result["completed_steps_summary"]

def test_build_graph_returns_compiled_graph():
    assert build_graph() is not None
```

- [ ] **Step 2: Run - verify fails**

```
pytest tests/test_graph.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement graph.py**

Create `harness/graph.py`:

```python
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
```

- [ ] **Step 4: Run - verify passes**

```
pytest tests/test_graph.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```
git add harness/graph.py tests/test_graph.py
git commit -m "feat: langgraph orchestrator with per-task retry loop"
```

---

### Task 7: Entry Point + Smoke Test

**Files:**
- Create: `harness/main.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: `run_harness(user_input: str) -> list[TaskResult]`

- [ ] **Step 1: Write smoke test**

Create `tests/test_smoke.py`:

```python
from unittest.mock import patch
from harness.main import run_harness

MOCK_PLANNER = '[{"id":1,"task_description":"implement add(a,b)","dependencies":[],"expected_output":"add fn","test_cases":[{"input":"1,2","expected":"3"}]}]'
MOCK_GENERATOR = "```implementation\ndef add(a, b):\n    return a + b\n```\n\n```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"
MOCK_EVALUATOR = '{"is_success": true, "rating": 5, "feedback": "All tests pass."}'

def test_full_pipeline_smoke():
    with patch("harness.agents.planner.call_llm", return_value=MOCK_PLANNER):
        with patch("harness.agents.generator.call_llm", return_value=MOCK_GENERATOR):
            with patch("harness.agents.evaluator.call_llm", return_value=MOCK_EVALUATOR):
                results = run_harness("build an add function")
    assert len(results) == 1
    assert results[0]["task_id"] == 1
    assert results[0]["passed"] is True
```

- [ ] **Step 2: Run - verify fails**

```
pytest tests/test_smoke.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement main.py**

Create `harness/main.py`:

```python
import sys
from harness.graph import build_graph
from harness.state import HarnessState, TaskResult

def run_harness(user_input: str) -> list[TaskResult]:
    graph = build_graph()
    initial: HarnessState = {
        "input": user_input, "overall_goal": "",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
    }
    final = graph.invoke(initial)
    return final["task_results"]

if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your request: ")
    results = run_harness(user_input)
    print("\n=== Harness Results ===")
    for r in results:
        print(f"Task {r['task_id']}: [{'PASS' if r['passed'] else 'FAIL'}] {r['feedback'][:100]}")
```

- [ ] **Step 4: Run smoke test**

```
pytest tests/test_smoke.py -v
```

Expected: 1 passed

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```
git add harness/main.py tests/test_smoke.py
git commit -m "feat: entry point and end-to-end smoke test"
```

---

## Summary

| Task | Deliverable |
|------|-------------|
| 1 | Scaffold, config, state types |
| 2 | Sandbox runner (subprocess pytest) |
| 3 | Planner agent + prompt |
| 4 | Generator agent + prompt |
| 5 | Evaluator agent + prompt |
| 6 | LangGraph orchestrator |
| 7 | Entry point + smoke test |
