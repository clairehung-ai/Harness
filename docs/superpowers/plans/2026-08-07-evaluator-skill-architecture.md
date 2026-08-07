# Evaluator Skill 架構擴充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 擴充 Harness Evaluator，讓它能根據任務的 test_type 自動選擇 pytest_runner 或 playwright_runner 執行測試，支援 unit / api / integration / e2e_ui 四種模式。

**Architecture:** 建立 harness/skills/ 目錄，定義 BaseRunner 抽象介面，PytestRunner 和 PlaywrightRunner 各自實作。Evaluator 新增 detect_test_type() 和 get_runner() 邏輯，根據 Task 的 test_type 欄位選擇對應 Runner。Planner prompt 更新以填入正確的 test_type。

**Tech Stack:** Python 3.11+, pytest, playwright, fastapi, httpx

## Global Constraints

- Python >= 3.11
- test_type 五個合法值："unit" | "api" | "integration" | "e2e_ui" | "auto"
- 所有 Runner 回傳格式：{"success": bool, "output": str}
- SANDBOX_TIMEOUT = 10 秒（從 harness.config 讀取，playwright 用 3x）
- Playwright 使用 headless chromium
- 所有新增代碼有對應測試

---

## File Map

```
harness/
├── state.py                              MODIFY
├── skills/
│   ├── __init__.py                       CREATE
│   ├── base_runner.py                    CREATE
│   ├── pytest_runner/
│   │   ├── __init__.py                   CREATE
│   │   ├── SKILL.md                      CREATE
│   │   └── pytest_runner.py              CREATE
│   └── playwright_runner/
│       ├── __init__.py                   CREATE
│       ├── SKILL.md                      CREATE
│       └── playwright_runner.py          CREATE
├── agents/
│   └── evaluator.py                      MODIFY
└── prompts/
    ├── evaluator.md                      MODIFY
    └── planner.md                        MODIFY

tests/
├── test_base_runner.py                   CREATE
├── test_pytest_runner.py                 CREATE
├── test_playwright_runner.py             CREATE
├── test_evaluator.py                     MODIFY
├── test_smoke.py                         MODIFY
└── test_state.py                         MODIFY
```

---

### Task 1: state.py 新增 test_type + BaseRunner 基礎

**Files:**
- Modify: `harness/state.py`
- Create: `harness/skills/__init__.py`
- Create: `harness/skills/base_runner.py`
- Create: `harness/skills/pytest_runner/__init__.py`
- Create: `harness/skills/playwright_runner/__init__.py`
- Test: `tests/test_base_runner.py`

**Interfaces:**
- Produces:
  - `Task` TypedDict 新增 `test_type: str`
  - `BaseRunner` ABC with `run(code: str, tests: str) -> dict`
  - `detect_test_type(code: str) -> str`
  - `get_runner(test_type: str) -> BaseRunner`

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_base_runner.py`:

```python
from harness.skills.base_runner import detect_test_type, BaseRunner
import pytest

def test_detect_unit_default():
    assert detect_test_type("def add(a, b):\n    return a + b\n") == "unit"

def test_detect_api_fastapi():
    assert detect_test_type("from fastapi import FastAPI\napp = FastAPI()\n") == "api"

def test_detect_api_flask():
    assert detect_test_type("from flask import Flask\napp = Flask(__name__)\n") == "api"

def test_detect_integration_sqlite():
    assert detect_test_type("import sqlite3\nimport os\ndef save(): pass\n") == "integration"

def test_detect_integration_file_io():
    assert detect_test_type("import csv\nimport os\ndef read(path):\n    with open(path) as f: pass\n") == "integration"

def test_detect_playwright():
    assert detect_test_type("from playwright.sync_api import Page\n") == "e2e_ui"

def test_detect_priority_playwright_over_api():
    assert detect_test_type("from playwright.sync_api import Page\nfrom fastapi import FastAPI\n") == "e2e_ui"

