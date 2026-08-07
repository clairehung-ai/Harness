# Harness Evaluator Skill 架構擴充設計

**日期：** 2026-08-07
**狀態：** 已核准

---

## 概覽

本 spec 描述 Harness 系統中 Evaluator Agent 的測試能力擴充設計。目標是讓 Evaluator 能根據任務類型，自動選擇對應的測試 Skill 執行驗證，支援四種測試模式：Unit Test、API Test、Integration Test、E2E UI Test。

---

## 設計目標

1. **可插拔的 Skill 架構** — 新增測試類型只需加一個新 Skill，不改動 Evaluator 核心邏輯
2. **Planner 自動判斷測試類型** — 每個 task 帶有 `test_type` 欄位，Planner 自動填入
3. **auto fallback 機制** — Planner 不確定時填 `auto`，Evaluator 根據產出物自動偵測
4. **evaluator.md 描述可用 Skill** — Evaluator Agent 透過 prompt 知道有哪些 Skill 可用

---

## 測試架構

```
測試工具
├── pytest
│   ├── Unit Test        — 純函式、工具類、計算邏輯
│   ├── API Test         — FastAPI/Flask endpoint（pytest + TestClient）
│   └── Integration Test — 跨模組串接、外部依賴（檔案、資料庫）
│
└── Playwright
    └── E2E UI Test      — 瀏覽器 UI、HTML 頁面、前端互動
```

---

## 目錄結構變更

```
harness/
├── skills/
│   ├── __init__.py
│   ├── base_runner.py                  ← 共用介面定義
│   ├── pytest_runner/
│   │   ├── SKILL.md                    ← 開發者規範文件
│   │   └── pytest_runner.py            ← unit / api / integration 執行代碼
│   └── playwright_runner/
│       ├── SKILL.md                    ← 開發者規範文件
│       └── playwright_runner.py        ← e2e_ui 執行代碼
│
├── sandbox/
│   └── runner.py                       ← 重構：委派給 skills/
│
├── agents/
│   └── evaluator.py                    ← 更新：加入 test_type 判斷和 skill 呼叫
│
├── prompts/
│   └── evaluator.md                    ← 更新：新增可用 Skill 說明區塊
│
└── state.py                            ← 更新：Task 新增 test_type 欄位
```

---

## State 變更

### Task TypedDict（新增 test_type 欄位）

```python
class Task(TypedDict):
    id: int
    task_description: str
    dependencies: list[int]
    expected_output: str
    test_cases: list[TestCase]
    test_type: str  # 新增："unit" | "api" | "integration" | "e2e_ui" | "auto"
```

### test_type 值定義

| 值 | 說明 | 由誰填入 |
|----|------|---------|
| `"unit"` | 純函式、工具類、計算邏輯測試 | Planner |
| `"api"` | FastAPI/Flask HTTP endpoint 測試 | Planner |
| `"integration"` | 跨模組、外部依賴測試 | Planner |
| `"e2e_ui"` | 瀏覽器 UI 互動測試 | Planner |
| `"auto"` | Planner 不確定，交由 Evaluator 自動偵測 | Planner |

---

## Planner 更新

### planner.md 新增 test_type 判斷規則

Planner 在拆解 task 時，依以下規則填入 `test_type`：

| 任務特徵 | 填入值 |
|---------|-------|
| 純函式、工具類、計算邏輯、資料處理 | `"unit"` |
| 有 FastAPI / Flask HTTP endpoint | `"api"` |
| 多個模組串接、資料庫操作、檔案 I/O | `"integration"` |
| 有瀏覽器 UI、HTML 頁面、JavaScript、React | `"e2e_ui"` |
| 不確定或任務描述模糊 | `"auto"` |

---

## Skill 架構

### base_runner.py — 共用介面

```python
from abc import ABC, abstractmethod

class BaseRunner(ABC):
    @abstractmethod
    def run(self, code: str, tests: str) -> dict:
        """
        執行測試並回傳結果。

        Returns:
            dict with keys:
                - success: bool
                - output: str（測試執行的完整輸出）
        """
        ...
```

所有 Skill Runner 都繼承 `BaseRunner`，Evaluator 只需呼叫 `.run()`。

---

### pytest_runner — 執行細節

**支援模式：** `unit`、`api`、`integration`

**unit / integration 模式：**
```
寫 solution.py + test_solution.py → tempdir
subprocess: sys.executable -m pytest test_solution.py -v --tb=short
回傳 {success, output}
```

**api 模式：**
```
寫 solution.py（含 FastAPI app）→ tempdir
寫 test_solution.py（用 TestClient）→ tempdir
subprocess: sys.executable -m pytest test_solution.py -v --tb=short
回傳 {success, output}
```

api 模式與 unit 模式的執行方式相同（都是 subprocess pytest），
差異只在 Generator 產出的測試程式使用 `TestClient` 而非直接呼叫函式。

---

### playwright_runner — 執行細節

**支援模式：** `e2e_ui`

**執行流程：**
```
1. 寫 solution 檔案（HTML / Python web app）→ tempdir
2. 寫 test_solution.py（playwright 測試）→ tempdir
3. 確認 playwright 已安裝（pip install playwright + playwright install chromium）
4. subprocess: sys.executable -m pytest test_solution.py -v --tb=short
5. 回傳 {success, output}
```

