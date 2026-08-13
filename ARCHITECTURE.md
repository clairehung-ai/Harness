# Harness 系統架構圖

**更新日期：** 2026-08-07
**版本：** master（PR #1 merged）

---

## 三個 Agent 概覽

```
┌─────────────────────────────────────────────────────┐
│                   三個 Agent                         │
│                                                     │
│  ┌──────────┐   ┌──────────────────┐   ┌─────────┐  │
│  │ Planner  │   │    Generator     │   │Evaluator│  │
│  └──────────┘   └──────────────────┘   └─────────┘  │
│  planner.md     ┌──────┬──────────┐    evaluator.md  │
│                 │Skill1│  Skill2  │                  │
│                 │test_ │  code_   │                  │
│                 │writer│  writer  │                  │
│                 └──────┴──────────┘                  │
│                 test_writer.md  code_writer.md       │
└─────────────────────────────────────────────────────┘
```

| Agent | 職責 | Prompt |
|-------|------|--------|
| **Planner** | 拆解需求為原子任務，定義 test_cases 和 test_type | `prompts/planner.md` |
| **Generator** | 兩階段 TDD：先寫 tests，再寫 code | `prompts/test_writer.md` + `prompts/code_writer.md` |
| **Evaluator** | 執行測試 + LLM 品質審查，產出 pass/fail + feedback | `prompts/evaluator.md` |

---

## Evaluator Skills（測試執行工具）

```
┌─────────────────────────────────────────────────────┐
│              Evaluator Skills（執行工具）              │
│                                                     │
│  ┌─────────────────────┬─────────────────────────┐   │
│  │   pytest_runner     │   playwright_runner     │   │
│  │   unit/api/integ.   │   e2e_ui headless       │   │
│  │   pytest_runner.py  │   playwright_runner.py  │   │
│  └─────────────────────┴─────────────────────────┘   │
│              base_runner.py                          │
│         detect_test_type() + get_runner()            │
└─────────────────────────────────────────────────────┘
```

| Skill | 支援模式 | 工具 |
|-------|---------|------|
| **pytest_runner** | `unit` / `api` / `integration` | subprocess pytest + TestClient |
| **playwright_runner** | `e2e_ui` | headless chromium |

### test_type 自動偵測規則（auto fallback）

| 代碼特徵 | 判斷為 |
|---------|-------|
| `playwright` / `from playwright` / `Page` | `e2e_ui` |
| `from fastapi` / `FastAPI(` / `from flask` / `Flask(` | `api` |
| `sqlite3` / `sqlalchemy` / `open(` / `csv` + 多個 import | `integration` |
| 其他 | `unit`（預設） |

---

## LangGraph 流程（Orchestrator）

```
planner
  │
  ▼
test_writer_node（只產出 tests，不產出 code）
  │
  ▼
red_light_check_node（驗證紅燈品質，不呼叫 LLM）
  │
  ├── SyntaxError → test_writer_node（重試，最多 MAX_RED_LIGHT_ROUNDS = 2 次）
  │
  ├── 全部通過（弱測試）→ 記錄警告 + 繼續
  │
  └── ImportError / AssertionError（正確紅燈）
        │
        ▼
      code_writer_node（看著已確認的 tests，只產出 code）
        │
        ▼
      evaluator_node（執行測試 + LLM 品質審查）
        │
        ├── fail → code_writer_node（retry，最多 MAX_ROUNDS = 3 次）
        │
        └── pass
              │
              ▼
            advance_task
              │
              ├── 還有任務 ──► test_writer_node（下一個 task）
              └── 全部完成 ──► END
```

---

## Generator Skills（LLM 指令）

```
harness/skills/
├── test_writer/
│   └── SKILL.md      ← 描述何時使用 test_writer，輸入輸出格式
└── code_writer/
    └── SKILL.md      ← 描述何時使用 code_writer，輸入輸出格式
```

| Skill | 職責 | 輸出格式 |
|-------|------|---------|
| **test_writer** | 根據 test_cases 產出 pytest 測試程式 | 只有 ` ```tests ``` ` block |
| **code_writer** | 看著已確認的 tests，產出能讓測試通過的實作代碼 | 只有 ` ```implementation ``` ` block |