def test_base_runner_is_abstract():
    with pytest.raises(TypeError):
        BaseRunner()
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_base_runner.py -v
```

Expected: ImportError

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
```

- [ ] **Step 4: 建立空檔**

`harness/skills/__init__.py` — 空
`harness/skills/pytest_runner/__init__.py` — 空
`harness/skills/playwright_runner/__init__.py` — 空

- [ ] **Step 5: 建立 harness/skills/base_runner.py**

```python
from abc import ABC, abstractmethod


class BaseRunner(ABC):
    """所有測試 Skill Runner 的抽象基底類別。"""

    @abstractmethod
    def run(self, code: str, tests: str) -> dict:
        """
        執行測試並回傳結果。
        Returns: {"success": bool, "output": str}
        """
        ...


def detect_test_type(code: str) -> str:
    """
    根據代碼內容自動偵測測試類型。
    優先順序：e2e_ui > api > integration > unit
    """
    if any(s in code for s in ["playwright", "from playwright", "Page"]):
        return "e2e_ui"
    if any(s in code for s in ["from fastapi", "FastAPI(", "from flask", "Flask("]):
        return "api"
    integration_signals = ["sqlite3", "sqlalchemy", "open(", "csv"]
    if any(s in code for s in integration_signals) and code.count("import ") >= 2:
        return "integration"
    return "unit"


def get_runner(test_type: str) -> BaseRunner:
    """根據 test_type 回傳對應 Runner，未知類型 fallback 到 unit。"""
    from harness.skills.pytest_runner.pytest_runner import PytestRunner
    from harness.skills.playwright_runner.playwright_runner import PlaywrightRunner

    mapping = {
        "unit": PytestRunner(mode="unit"),
        "api": PytestRunner(mode="api"),
        "integration": PytestRunner(mode="integration"),
        "e2e_ui": PlaywrightRunner(),
    }
    return mapping.get(test_type, PytestRunner(mode="unit"))
```

- [ ] **Step 6: 執行測試 — 確認通過**

```
python -m pytest tests/test_base_runner.py -v
```

Expected: 8 passed

- [ ] **Step 7: 確認既有測試無破壞**

```
python -m pytest tests/test_state.py tests/test_graph.py tests/test_planner.py -v
```

Expected: 通過

- [ ] **Step 8: Commit**

```
git add harness/state.py harness/skills/ tests/test_base_runner.py
git commit -m "feat: 新增 test_type 到 Task，建立 BaseRunner + detect_test_type + get_runner"
```

---

### Task 2: PytestRunner 實作 + SKILL.md

**Files:**
- Create: `harness/skills/pytest_runner/pytest_runner.py`
- Create: `harness/skills/pytest_runner/SKILL.md`
- Test: `tests/test_pytest_runner.py`

**Interfaces:**
- Consumes: `BaseRunner` from `harness.skills.base_runner`, `SANDBOX_TIMEOUT` from `harness.config`
- Produces: `PytestRunner(mode: str)` with `.run(code, tests) -> dict`

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_pytest_runner.py`:

```python
from harness.skills.pytest_runner.pytest_runner import PytestRunner

def test_unit_passing():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b):\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = runner.run(code, tests)
    assert result["success"] is True

def test_unit_failing():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b):\n    return a - b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = runner.run(code, tests)
    assert result["success"] is False

