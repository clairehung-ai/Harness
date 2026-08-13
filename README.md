# Harness

多 Agent 軟體工程系統，採用 TDD 流程自動完成軟體開發任務。

Planner 拆解需求 → test_writer 寫測試 → red_light_check 驗紅燈 → code_writer 寫代碼 → Evaluator 評估 → 自動循環直到通過。

---

## 架構

```
Planner
  └── 拆解需求成 tasks，定義 test_cases、output_filename、test_type

Generator（TDD 兩階段）
  ├── test_writer skill   — 只寫測試程式
  ├── red_light_check     — 驗證測試真的會失敗（紅燈）
  └── code_writer skill   — 看著已確認的測試，寫實作代碼

Evaluator
  ├── pytest_runner skill   — unit / api / integration 測試
  └── playwright_runner skill — e2e_ui 瀏覽器測試

LangGraph Orchestrator
  planner → test_writer → red_light_check → code_writer → evaluator → advance_task
```

詳細架構說明：[ARCHITECTURE.md](ARCHITECTURE.md)

---

## 安裝

**需求：** Python 3.11+

```bash
pip install -r requirements.txt
```

**（選用）E2E UI 測試：**

```bash
pip install pytest-playwright
python -m playwright install chromium
```

---

## 設定

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
```

---

## 使用方式

### 程式呼叫

```python
from harness.main import run_harness

result = run_harness("build a function that calculates the average of a list")

print(f"Passed: {result['passed']}/{result['total']}")
for task in result["task_results"]:
    status = "✅" if task["passed"] else "⚠️ FORCED"
    print(f"  Task {task['task_id']}: {status}")
```

### 命令列

```bash
python -m harness.main "build a CSV parser that returns summary statistics"
```

輸出範例：

```
=== Harness Results ===
Task 1: [✅ PASS] All tests pass and code is clean.
Task 2: [✅ PASS] Good implementation with proper error handling.

📊 Summary: 2/2 passed
📋 Run log: ./harness_run_20260807_103000.jsonl
```

---

## 支援的測試類型

Planner 會自動判斷每個 task 應使用哪種測試，也可手動指定：

| test_type | 說明 | 測試格式 |
|-----------|------|---------|
| `unit` | 純函式、工具類（預設） | `from solution import fn` |
| `api` | FastAPI / Flask endpoint | `from fastapi.testclient import TestClient` |
| `integration` | 跨模組、資料庫、檔案 I/O | `from solution import fn` |
| `e2e_ui` | 瀏覽器 UI 測試 | `from playwright.sync_api import Page` |
| `auto` | 自動偵測 | — |

---

## Run Log

每次執行會產生 `harness_run_<timestamp>.jsonl`，記錄每個 task 的完整執行過程：

```json
{"timestamp": "2026-08-07T10:30:00", "task_id": 1, "task_description": "...",
 "passed": true, "forced": false, "round": 1,
 "current_tests": "...", "current_code": "...", "evaluator_feedback": "..."}
```

---

## 設定參數

`harness/config.py`：

| 參數 | 預設 | 說明 |
|------|------|------|
| `MODEL` | `gpt-4o` | 所有 Agent 使用的模型 |
| `MAX_ROUNDS` | `3` | code_writer 最多 retry 幾次 |
| `MAX_RED_LIGHT_ROUNDS` | `2` | test_writer 最多 retry 幾次 |
| `SANDBOX_TIMEOUT` | `10` 秒 | pytest 執行時間上限 |

---

## 多檔案專案

Planner 可以為每個 task 指定輸出檔名，讓不同 task 的代碼放在不同模組：

```
Task 1 → models.py    （User 資料模型）
Task 2 → services.py  （呼叫 models.py）
Task 3 → api.py       （呼叫 services.py 的 FastAPI endpoints）
```

Task 2 的測試可以直接 `from models import User`，sandbox 會自動把已完成的模組帶進去。

---

## 開發

```bash
# 執行測試
python -m pytest tests/ -v

# 執行（含 playwright 整合測試）
python -m pytest tests/ -v --ignore=tests/test_playwright_runner.py
```

---

## GitHub

https://github.com/clairehung-ai/Harness