---

## 檔案結構

```
harness/
├── config.py               常數設定
│                           MAX_ROUNDS = 3
│                           MAX_RED_LIGHT_ROUNDS = 2
│                           MODEL = "gpt-4o"
│                           SANDBOX_TIMEOUT = 10
│
├── state.py                HarnessState TypedDict
│
├── graph.py                LangGraph Orchestrator
│                           節點、邊、條件路由
│
├── main.py                 run_harness(user_input) 入口
│
├── agents/
│   ├── planner.py          planner_node
│   ├── generator.py        test_writer_node
│   │                       red_light_check_node
│   │                       code_writer_node
│   └── evaluator.py        evaluator_node
│
├── prompts/                LLM prompts（繁體中文，含完整規範和範例）
│   ├── planner.md
│   ├── test_writer.md
│   ├── code_writer.md
│   ├── generator.md        舊版（保留，未來可棄用）
│   └── evaluator.md
│
├── skills/
│   ├── base_runner.py      BaseRunner ABC
│   │                       detect_test_type(code) -> str
│   │                       get_runner(test_type) -> BaseRunner
│   │
│   ├── test_writer/
│   │   └── SKILL.md
│   ├── code_writer/
│   │   └── SKILL.md
│   ├── pytest_runner/
│   │   ├── SKILL.md
│   │   └── pytest_runner.py
│   └── playwright_runner/
│       ├── SKILL.md
│       └── playwright_runner.py
│
└── sandbox/
    └── runner.py           舊版（保留，未來可棄用）

tests/                      51 tests passing
```

---

## HarnessState 欄位

```python
class HarnessState(TypedDict):
    # 輸入
    input: str                    # 原始需求（自然語言或 ticket）
    overall_goal: str             # Planner 解析後的目標

    # 任務清單
    tasks: list[Task]             # 含 test_type, test_cases
    current_task_index: int       # 目前執行到第幾個 task

    # 當前執行狀態
    current_code: str             # code_writer 最新產出
    current_tests: str            # test_writer 最新產出
    evaluator_feedback: str       # Evaluator 的 feedback
    passed: bool                  # Evaluator 是否通過
    round: int                    # code_writer retry 次數

    # TDD 狀態
    tdd_phase: str                # "write_tests" | "write_code"
    red_light_round: int          # test_writer retry 次數

    # 進度記錄
    completed_steps_summary: str  # 已完成任務摘要
    task_results: list[TaskResult]
```

---

## 設定參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `MAX_ROUNDS` | 3 | code_writer 最多 retry 幾次 |
| `MAX_RED_LIGHT_ROUNDS` | 2 | test_writer 最多 retry 幾次（SyntaxError） |
| `MODEL` | `gpt-4o` | 所有 LLM 呼叫使用的模型 |
| `SANDBOX_TIMEOUT` | 10 秒 | pytest subprocess 執行時間上限 |

---

## 支援的輸入格式

**自然語言：**
```
build a Python utility that reads a CSV file and returns summary statistics
```

**結構化 ticket：**
```json
{
  "title": "CSV Summary Utility",
  "description": "...",
  "acceptance_criteria": ["...", "..."]
}
```

---

## 測試覆蓋

| 測試檔案 | 覆蓋元件 |
|---------|---------|
| `test_state.py` | HarnessState, Task, TaskResult TypedDicts |
| `test_planner.py` | planner_node |
| `test_generator.py` | test_writer_node, red_light_check_node, code_writer_node |
| `test_evaluator.py` | evaluator_node, test_type routing |
| `test_base_runner.py` | detect_test_type, get_runner, BaseRunner |
| `test_pytest_runner.py` | PytestRunner (unit/api/integration) |
| `test_playwright_runner.py` | PlaywrightRunner (e2e_ui) |
| `test_runner.py` | sandbox runner (legacy) |
| `test_graph.py` | graph routing, advance_task |
| `test_smoke.py` | 完整 pipeline E2E |

**總計：51 passed（2 playwright skipped when not installed）**

---

## 已知缺口與改進建議

目前系統可以跑通完整的 TDD 循環，但在走向真實專案使用前，以下是評估後發現的缺口，依優先順序排列。

