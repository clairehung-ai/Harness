# Generator TDD 改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 Harness Generator Agent 改造為 TDD 兩階段流程：test_writer skill 先產出測試，red_light_check 驗證紅燈品質，code_writer skill 再產出實作代碼。

**Architecture:** Generator 拆成三個 LangGraph 節點（test_writer_node、red_light_check_node、code_writer_node），graph 重接條件邊。每個 Generator Skill 有 SKILL.md + prompt 文件，與 Evaluator Skill 架構對稱。

**Tech Stack:** Python 3.11+, LangGraph, LangChain OpenAI, pytest

**Working directory:** D:\projects\Harness\.worktrees\feat-tdd-generator
**Git branch:** feat/tdd-generator

## Global Constraints

- Python >= 3.11
- 所有新增節點的回傳格式：dict（部分 state 更新）
- MAX_RED_LIGHT_ROUNDS = 2（config.py）
- tdd_phase 合法值："write_tests" | "write_code"
- test_writer_node 只產出 current_tests，不產出 current_code
- code_writer_node 只產出 current_code，不改動 current_tests
- red_light_check_node 不呼叫 LLM
- 所有新增代碼有對應測試
- git commit 在 feat/tdd-generator branch

---

## File Map

```
harness/
├── config.py                           MODIFY — 新增 MAX_RED_LIGHT_ROUNDS = 2
├── state.py                            MODIFY — HarnessState 新增 tdd_phase、red_light_round
├── agents/
│   └── generator.py                   MODIFY — 新增三個節點函式
├── prompts/
│   ├── test_writer.md                 CREATE — test_writer LLM prompt
│   └── code_writer.md                 CREATE — code_writer LLM prompt
├── skills/
│   ├── test_writer/
│   │   └── SKILL.md                   CREATE
│   └── code_writer/
│       └── SKILL.md                   CREATE
└── graph.py                           MODIFY — 替換 generator 節點，重接條件邊

tests/
├── test_state.py                       MODIFY — 新增 tdd_phase、red_light_round 欄位測試
├── test_generator.py                   MODIFY — 新增三個節點測試
├── test_graph.py                       MODIFY — 更新 graph 測試
└── test_smoke.py                       MODIFY — 更新 smoke test
```

---

### Task 1: config + state 新增 TDD 欄位

**Files:**
- Modify: `harness/config.py`
- Modify: `harness/state.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `MAX_RED_LIGHT_ROUNDS: int = 2` from `harness.config`
  - `HarnessState` 新增 `tdd_phase: str`、`red_light_round: int`

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_state.py` 新增：

```python
def test_harness_state_has_tdd_fields():
    from harness.state import HarnessState
    state: HarnessState = {
        "input": "test", "overall_goal": "test",
        "tasks": [], "current_task_index": 0,
        "completed_steps_summary": "",
        "current_code": "", "current_tests": "",
        "evaluator_feedback": "", "passed": False,
        "round": 0, "task_results": [],
        "tdd_phase": "write_tests",
        "red_light_round": 0,
    }
    assert state["tdd_phase"] == "write_tests"
    assert state["red_light_round"] == 0

def test_config_has_max_red_light_rounds():
    from harness.config import MAX_RED_LIGHT_ROUNDS
    assert MAX_RED_LIGHT_ROUNDS == 2
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_state.py::test_harness_state_has_tdd_fields tests/test_state.py::test_config_has_max_red_light_rounds -v
```

Expected: ImportError 或 KeyError

- [ ] **Step 3: 更新 harness/config.py**

```python
MAX_ROUNDS: int = 3
MAX_RED_LIGHT_ROUNDS: int = 2
MODEL: str = "gpt-4o"
SANDBOX_TIMEOUT: int = 10
```

- [ ] **Step 4: 更新 harness/state.py**

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
```

- [ ] **Step 5: 執行測試 — 確認通過**

```
python -m pytest tests/test_state.py -v
```

Expected: 全部通過（含新增的 2 個）

- [ ] **Step 6: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/config.py harness/state.py tests/test_state.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: state 新增 tdd_phase、red_light_round，config 新增 MAX_RED_LIGHT_ROUNDS"
```

---

### Task 2: test_writer_node + prompt + SKILL.md

