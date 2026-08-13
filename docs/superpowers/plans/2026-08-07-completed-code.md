# completed_code：code_writer 看到已產出代碼 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 HarnessState 新增 completed_code: dict 欄位，讓 code_writer_node 在撰寫代碼時能看到前面所有 task 已產出的代碼。

**Architecture:** state.py 新增欄位，advance_task 存入代碼，code_writer_node 注入 prompt，code_writer.md 新增說明區塊，main.py 初始化空 dict。

**Tech Stack:** Python 3.11+, LangGraph

## Global Constraints

- Python >= 3.11
- completed_code key 格式：str(task_id)，例如 "1"、"2"
- completed_code value：完整代碼字串
- 若 completed_code 為空，prompt 注入 "None"
- 所有修改的代碼有對應測試

---

## File Map

```
harness/state.py                MODIFY — HarnessState 新增 completed_code: dict
harness/graph.py                MODIFY — advance_task 存入 completed_code
harness/main.py                 MODIFY — initial state 加 completed_code: {}
harness/agents/generator.py     MODIFY — code_writer_node 注入 {{completed_code}}
harness/prompts/code_writer.md  MODIFY — 新增 {{completed_code}} 區塊

tests/test_state.py             MODIFY — 新增 completed_code 欄位測試
tests/test_graph.py             MODIFY — advance_task 測試驗證 completed_code 存入
tests/test_generator.py         MODIFY — code_writer_node 測試驗證 prompt 注入
tests/test_smoke.py             MODIFY — initial state 更新
```

---

### Task 1: state + graph + main（資料層）

**Files:**
- Modify: `harness/state.py`
- Modify: `harness/graph.py`
- Modify: `harness/main.py`
- Modify: `tests/test_state.py`
- Modify: `tests/test_graph.py`
- Modify: `tests/test_smoke.py`

**Interfaces:**
- Produces:
  - `HarnessState` 新增 `completed_code: dict`
  - `advance_task` 將 `str(task["id"]): state["current_code"]` 存入 `completed_code`
  - `run_harness()` initial state 有 `completed_code: {}`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_state.py` 新增：

```python
def test_harness_state_has_completed_code():
    from harness.state import HarnessState
    state: HarnessState = {
        "input": "test", "overall_goal": "test",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests", "red_light_round": 0,
        "completed_code": {},
    }
    assert state["completed_code"] == {}
    assert isinstance(state["completed_code"], dict)
```

在 `tests/test_graph.py` 新增（在 `make_tdd_state` 或 `make_state` 的 base dict 裡加入 `"completed_code": {}`，並新增測試）：

```python
def test_advance_task_stores_completed_code():
    """advance_task 應將 current_code 存入 completed_code"""
    state = make_tdd_state(current_task_index=0, passed=True)
    state["completed_code"] = {}
    state["current_code"] = "def add(a, b):\n    return a + b\n"
    result = advance_task(state)
    assert "1" in result["completed_code"]
    assert "def add" in result["completed_code"]["1"]

def test_advance_task_accumulates_completed_code():
    """advance_task 應保留前面 task 的 completed_code"""
    state = make_tdd_state(current_task_index=1, passed=True)
    state["completed_code"] = {"1": "def add(a, b): return a + b"}
    state["current_code"] = "def multiply(a, b):\n    return a * b\n"
    result = advance_task(state)
    assert "1" in result["completed_code"]
    assert "2" in result["completed_code"]
    assert "def multiply" in result["completed_code"]["2"]
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_state.py::test_harness_state_has_completed_code tests/test_graph.py::test_advance_task_stores_completed_code -v
```

Expected: KeyError 或 TypeError

- [ ] **Step 3: 更新 harness/state.py**

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
    test_type: str  # "unit" | "api" | "integration" | "e2e_ui" | "auto"

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
    tdd_phase: str        # "write_tests" | "write_code"
    red_light_round: int  # test_writer 重試次數
    completed_code: dict  # {str(task_id): code_str} 已完成 task 的代碼
```

- [ ] **Step 4: 更新 harness/graph.py 的 advance_task**

在 `advance_task` 函式內新增 completed_code 邏輯：

```python
def advance_task(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]
    status = "PASSED" if state["passed"] else "FORCED"
    summary = f"{state['completed_steps_summary']}\n- Task {task['id']}: {task['task_description']} [{status}]".strip()
    result: TaskResult = {
        "task_id": task["id"], "code": state["current_code"],
        "tests": state["current_tests"], "passed": state["passed"],
        "rating": 0, "feedback": state["evaluator_feedback"],
    }
    new_completed_code = dict(state["completed_code"])
    new_completed_code[str(task["id"])] = state["current_code"]
    return {
        "current_task_index": state["current_task_index"] + 1,
        "round": 0, "evaluator_feedback": "",
        "current_code": "", "current_tests": "",
        "passed": False, "completed_steps_summary": summary,
        "task_results": list(state["task_results"]) + [result],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
        "completed_code": new_completed_code,
    }
```

- [ ] **Step 5: 更新 harness/main.py**

在 `initial` dict 新增 `"completed_code": {}`：

```python
def run_harness(user_input: str) -> list[TaskResult]:
    graph = build_graph()
    initial: HarnessState = {
        "input": user_input, "overall_goal": "",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
        "completed_code": {},
    }
    final = graph.invoke(initial)
    return final["task_results"]
```