**playwright 測試程式範例（Generator 會產出類似這樣的代碼）：**
```python
from playwright.sync_api import Page

def test_page_title(page: Page):
    page.goto("file:///path/to/solution.html")
    assert page.title() == "My Page"

def test_button_click(page: Page):
    page.goto("file:///path/to/solution.html")
    page.click("#submit-btn")
    assert page.locator("#result").text_content() == "Success"
```

---

## test_type 自動偵測邏輯（auto fallback）

當 `test_type == "auto"` 時，Evaluator 掃描 Generator 產出的代碼，依以下優先順序判斷：

```
優先順序（由高到低）

1. 代碼含 "playwright" / "page." / "browser." / "Page"
   → e2e_ui

2. 代碼含 "from fastapi" / "FastAPI()" / "from flask" / "Flask("
   → api

3. 代碼含多個 import + ("open(" / "sqlite3" / "sqlalchemy" / "csv")
   → integration

4. 其他
   → unit（預設 fallback）
```

偵測函式位置：`harness/skills/base_runner.py` 的 `detect_test_type(code: str) -> str`

---

## Evaluator Agent 更新

### evaluator.py 更新邏輯

```python
def evaluator_node(state: HarnessState) -> dict:
    task = state["tasks"][state["current_task_index"]]

    # 1. 決定 test_type
    test_type = task.get("test_type", "auto")
    if test_type == "auto":
        test_type = detect_test_type(state["current_code"])

    # 2. 選擇對應 Runner
    runner = get_runner(test_type)  # 回傳對應的 BaseRunner 實例

    # 3. 執行測試
    run_result = runner.run(state["current_code"], state["current_tests"])

    # 4. LLM 品質評估（不變）
    ...
```

### get_runner() 對應表

```python
def get_runner(test_type: str) -> BaseRunner:
    mapping = {
        "unit": PytestRunner(mode="unit"),
        "api": PytestRunner(mode="api"),
        "integration": PytestRunner(mode="integration"),
        "e2e_ui": PlaywrightRunner(),
    }
    return mapping.get(test_type, PytestRunner(mode="unit"))
```

---

## evaluator.md 新增 Skill 說明區塊

`evaluator.md` 新增以下區塊，讓 Evaluator Agent 知道有哪些 Skill 可用：

```
## 可用的測試 Skill

你有兩個測試 Skill 可以使用。系統會根據任務的 test_type 自動呼叫對應的 Skill，
你需要理解每個 Skill 的使用情境，以便在評估報告中正確描述測試執行的背景。

### Skill 1: pytest_runner

**用途：** 執行 Python 代碼的單元測試、API 測試和整合測試

**使用情境：**
- test_type = "unit"：純函式、工具類、計算邏輯
- test_type = "api"：FastAPI / Flask HTTP endpoint（使用 TestClient）
- test_type = "integration"：跨模組串接、資料庫、檔案 I/O

**測試程式格式：**
- 從 solution 模組匯入：from solution import <函式名>
- API 測試使用 TestClient：from fastapi.testclient import TestClient

### Skill 2: playwright_runner

**用途：** 執行瀏覽器 UI 的端對端測試

**使用情境：**
- test_type = "e2e_ui"：HTML 頁面、JavaScript 互動、React 前端
- 任務描述包含：瀏覽器操作、頁面元素驗證、使用者互動流程

**測試程式格式：**
- 使用 playwright.sync_api：from playwright.sync_api import Page
- 測試函式接收 page 參數：def test_xxx(page: Page)
```

---

## SKILL.md 文件規範

### pytest_runner/SKILL.md 涵蓋內容

- Skill 名稱與用途
- 支援的測試類型（unit / api / integration）及各自的適用條件
- 每種類型的代碼範例（solution.py + test_solution.py）
- 輸入規格：code: str, tests: str, mode: str
- 輸出規格：{"success": bool, "output": str}
- 限制：SANDBOX_TIMEOUT、不支援外部網路請求

### playwright_runner/SKILL.md 涵蓋內容

- Skill 名稱與用途
- 使用情境：何時該選 playwright 而非 pytest
- 前置條件：playwright 安裝、chromium 安裝
- 代碼範例（solution HTML + playwright 測試）
- 輸入規格：code: str, tests: str
- 輸出規格：{"success": bool, "output": str}
- 限制：headless 模式、SANDBOX_TIMEOUT、僅支援 chromium

---

## Planner prompt 更新摘要

`planner.md` 新增以下內容：

1. `test_type` 欄位說明加入 JSON schema 表格
2. 判斷規則（5 種情境對應的 test_type 值）
3. 完整範例更新（包含 test_type 欄位）

---

## 不在本 spec 範圍內

- Generator 的 TDD 改造（拆兩階段）— 獨立 spec
- Playwright 的 Visual Regression Testing
- 測試覆蓋率報告（pytest-cov）
- 平行執行多個 task 的測試

---

## 成功標準

- `test_type` 欄位在 Task TypedDict 中定義
- Planner 在每個 task 正確填入 `test_type`
- `auto` 模式能正確偵測四種測試類型
- `pytest_runner` 能執行 unit / api / integration 三種模式
- `playwright_runner` 能在 headless 模式執行 e2e_ui 測試
- `evaluator.md` 包含完整的 Skill 使用說明
- 兩個 `SKILL.md` 文件包含完整技術規範
- 所有新增代碼有對應的測試
