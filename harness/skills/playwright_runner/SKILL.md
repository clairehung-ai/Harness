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