### 🔴 高優先

#### 1. 多檔案管理

**問題：** Generator 目前所有產出都寫入 `solution.py` 一個檔案。真實專案需要多個檔案（`models.py`、`services.py`、`api.py` 等）。

**影響：** 無法處理跨越多個模組的任務，任務複雜度受限。

**建議方向：**
- `Task` 新增 `output_files: list[str]` 欄位
- Generator 產出改為多個 fenced block，每個對應一個檔案
- sandbox runner 支援寫入多個檔案到 tempdir

---

#### 2. code_writer 看不到已產出的代碼

**問題：** `completed_steps_summary` 只有文字摘要，不包含實際代碼。code_writer 在 Task 2 時不知道 Task 1 產出了什麼函式，可能重複實作。

**影響：** 多 task 的專案容易出現重複代碼或不一致的介面。

**建議方向：**
- `HarnessState` 新增 `completed_code: dict[str, str]`（filename → code）
- `advance_task` 將當前 task 的代碼存入 `completed_code`
- `code_writer.md` 的 prompt 注入 `{{completed_code}}`

---

### 🟡 中優先

#### 3. Logging（可觀測性）

**問題：** Pipeline 跑完只有最終 `task_results`，中間每輪的 tests / code / feedback 全部消失。

**影響：** 無法 debug、無法分析系統行為、無法改善 prompt 品質。

**建議方向：**
- 每輪結束後寫入 `harness_run_<timestamp>.jsonl`
- 記錄：task_id、round、tdd_phase、current_tests、current_code、evaluator_feedback、passed
- 提供簡單的 `harness/utils/log_reader.py` 解析 log

---

#### 4. 依賴順序執行（拓撲排序）

**問題：** `Task.dependencies` 欄位有定義，但 Orchestrator 目前按 `id` 順序執行，沒有做拓撲排序。

**影響：** 如果 Task 3 依賴 Task 5，系統不會正確處理執行順序。

**建議方向：**
- `planner_node` 或 `graph.py` 在執行前對 tasks 做拓撲排序
- 若有循環依賴，提早失敗並回報錯誤

---

#### 5. 錯誤恢復與報告

**問題：** 超過 `MAX_ROUNDS` 時是「強制通過」，沒有清楚通知哪個 task 失敗、原因是什麼。

**影響：** 使用者拿到結果不知道品質，無法判斷是否需要人工介入。

**建議方向：**
- `TaskResult` 新增 `forced: bool`（是否強制通過）
- `run_harness()` 結果包含整體摘要：通過幾個、強制通過幾個、失敗原因
- 輸出格式改為結構化 JSON，方便後續處理

---

### 🟢 低優先

#### 6. Human-in-the-loop

**問題：** 系統完全自動，但某些情況應該讓人介入：Planner 拆出明顯錯誤的任務、code_writer 多輪都失敗、Evaluator rating 持續偏低。

**建議方向：**
- 可設定 `HUMAN_IN_LOOP = True` 模式
- 每個 task 結束後暫停，顯示結果等待確認
- 低 rating（< 3）時自動暫停請求人工指引

---

#### 7. README

**問題：** 目前沒有 README，新使用者不知道如何安裝、設定 `OPENAI_API_KEY`、執行第一個任務。

**需要涵蓋：**
- 安裝依賴（`pip install -r requirements.txt`）
- 設定環境變數（`OPENAI_API_KEY`）
- 執行方式（`python -m harness.main "你的需求"`）
- 架構簡介（指向 ARCHITECTURE.md）

---

## 改進優先順序總覽

| 優先級 | 功能 | 影響範圍 |
|--------|------|---------|
| 🔴 高 | 多檔案管理 | Generator、sandbox、state |
| 🔴 高 | code_writer 看到已產出代碼 | state、graph、prompt |
| 🟡 中 | Logging | 新增 utils/logger.py |
| 🟡 中 | 依賴順序執行 | graph.py |
| 🟡 中 | 錯誤恢復與報告 | state、main.py |
| 🟢 低 | Human-in-the-loop | config、graph |
| 🟢 低 | README | 新增檔案 |