**Files:**
- Create: `harness/prompts/test_writer.md`
- Create: `harness/skills/test_writer/SKILL.md`
- Modify: `harness/agents/generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `HarnessState`, `MODEL` from `harness.config`
- Produces:
  - `test_writer_node(state: HarnessState) -> dict` 回傳 `{"current_tests": str, "current_code": "", "tdd_phase": "write_tests", "passed": False}`
  - `call_test_writer_llm(prompt: str) -> str`（分離供 mock）

- [ ] **Step 1: 建立 harness/skills/test_writer/ 目錄並建立 SKILL.md**

建立 `harness/skills/test_writer/SKILL.md`：

```markdown
# Skill: test_writer

## 用途

根據 Planner 提供的 task_description 和 test_cases，產出完整的 pytest 測試程式。
不產出實作代碼。

## 使用情境

- 每個 task 的 TDD 流程第一步
- 在 code_writer 之前執行
- red_light_check 偵測到 SyntaxError 時重試

## 輸入

- `{{overall_goal}}` — 整個專案目標
- `{{task_description}}` — 當前任務描述
- `{{expected_output}}` — 預期產出物
- `{{test_cases}}` — 測試案例清單（JSON）
- `{{test_type}}` — 測試格式類型
- `{{red_light_feedback}}` — SyntaxError 時的修正建議（可為 None）

## 輸出格式

只輸出一個 fenced code block，標籤為 `tests`：

```tests
from solution import my_function
import pytest

def test_xxx():
    assert my_function(input) == expected
```

不輸出 `implementation` block。不輸出任何說明文字。

## 對應 prompt

`harness/prompts/test_writer.md`
```

- [ ] **Step 2: 建立 harness/prompts/test_writer.md**

```markdown
# 角色：測試程式撰寫專員（TDD 紅燈階段）

你是 Harness 多 Agent 系統中負責「寫測試」的專員。你的任務是根據 Planner 提供的任務規格，撰寫完整的 pytest 測試程式。

**你只寫測試，不寫實作代碼。**

---

## 你的職責

- 依照 `{{test_cases}}` 撰寫覆蓋所有案例的 pytest 測試程式
- 根據 `{{test_type}}` 選擇正確的測試格式
- 若有 `{{red_light_feedback}}`，修正上次測試程式的語法錯誤

## 你不應該做的事

- 不應產出任何實作代碼
- 不應輸出 `implementation` block
- 不應在 block 之外加入任何文字
- 不應讓測試在沒有實作代碼的情況下通過（測試必須依賴 solution 模組）

---

## 輸入

**整體目標：** {{overall_goal}}

**任務描述：** {{task_description}}

**預期產出：** {{expected_output}}

**測試類型：** {{test_type}}

**測試案例（必須全部覆蓋）：**
{{test_cases}}

**上次測試的問題（若有）：**
{{red_light_feedback}}

---

## 測試格式規範

根據 `{{test_type}}` 使用對應格式：

### unit / integration
```python
from solution import <函式名>
import pytest

def test_正常情況():
    assert <函式名>(<輸入>) == <預期>

def test_錯誤情況():
    with pytest.raises(ValueError):
        <函式名>(<錯誤輸入>)
```

### api
```python
from fastapi.testclient import TestClient
from solution import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/your-endpoint")
    assert response.status_code == 200
    assert response.json() == {"key": "value"}
```

### e2e_ui
```python
from playwright.sync_api import Page
import os

def test_page(page: Page):
    html_path = os.path.join(os.path.dirname(__file__), "solution.html")
    page.goto(f"file://{html_path}")
    assert page.title() == "預期標題"
```

---

## 輸出規範

只輸出一個 fenced code block，標籤必須是 `tests`：

你的輸出（僅限一個 `tests` block，不加任何其他內容）：
```

- [ ] **Step 3: 寫失敗測試**

在 `tests/test_generator.py` 新增：

```python
MOCK_TESTS_ONLY = "```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"

def test_test_writer_returns_tests_only():
    """test_writer_node 只產出 current_tests，不產出 current_code"""
    with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS_ONLY):
        result = test_writer_node(make_state())
    assert "def test_add" in result["current_tests"]
    assert result["current_code"] == ""
    assert result["tdd_phase"] == "write_tests"
    assert result["passed"] is False

