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