- [ ] **Step 6: 更新 tests/test_smoke.py 的 make_state（若有直接建 HarnessState 的地方）**

在 smoke test 的 initial state dict 或任何 `make_state` helper 中加入 `"completed_code": {}`。

- [ ] **Step 7: 執行測試 — 確認通過**

```
python -m pytest tests/test_state.py tests/test_graph.py tests/test_smoke.py -v
```

Expected: 全部通過

- [ ] **Step 8: Commit**

```
git -C "D:\projects\Harness" add harness/state.py harness/graph.py harness/main.py tests/test_state.py tests/test_graph.py tests/test_smoke.py
git -C "D:\projects\Harness" commit -m "feat: HarnessState 新增 completed_code，advance_task 儲存已完成代碼"
```

---

### Task 2: code_writer_node + prompt 注入

**Files:**
- Modify: `harness/agents/generator.py`
- Modify: `harness/prompts/code_writer.md`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `HarnessState["completed_code"]: dict` from Task 1
- Produces:
  - `_format_completed_code(completed_code: dict) -> str` — 格式化為 prompt 可讀文字
  - `code_writer_node` 注入 `{{completed_code}}`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_generator.py` 新增：

```python
def test_code_writer_injects_completed_code():
    """completed_code 被注入 prompt"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add(): assert add(1,2)==3\n"
    state["completed_code"] = {"1": "def multiply(a, b):\n    return a * b\n"}
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_CODE_ONLY
    with patch("harness.agents.generator.call_code_writer_llm", side_effect=capture):
        code_writer_node(state)
    assert "def multiply" in captured[0]
    assert "{{completed_code}}" not in captured[0]

def test_code_writer_empty_completed_code_shows_none():
    """completed_code 為空時，prompt 注入 None"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add(): assert add(1,2)==3\n"
    state["completed_code"] = {}
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_CODE_ONLY
    with patch("harness.agents.generator.call_code_writer_llm", side_effect=capture):
        code_writer_node(state)
    assert "None" in captured[0]
    assert "{{completed_code}}" not in captured[0]
```

同時更新 `make_state()` helper 加入 `"completed_code": {}`：

```python
def make_state(test_type: str = "unit") -> HarnessState:
    return {"input": "build add", "overall_goal": "build add",
            "tasks": [{"id": 1, "task_description": "implement add(a,b)",
                        "dependencies": [], "expected_output": "add fn",
                        "test_cases": [{"input": "1,2", "expected": "3"}],
                        "test_type": test_type}],
            "current_task_index": 0, "completed_steps_summary": "",
            "current_code": "", "current_tests": "",
            "evaluator_feedback": "", "passed": False,
            "round": 0, "task_results": [],
            "tdd_phase": "write_tests", "red_light_round": 0,
            "completed_code": {}}
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_generator.py::test_code_writer_injects_completed_code -v
```

Expected: FAIL（`{{completed_code}}` 還未替換）

- [ ] **Step 3: 新增 _format_completed_code 並更新 code_writer_node**

在 `harness/agents/generator.py` 新增函式並更新 `code_writer_node`：

```python
def _format_completed_code(completed_code: dict) -> str:
    """將 completed_code dict 格式化為 prompt 可讀的字串。"""
    if not completed_code:
        return "None"
    parts = []
    for task_id, code in completed_code.items():
        parts.append(f"### Task {task_id} 的代碼\n```python\n{code}\n```")
    return "\n\n".join(parts)


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
        .replace("{{completed_code}}", _format_completed_code(state.get("completed_code", {})))
        .replace("{{evaluator_feedback}}", state["evaluator_feedback"] or "None")
    )
    raw = call_code_writer_llm(prompt)
    code = _extract_block(raw, "implementation")
    return {
        "current_code": code,
        "tdd_phase": "write_code",
    }
```

- [ ] **Step 4: 更新 harness/prompts/code_writer.md**

在「已完成步驟」區塊之後、「當前任務」區塊之前，插入：

```markdown
## 已產出的代碼（前面 task 的實作，可直接呼叫）

{{completed_code}}

閱讀以上代碼，了解：
- 已有哪些函式、類別可以直接呼叫，不需重複實作
- 現有的介面、參數命名和回傳型別，保持一致
- 若值為 None，表示這是第一個 task，沒有前置代碼

---
```

- [ ] **Step 5: 執行測試 — 確認通過**

```
python -m pytest tests/test_generator.py -v
```

Expected: 全部通過

- [ ] **Step 6: 執行完整測試套件**

```
python -m pytest tests/ --ignore=tests/test_playwright_runner.py --ignore=tests/test_pytest_runner.py --ignore=tests/test_runner.py -v --tb=short
```

Expected: 全部通過

- [ ] **Step 7: Commit**

```
git -C "D:\projects\Harness" add harness/agents/generator.py harness/prompts/code_writer.md tests/test_generator.py
git -C "D:\projects\Harness" commit -m "feat: code_writer_node 注入 completed_code，讓 LLM 看到前面 task 的代碼"
```

---

## Summary

| Task | 產出 |
|------|------|
| 1 | state 新增 completed_code，advance_task 儲存，main.py 初始化 |
| 2 | _format_completed_code，code_writer_node 注入，code_writer.md 更新 |