def test_test_writer_strips_fences():
    with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS_ONLY):
        result = test_writer_node(make_state())
    assert "```" not in result["current_tests"]

def test_test_writer_injects_red_light_feedback():
    """red_light_feedback 被注入 prompt"""
    state = make_state()
    state["evaluator_feedback"] = "SyntaxError on line 3"
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_TESTS_ONLY
    with patch("harness.agents.generator.call_test_writer_llm", side_effect=capture):
        test_writer_node(state)
    assert "SyntaxError on line 3" in captured[0]
```

- [ ] **Step 4: 執行測試 — 確認失敗**

```
python -m pytest tests/test_generator.py::test_test_writer_returns_tests_only -v
```

Expected: ImportError (test_writer_node not found)

- [ ] **Step 5: 實作 test_writer_node（新增到 generator.py）**

在 `harness/agents/generator.py` 新增：

```python
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
```

- [ ] **Step 6: 執行測試 — 確認通過**

```
python -m pytest tests/test_generator.py -v
```

Expected: 全部通過（含新增的 3 個）

- [ ] **Step 7: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/agents/generator.py harness/prompts/test_writer.md harness/skills/test_writer/ tests/test_generator.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: 新增 test_writer_node、test_writer.md prompt 和 SKILL.md"
```

---

### Task 3: red_light_check_node

**Files:**
- Modify: `harness/agents/generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `HarnessState`, `detect_test_type` + `get_runner` from `harness.skills.base_runner`, `MAX_RED_LIGHT_ROUNDS` from `harness.config`
- Produces:
  - `red_light_check_node(state: HarnessState) -> dict`
  - 回傳之一：`{"red_light_round": int, "evaluator_feedback": str}`（SyntaxError）
  - 回傳之二：`{"tdd_phase": "write_code", "red_light_round": 0, "evaluator_feedback": str}`（弱測試）
  - 回傳之三：`{"tdd_phase": "write_code", "red_light_round": 0, "evaluator_feedback": ""}`（正確紅燈）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_generator.py` 新增：

```python
def test_red_light_check_correct_red_light():
    """ImportError = 正確紅燈，進入 write_code"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    state["red_light_round"] = 0
    mock_run = {"success": False, "output": "ImportError: No module named 'solution'"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["tdd_phase"] == "write_code"
    assert result["red_light_round"] == 0
    assert result["evaluator_feedback"] == ""

def test_red_light_check_syntax_error():
    """SyntaxError = tests 寫壞，增加 red_light_round"""
    state = make_state()
    state["current_tests"] = "def test_bad(\n    pass\n"
    state["red_light_round"] = 0
    mock_run = {"success": False, "output": "SyntaxError: invalid syntax"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["red_light_round"] == 1
    assert "SyntaxError" in result["evaluator_feedback"]
    assert "tdd_phase" not in result

def test_red_light_check_weak_tests():
    """所有測試通過（弱測試），記錄警告並繼續"""
    state = make_state()
    state["current_tests"] = "def test_always_pass():\n    assert True\n"
    state["red_light_round"] = 0
    mock_run = {"success": True, "output": "1 passed"}
    with patch("harness.agents.generator.get_runner") as mock_get:
        mock_get.return_value.run.return_value = mock_run
        result = red_light_check_node(state)
    assert result["tdd_phase"] == "write_code"
    assert result["red_light_round"] == 0
    assert "警告" in result["evaluator_feedback"]
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_generator.py::test_red_light_check_correct_red_light -v
```

Expected: ImportError (red_light_check_node not found)

- [ ] **Step 3: 實作 red_light_check_node（新增到 generator.py）**

在 `harness/agents/generator.py` 新增 import 並實作：

```python
from harness.skills.base_runner import detect_test_type, get_runner
from harness.config import MODEL, MAX_RED_LIGHT_ROUNDS
```

```python
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
```

- [ ] **Step 4: 執行測試 — 確認通過**

```
python -m pytest tests/test_generator.py -v
```

Expected: 全部通過