def test_api_mode_fastapi():
    runner = PytestRunner(mode="api")
    code = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/hello')\n"
        "def hello():\n"
        "    return {'message': 'hello world'}\n"
    )
    tests = (
        "from fastapi.testclient import TestClient\n"
        "from solution import app\n"
        "client = TestClient(app)\n"
        "def test_hello():\n"
        "    r = client.get('/hello')\n"
        "    assert r.status_code == 200\n"
        "    assert r.json() == {'message': 'hello world'}\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_integration_file_io():
    runner = PytestRunner(mode="integration")
    code = (
        "import os\n"
        "def write_and_read(path, content):\n"
        "    with open(path, 'w') as f: f.write(content)\n"
        "    with open(path) as f: return f.read()\n"
    )
    tests = (
        "import os\n"
        "from solution import write_and_read\n"
        "def test_write_and_read(tmp_path):\n"
        "    p = str(tmp_path / 'test.txt')\n"
        "    assert write_and_read(p, 'hello') == 'hello'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_syntax_error_returns_failure():
    runner = PytestRunner(mode="unit")
    code = "def add(a, b)\n    return a + b\n"
    tests = "from solution import add\ndef test_add():\n    assert add(1,2)==3\n"
    result = runner.run(code, tests)
    assert result["success"] is False

def test_returns_required_keys():
    runner = PytestRunner(mode="unit")
    result = runner.run("def f(): return 1\n", "from solution import f\ndef test_f():\n    assert f()==1\n")
    assert "success" in result and "output" in result
    assert isinstance(result["success"], bool)
    assert isinstance(result["output"], str)

def test_invalid_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        PytestRunner(mode="invalid")
```

- [ ] **Step 2: 執行測試 — 確認失敗**

```
python -m pytest tests/test_pytest_runner.py -v
```

Expected: ImportError

先安裝依賴（若未安裝）:
```
pip install fastapi httpx
```

- [ ] **Step 3: 建立 harness/skills/pytest_runner/pytest_runner.py**

```python
import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PytestRunner(BaseRunner):
    """pytest Skill Runner，支援 unit / api / integration 三種模式。"""

    VALID_MODES = ("unit", "api", "integration")

    def __init__(self, mode: str = "unit"):
        if mode not in self.VALID_MODES:
            raise ValueError(f"不支援的模式：{mode}，合法值為 {self.VALID_MODES}")
        self.mode = mode

    def run(self, code: str, tests: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "solution.py"), "w", encoding="utf-8") as f:
                f.write(code)
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT, cwd=tmpdir,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: 測試執行超過時間限制"}
            except Exception as e:
                return {"success": False, "output": f"runner 錯誤: {e}"}
```

- [ ] **Step 4: 執行測試 — 確認通過**

```
python -m pytest tests/test_pytest_runner.py -v
```

Expected: 7 passed

- [ ] **Step 5: 建立 harness/skills/pytest_runner/SKILL.md**

```markdown
# Skill: pytest_runner

## 用途
使用 pytest 在 subprocess sandbox 中執行 Python 代碼測試。支援三種模式：unit、api、integration。

## 使用情境

| mode | 適用類型 | 典型特徵 |
|------|---------|---------|
| `unit` | 純函式、工具類、計算邏輯 | 只 import 標準庫 |
| `api` | FastAPI / Flask endpoint | 含 FastAPI() 或 Flask( |
| `integration` | 跨模組、檔案 I/O、資料庫 | 含 open( / sqlite3 / csv |

## 輸入
- `code: str` — 實作代碼，寫入 solution.py
- `tests: str` — pytest 測試程式，寫入 test_solution.py
- `mode: str` — "unit" / "api" / "integration"

## 輸出
{"success": bool, "output": str}

## 測試程式格式

**unit/integration:**
```python
from solution import my_function
def test_xxx(): ...
```

**api:**
```python
from fastapi.testclient import TestClient
from solution import app
client = TestClient(app)
def test_xxx(): ...
```

## 限制
- SANDBOX_TIMEOUT = 10 秒
- 不支援外部網路請求
- api 模式使用 TestClient，不啟動真實 server
```

- [ ] **Step 6: Commit**

```
git add harness/skills/pytest_runner/ tests/test_pytest_runner.py
git commit -m "feat: 新增 PytestRunner，支援 unit / api / integration 三種模式"
```

---

### Task 3: PlaywrightRunner 實作 + SKILL.md

**Files:**
- Create: `harness/skills/playwright_runner/playwright_runner.py`
- Create: `harness/skills/playwright_runner/SKILL.md`
- Test: `tests/test_playwright_runner.py`

**Interfaces:**
- Consumes: `BaseRunner`, `SANDBOX_TIMEOUT`
- Produces: `PlaywrightRunner()` with `.run(code, tests) -> dict` and `._is_html(code) -> bool`

- [ ] **Step 1: 安裝 playwright**

```
pip install pytest-playwright
python -m playwright install chromium
```

Expected: chromium 下載完成

- [ ] **Step 2: 寫失敗測試**

建立 `tests/test_playwright_runner.py`:

```python
from harness.skills.playwright_runner.playwright_runner import PlaywrightRunner

def test_is_html_true():
    runner = PlaywrightRunner()
    assert runner._is_html("<!DOCTYPE html><html><body></body></html>") is True

def test_is_html_false():
    runner = PlaywrightRunner()
    assert runner._is_html("from fastapi import FastAPI\n") is False

def test_returns_required_keys():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>T</title></head><body></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_title(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.title() == 'T'\n"
    )
    result = runner.run(code, tests)
    assert "success" in result and "output" in result

def test_passing_html():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>Hi</title></head><body><p id='msg'>Hello</p></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_msg(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.locator('#msg').text_content() == 'Hello'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is True

def test_failing_html():
    runner = PlaywrightRunner()
    code = "<!DOCTYPE html><html><head><title>Hi</title></head><body><p id='msg'>Hello</p></body></html>"
    tests = (
        "from playwright.sync_api import Page\nimport os\n"
        "def test_msg(page: Page):\n"
        "    p = os.path.join(os.path.dirname(__file__), 'solution.html')\n"
        "    page.goto(f'file://{p}')\n"
        "    assert page.locator('#msg').text_content() == 'Wrong'\n"
    )
    result = runner.run(code, tests)
    assert result["success"] is False
```

- [ ] **Step 3: 執行測試 — 確認失敗**

```
python -m pytest tests/test_playwright_runner.py -v
```

Expected: ImportError

- [ ] **Step 4: 建立 harness/skills/playwright_runner/playwright_runner.py**

```python
import subprocess, tempfile, os, sys
from harness.skills.base_runner import BaseRunner
from harness.config import SANDBOX_TIMEOUT


class PlaywrightRunner(BaseRunner):
    """Playwright headless chromium E2E UI 測試 Skill Runner。"""

    def _is_html(self, code: str) -> bool:
        stripped = code.strip().lower()
        return stripped.startswith("<!doctype html") or stripped.startswith("<html")

    def run(self, code: str, tests: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = "solution.html" if self._is_html(code) else "solution.py"
            with open(os.path.join(tmpdir, filename), "w", encoding="utf-8") as f:
                f.write(code)
            with open(os.path.join(tmpdir, "test_solution.py"), "w", encoding="utf-8") as f:
                f.write(tests)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short", "--browser", "chromium"],
                    capture_output=True, text=True,
                    timeout=SANDBOX_TIMEOUT * 3,
                    cwd=tmpdir,
                )
                return {"success": result.returncode == 0, "output": result.stdout + result.stderr}
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "timeout: Playwright 測試超過時間限制"}
            except Exception as e:
                return {"success": False, "output": f"playwright runner 錯誤: {e}"}
```

- [ ] **Step 5: 執行測試 — 確認通過**

```
python -m pytest tests/test_playwright_runner.py -v
```

Expected: 5 passed

- [ ] **Step 6: 建立 harness/skills/playwright_runner/SKILL.md**

```markdown
# Skill: playwright_runner

## 用途
使用 Playwright headless chromium 執行瀏覽器 E2E UI 測試。

## 使用情境（選這個 skill 的條件）
- test_type = "e2e_ui"
- 任務產出物是 HTML 頁面或前端 UI
- 任務描述含：頁面互動、按鈕點擊、表單、頁面元素驗證
- 代碼含：playwright / page. / browser. / from playwright

## 不適合用 playwright_runner 的情況
- 純 Python 函式 → pytest_runner(unit)
- FastAPI/Flask API → pytest_runner(api)
- 無 UI 整合測試 → pytest_runner(integration)

## 前置條件
```
pip install pytest-playwright
python -m playwright install chromium
```

## 輸入
- `code: str` — HTML 代碼寫入 solution.html，Python 代碼寫入 solution.py
- `tests: str` — pytest-playwright 測試，寫入 test_solution.py

## 代碼類型判斷
- 以 <!DOCTYPE html 或 <html 開頭 → HTML → solution.html
- 其他 → Python → solution.py

## 輸出
{"success": bool, "output": str}

## 測試程式格式
```python
from playwright.sync_api import Page
import os

def test_xxx(page: Page):
    html_path = os.path.join(os.path.dirname(__file__), "solution.html")
    page.goto(f"file://{html_path}")
    assert page.title() == "Expected Title"
```

## 限制
- SANDBOX_TIMEOUT * 3（瀏覽器啟動需較多時間）
- 僅支援 headless chromium
- 不支援外部網路
- playwright 需預先安裝
```

- [ ] **Step 7: Commit**

```
git add harness/skills/playwright_runner/ tests/test_playwright_runner.py
git commit -m "feat: 新增 PlaywrightRunner，支援 headless chromium E2E UI 測試"
```

---

### Task 4: Evaluator 更新 — 使用 Skill Runner

**Files:**
- Modify: `harness/agents/evaluator.py`
- Modify: `tests/test_evaluator.py`

**Interfaces:**
- Consumes: `detect_test_type`, `get_runner` from `harness.skills.base_runner`
- Produces: `evaluator_node` 行為不變，但透過 skill runner 執行測試

- [ ] **Step 1: 新增測試到 tests/test_evaluator.py**

在現有測試末尾加入：

```python
def test_evaluator_routes_to_skill_runner():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["test_type"] = "unit"
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
        with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
            result = evaluator_node(state)
    mock_runner.run.assert_called_once()
    assert result["passed"] is True

def test_evaluator_auto_detects():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0]["test_type"] = "auto"
    state["current_code"] = "def add(a, b): return a + b"
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.detect_test_type", return_value="unit") as mock_detect:
        with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
            with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
                result = evaluator_node(state)
    mock_detect.assert_called_once_with(state["current_code"])
    assert result["passed"] is True

def test_evaluator_missing_test_type_fallbacks():
    from unittest.mock import MagicMock
    state = make_state()
    state["tasks"][0].pop("test_type", None)
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}
    with patch("harness.agents.evaluator.detect_test_type", return_value="unit"):
        with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
            with patch("harness.agents.evaluator.call_llm", return_value=PASS_JSON):
                result = evaluator_node(state)
    assert result["passed"] is True
```

- [ ] **Step 2: 執行新測試 — 確認失敗**

```
python -m pytest tests/test_evaluator.py::test_evaluator_routes_to_skill_runner -v
```

Expected: FAIL（evaluator 尚未使用 get_runner）

- [ ] **Step 3: 更新 harness/agents/evaluator.py**

```python
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
```

- [ ] **Step 4: 執行全部 evaluator 測試**

```
python -m pytest tests/test_evaluator.py -v
```

Expected: 6 passed（3 原有 + 3 新增）

- [ ] **Step 5: Commit**

```
git add harness/agents/evaluator.py tests/test_evaluator.py
git commit -m "feat: Evaluator 改用 Skill Runner，支援 test_type 路由和 auto 偵測"
```

---

### Task 5: 更新 prompts + smoke test

**Files:**
- Modify: `harness/prompts/evaluator.md`
- Modify: `harness/prompts/planner.md`
- Modify: `tests/test_smoke.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: 更新 harness/prompts/evaluator.md**

在「## 輸入」區塊之前插入以下 Skill 說明區塊（找到 `## 輸入` 這行，在它之前插入）：

```markdown
---

## 可用的測試 Skill

系統根據任務 test_type 自動選擇對應 Skill 執行測試，並將結果提供給你評估。

### Skill 1：pytest_runner
- test_type = "unit"：純函式測試，from solution import <fn>
- test_type = "api"：FastAPI TestClient 測試，from fastapi.testclient import TestClient
- test_type = "integration"：跨模組、檔案 I/O、資料庫

### Skill 2：playwright_runner
- test_type = "e2e_ui"：HTML 頁面、JS 互動、前端 UI
- 測試含 from playwright.sync_api import Page，函式接收 page: Page 參數
- TimeoutError → 元素不存在；AssertionError → 內容不符

---
```

- [ ] **Step 2: 更新 harness/prompts/planner.md**

在欄位說明表格的 test_cases 行之後，加入 test_type 行：

```
| `test_type` | str | ✓ | 測試類型：`"unit"` / `"api"` / `"integration"` / `"e2e_ui"` / `"auto"` |
```

並在 test_cases 說明區塊之後加入判斷規則表格：

```markdown
### test_type 判斷規則

| 任務特徵 | 填入值 |
|---------|-------|
| 純函式、工具類、計算邏輯 | `"unit"` |
| FastAPI / Flask HTTP endpoint | `"api"` |
| 多模組串接、sqlite3 / csv / open() | `"integration"` |
| HTML 頁面、JavaScript、React 前端 | `"e2e_ui"` |
| 不確定 | `"auto"` |
```

並更新完整範例的 JSON，加入 test_type 欄位：
```json
"test_type": "unit"
```

- [ ] **Step 3: 更新 tests/test_state.py**

在 `test_task_has_required_fields` 中加入 test_type：

```python
def test_task_has_required_fields():
    task: Task = {
        "id": 1,
        "task_description": "do something",
        "dependencies": [],
        "expected_output": "a function",
        "test_cases": [{"input": "x", "expected": "y"}],
        "test_type": "unit"
    }
    assert task["id"] == 1
    assert task["test_type"] == "unit"
```

- [ ] **Step 4: 更新 tests/test_smoke.py**

更新 MOCK_PLANNER 加入 test_type，並更新 test_full_pipeline_smoke 使用 get_runner mock：

```python
MOCK_PLANNER = '[{"id":1,"task_description":"implement add(a,b)","dependencies":[],"expected_output":"add fn","test_cases":[{"input":"1,2","expected":"3"}],"test_type":"unit"}]'

def test_full_pipeline_smoke():
    from unittest.mock import MagicMock
    mock_runner = MagicMock()
    mock_runner.run.return_value = {"success": True, "output": "1 passed"}

    with patch("harness.agents.planner.call_llm", return_value=MOCK_PLANNER):
        with patch("harness.agents.generator.call_llm", return_value=MOCK_GENERATOR):
            with patch("harness.agents.evaluator.call_llm", return_value=MOCK_EVALUATOR):
                with patch("harness.agents.evaluator.get_runner", return_value=mock_runner):
                    results = run_harness("build an add function")

    assert len(results) == 1
    assert results[0]["task_id"] == 1
    assert results[0]["passed"] is True
```

- [ ] **Step 5: 執行完整測試套件**

```
python -m pytest tests/ -v
```

Expected: 全部通過

- [ ] **Step 6: Commit**

```
git add harness/prompts/ tests/test_smoke.py tests/test_state.py
git commit -m "docs: 更新 evaluator.md 和 planner.md，加入 Skill 說明和 test_type 規則"
```

---

## Summary

| Task | 產出 |
|------|------|
| 1 | state.py 新增 test_type，BaseRunner + detect_test_type + get_runner |
| 2 | PytestRunner（unit/api/integration）+ SKILL.md |
| 3 | PlaywrightRunner（e2e_ui）+ SKILL.md |
| 4 | Evaluator 改用 Skill Runner，支援 test_type 路由 |
| 5 | prompts 更新 + smoke test + state test 整合驗證 |