- [ ] **Step 5: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/agents/generator.py tests/test_generator.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: 新增 red_light_check_node，驗證 TDD 紅燈品質"
```

---

### Task 4: code_writer_node + prompt + SKILL.md

**Files:**
- Create: `harness/prompts/code_writer.md`
- Create: `harness/skills/code_writer/SKILL.md`
- Modify: `harness/agents/generator.py`
- Modify: `tests/test_generator.py`

**Interfaces:**
- Consumes: `HarnessState`, `MODEL`
- Produces:
  - `code_writer_node(state: HarnessState) -> dict` 回傳 `{"current_code": str, "tdd_phase": "write_code"}`
  - `call_code_writer_llm(prompt: str) -> str`

- [ ] **Step 1: 建立 harness/skills/code_writer/SKILL.md**

```markdown
# Skill: code_writer

## 用途

看著已確認通過紅燈驗證的測試程式，產出能讓所有測試通過的實作代碼。
不產出測試程式（測試已由 test_writer 產出並確認）。

## 使用情境

- red_light_check 通過（正確紅燈）之後
- Evaluator 評估失敗需要 retry 時（feedback 傳入）

## 輸入

- `{{overall_goal}}` — 整個專案目標
- `{{completed_steps_summary}}` — 已完成任務摘要
- `{{task_description}}` — 當前任務描述
- `{{expected_output}}` — 預期產出物
- `{{test_type}}` — 測試類型
- `{{current_tests}}` — 已確認的測試程式（red_light_check 通過）
- `{{evaluator_feedback}}` — Evaluator 的修正建議（retry 時）

## 輸出格式

只輸出一個 fenced code block，標籤為 `implementation`：

```implementation
def my_function(x):
    return x + 1
```

不輸出 `tests` block。不輸出任何說明文字。

## 對應 prompt

`harness/prompts/code_writer.md`
```

- [ ] **Step 2: 建立 harness/prompts/code_writer.md**

```markdown
# 角色：實作代碼撰寫專員（TDD 綠燈階段）

你是 Harness 多 Agent 系統中負責「寫實作代碼」的專員。測試程式已由 test_writer 產出並通過紅燈驗證。你的任務是看著這些測試，寫出能讓所有測試通過的實作代碼。

**你只寫實作代碼，測試已經存在，不需要重寫。**

---

## 你的職責

- 閱讀 `{{current_tests}}` 理解測試的期望行為
- 撰寫能讓所有測試通過的最小可行實作
- 若有 `{{evaluator_feedback}}`，修正上一輪的問題

## 你不應該做的事

- 不應產出測試程式
- 不應輸出 `tests` block
- 不應修改測試的期望行為
- 不應在 block 之外加入任何文字

---

## 輸入

**整體目標：** {{overall_goal}}

**已完成步驟：** {{completed_steps_summary}}

**任務描述：** {{task_description}}

**預期產出：** {{expected_output}}

**測試類型：** {{test_type}}

**已確認的測試程式（你必須讓這些測試通過）：**
```
{{current_tests}}
```

**Evaluator 的修正建議（若有）：**
{{evaluator_feedback}}

---

## 實作指引

1. 仔細閱讀測試程式，理解每個測試的期望行為
2. 根據 test_type 確認實作的形式（Python 函式、FastAPI app、HTML 頁面）
3. 撰寫能讓所有測試通過的最小實作，不超出測試要求的範圍
4. 若有 evaluator_feedback，逐項修正

---

## 輸出規範

只輸出一個 fenced code block，標籤必須是 `implementation`：

你的輸出（僅限一個 `implementation` block，不加任何其他內容）：
```

- [ ] **Step 3: 寫失敗測試**

在 `tests/test_generator.py` 新增：

```python
MOCK_CODE_ONLY = "```implementation\ndef add(a, b):\n    return a + b\n```"

def test_code_writer_returns_code_only():
    """code_writer_node 只產出 current_code，不改 current_tests"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE_ONLY):
        result = code_writer_node(state)
    assert "def add" in result["current_code"]
    assert result["tdd_phase"] == "write_code"
    assert "current_tests" not in result  # 不改動 current_tests

def test_code_writer_injects_current_tests_into_prompt():
    """current_tests 被注入 prompt"""
    state = make_state()
    state["current_tests"] = "from solution import add\ndef test_add(): assert add(1,2)==3\n"
    captured = []
    def capture(prompt):
        captured.append(prompt)
        return MOCK_CODE_ONLY
    with patch("harness.agents.generator.call_code_writer_llm", side_effect=capture):
        code_writer_node(state)
    assert "from solution import add" in captured[0]
    assert "{{current_tests}}" not in captured[0]

def test_code_writer_strips_fences():
    state = make_state()
    state["current_tests"] = "def test_f(): pass\n"
    with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE_ONLY):
        result = code_writer_node(state)
    assert "```" not in result["current_code"]
```

- [ ] **Step 4: 執行測試 — 確認失敗**

```
python -m pytest tests/test_generator.py::test_code_writer_returns_code_only -v
```

Expected: ImportError (code_writer_node not found)

- [ ] **Step 5: 實作 code_writer_node（新增到 generator.py）**

```python
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
```

- [ ] **Step 6: 執行測試 — 確認通過**

```
python -m pytest tests/test_generator.py -v
```

Expected: 全部通過

- [ ] **Step 7: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/agents/generator.py harness/prompts/code_writer.md harness/skills/code_writer/ tests/test_generator.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: 新增 code_writer_node、code_writer.md prompt 和 SKILL.md"
```

---

### Task 5: graph.py 重接 TDD 流程

**Files:**
- Modify: `harness/graph.py`
- Modify: `tests/test_graph.py`

**Interfaces:**
- Consumes:
  - `test_writer_node` from `harness.agents.generator`
  - `red_light_check_node` from `harness.agents.generator`
  - `code_writer_node` from `harness.agents.generator`
  - `MAX_RED_LIGHT_ROUNDS` from `harness.config`
- Produces:
  - `route_after_red_light_check(state: HarnessState) -> str` 回傳 `"test_writer"` 或 `"code_writer"`
  - `build_graph() -> CompiledGraph`（流程改為 planner → test_writer → red_light_check → code_writer → evaluator）

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_graph.py` 新增：

```python
from harness.graph import route_after_red_light_check
from harness.config import MAX_RED_LIGHT_ROUNDS

def make_tdd_state(**kwargs):
    base = make_state()
    base["tdd_phase"] = "write_tests"
    base["red_light_round"] = 0
    base.update(kwargs)
    return base

def test_route_red_light_syntax_error_retries():
    """red_light_round > 0 且 < MAX → 回到 test_writer"""
    state = make_tdd_state(red_light_round=1, tdd_phase="write_tests")
    assert route_after_red_light_check(state) == "test_writer"

def test_route_red_light_max_rounds_forces_advance():
    """red_light_round >= MAX → 強制進入 code_writer"""
    state = make_tdd_state(red_light_round=MAX_RED_LIGHT_ROUNDS, tdd_phase="write_tests")
    assert route_after_red_light_check(state) == "code_writer"

def test_route_red_light_correct_red_light():
    """red_light_round == 0，tdd_phase == write_code → code_writer"""
    state = make_tdd_state(red_light_round=0, tdd_phase="write_code")
    assert route_after_red_light_check(state) == "code_writer"

def test_build_graph_has_tdd_nodes():
    """graph 包含 test_writer、red_light_check、code_writer 節點"""
    graph = build_graph()
    assert graph is not None
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_graph.py::test_route_red_light_syntax_error_retries -v
```

Expected: ImportError (route_after_red_light_check not found)

- [ ] **Step 3: 更新 harness/graph.py**

```python
from langgraph.graph import StateGraph, END
from harness.state import HarnessState, TaskResult
from harness.agents.planner import planner_node
from harness.agents.generator import test_writer_node, red_light_check_node, code_writer_node
from harness.agents.evaluator import evaluator_node
from harness.config import MAX_ROUNDS, MAX_RED_LIGHT_ROUNDS


def route_after_red_light_check(state: HarnessState) -> str:
    """條件邊：red_light_check 後決定走 test_writer 還是 code_writer。"""
    if state["red_light_round"] > 0 and state["red_light_round"] < MAX_RED_LIGHT_ROUNDS:
        return "test_writer"
    return "code_writer"


def route_after_evaluator(state: HarnessState) -> str:
    if state["passed"] or state["round"] >= MAX_ROUNDS:
        return "advance_task"
    return "code_writer"


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
        "tdd_phase": "write_tests",
        "red_light_round": 0,
    }


def route_after_advance(state: HarnessState) -> str:
    if state["current_task_index"] >= len(state["tasks"]):
        return END
    return "test_writer"


def build_graph():
    g = StateGraph(HarnessState)
    g.add_node("planner", planner_node)
    g.add_node("test_writer", test_writer_node)
    g.add_node("red_light_check", red_light_check_node)
    g.add_node("code_writer", code_writer_node)
    g.add_node("evaluator", evaluator_node)
    g.add_node("advance_task", advance_task)

    g.set_entry_point("planner")
    g.add_edge("planner", "test_writer")
    g.add_edge("test_writer", "red_light_check")
    g.add_conditional_edges("red_light_check", route_after_red_light_check,
                             {"test_writer": "test_writer", "code_writer": "code_writer"})
    g.add_edge("code_writer", "evaluator")
    g.add_conditional_edges("evaluator", route_after_evaluator,
                             {"advance_task": "advance_task", "code_writer": "code_writer"})
    g.add_conditional_edges("advance_task", route_after_advance,
                             {"test_writer": "test_writer", END: END})
    return g.compile()
```

- [ ] **Step 4: 執行 graph 測試**

```
python -m pytest tests/test_graph.py -v
```

Expected: 全部通過（含新增的 4 個）

- [ ] **Step 5: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/graph.py tests/test_graph.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: graph 重接 TDD 流程，planner→test_writer→red_light_check→code_writer→evaluator"
```

---

### Task 6: 更新 main.py initial state + smoke test

**Files:**
- Modify: `harness/main.py`
- Modify: `tests/test_smoke.py`

**Interfaces:**
- 更新 `run_harness` 的 initial state 加入 `tdd_phase` 和 `red_light_round`
- 更新 smoke test mock 路徑：從 `generator.call_llm` 拆成 `call_test_writer_llm` 和 `call_code_writer_llm`

- [ ] **Step 1: 更新 harness/main.py**

將 `initial_state` 新增兩個欄位：

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
    }
    final = graph.invoke(initial)
    return final["task_results"]
```

- [ ] **Step 2: 更新 tests/test_smoke.py**

```python
MOCK_TESTS = "```tests\nfrom solution import add\ndef test_add():\n    assert add(1, 2) == 3\n```"
MOCK_CODE = "```implementation\ndef add(a, b):\n    return a + b\n```"

def test_full_pipeline_smoke():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    # 第一次執行（red_light_check）：ImportError = 正確紅燈
    mock_runner.run.return_value = {"success": False, "output": "ImportError: No module named 'solution'"}

    mock_eval_runner = MagicMock()
    mock_eval_runner.run.return_value = {"success": True, "output": "1 passed"}

    with patch("harness.agents.planner.call_llm", return_value=MOCK_PLANNER):
        with patch("harness.agents.generator.call_test_writer_llm", return_value=MOCK_TESTS):
            with patch("harness.agents.generator.call_code_writer_llm", return_value=MOCK_CODE):
                with patch("harness.agents.generator.get_runner", return_value=mock_runner):
                    with patch("harness.agents.evaluator.call_llm", return_value=MOCK_EVALUATOR):
                        with patch("harness.agents.evaluator.get_runner", return_value=mock_eval_runner):
                            results = run_harness("build an add function")

    assert len(results) == 1
    assert results[0]["task_id"] == 1
    assert results[0]["passed"] is True
```

- [ ] **Step 3: 執行 smoke test**

```
python -m pytest tests/test_smoke.py -v
```

Expected: 1 passed

- [ ] **Step 4: 執行完整測試套件**

```
python -m pytest tests/ -v --tb=short
```

Expected: 全部通過（2 skipped for playwright 可接受）

- [ ] **Step 5: Commit**

```
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" add harness/main.py tests/test_smoke.py
git -C "D:\projects\Harness\.worktrees\feat-tdd-generator" commit -m "feat: main.py 加入 TDD 初始 state，smoke test 更新為新流程"
```

---

## Summary

| Task | 產出 |
|------|------|
| 1 | config 新增 MAX_RED_LIGHT_ROUNDS，state 新增 tdd_phase + red_light_round |
| 2 | test_writer_node + test_writer.md + SKILL.md |
| 3 | red_light_check_node（三條路徑：SyntaxError / 弱測試 / 正確紅燈） |
| 4 | code_writer_node + code_writer.md + SKILL.md |
| 5 | graph.py 重接 TDD 流程 |
| 6 | main.py + smoke test 整合驗證 |
