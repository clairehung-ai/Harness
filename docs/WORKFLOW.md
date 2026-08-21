# 專案執行流程

---

## Harness — AI 程式碼生成系統

```
開發者修改 Harness 程式碼
        │
        ▼
手動建立 worktree（功能隔離）
  git worktree add D:\projects\Harness-worktrees\fix-xxx -b fix/xxx
        │
        ▼
在 worktree 內開發與測試
  pytest tests/ -v
        │
        ├── ❌ 測試失敗 → 繼續修改
        │
        └── ✅ 測試通過
                │
                ▼
        git commit + push
                │
                ▼
        GitHub CI 自動觸發（ci.yml）
        └── pytest tests/ 全套跑一次
                │
                ├── ❌ CI 失敗 → 修正後重新 push
                │
                └── ✅ CI 通過
                        │
                        ▼
                開 PR → merge 進 master
```

---

## Asset Inventory — 資產清冊系統

### A. 新需求流程（透過 Harness 自動生成）

```
開發者在 GitHub 開 Issue
  標題：「新增備註欄位」
  內容：詳細需求描述
        │
        ▼
GitHub Actions 偵測到 Issue opened
  觸發 harness-trigger.yml
        │
        ▼
Self-hosted Runner（你的 Windows 電腦）
  執行 python -m harness.github_runner
        │
        ▼
┌─────────────────────────────────────────────┐
│  Harness TDD 流程                            │
│                                             │
│  1. Planner                                 │
│     ├── 掃描 backend/ frontend/ 現有結構     │
│     └── 拆解為原子任務（含 output_filename） │
│                                             │
│  2. 每個 Task 循環：                         │
│     ├── test_writer：寫 pytest 測試          │
│     ├── red_light_check：確認測試會失敗       │
│     ├── code_writer：                       │
│     │   ├── 讀取現有檔案內容                 │
│     │   └── 在既有 code 上修改              │
│     └── evaluator：                         │
│         ├── pytest 實際執行（為主）           │
│         ├── Playwright 截圖（e2e_ui）        │
│         └── LLM 品質評語（輔助）             │
│                                             │
└─────────────────────────────────────────────┘
        │
        ├── ❌ Task 失敗 → code_writer 重試（最多 3 次）
        │
        └── ✅ 所有 Task 完成
                │
                ▼
        生成的 code 寫入現有專案
        backend/models.py、frontend/AssetList.js 等
                │
                ▼
        git init（若無）→ 建立 worktree branch
        run/issue-<號碼>
                │
                ▼
        push branch 到 GitHub
                │
                ▼
        自動開 PR（gh pr create）
                │
                ▼
        在原 Issue 留言
        ├── ✅/❌/⚠️ 每個 Task 測試結果表格
        ├── PR 連結
        └── Playwright 截圖（GitHub Artifacts）
                │
                ▼
        開發者 Review PR
        ├── 查看測試明細
        ├── 下載 Artifacts 看截圖和 HTML 報告
        └── 若有問題 → 手動修正後 commit
                │
                ▼
        merge PR 進 main
                │
                ▼
        GitHub CI 自動觸發（ci.yml）
        ├── backend syntax 驗證
        └── pytest backend/tests/（若有）


```

### B. 手動修正流程（緊急修改或 Harness 無法處理的情況）

```
開發者發現問題
        │
        ▼
手動建立 worktree
  git worktree add
  D:\projects\Asset_inventory-worktrees\fix-xxx
  -b fix/xxx
        │
        ▼
在 worktree 內修改對應檔案
  backend/ 或 frontend/
        │
        ▼
驗證
  ├── python -m py_compile backend/api.py
  └── pytest backend/tests/（若有）
        │
        ▼
git commit + push
        │
        ▼
開 PR → Review → merge 進 main
        │
        ▼
GitHub CI 自動驗證
```

---

## 兩個專案的關係

```
D:\projects\
├── Harness\                 ← AI 生成引擎
│   ├── harness/
│   │   ├── agents/          ← Planner、Generator、Evaluator
│   │   ├── skills/          ← PytestRunner、PlaywrightRunner
│   │   ├── utils/           ← git_manager、exporter、logger
│   │   └── github_runner.py ← GitHub Actions 入口
│   └── .github/workflows/
│       └── ci.yml           ← Harness 自身 CI
│
└── Asset_inventory\         ← 被管理的專案
    ├── backend/             ← Python FastAPI
    ├── frontend/            ← React JS
    └── .github/workflows/
        ├── harness-trigger.yml  ← Issue → Harness 觸發
        └── ci.yml               ← PR/push 自動驗證
```

---

## 環境需求

| 項目 | 說明 |
|------|------|
| Self-hosted Runner | Windows 電腦需保持開機並執行 `C:\actions-runner\run.cmd` |
| Python 環境 | Harness 依賴套件已安裝（`pip install -r requirements.txt`） |
| Playwright | `pip install pytest-playwright && python -m playwright install chromium` |
| PostgreSQL | Asset Inventory backend 需要 DB 連線 |
| GitHub Secrets | `HARNESS_API_KEY`、`HARNESS_BASE_URL` |
| GitHub Variables | `HARNESS_DIR`、`EXPORT_DIR`、`HARNESS_MODEL`、`HARNESS_MAX_TOKENS` |

---

## 注意事項

- **Runner 必須開機** — Self-hosted runner 停止時，Issue 觸發的 workflow 會等待或失敗
- **Harness 改動走 worktree** — 直接在 master 改動，CI 失敗沒有隔離保護
- **Forced 任務需人工確認** — Issue 留言顯示 ⚠️ FORCED 表示測試未完全通過，需要人工 review 該 task 的程式碼
- **Playwright 截圖** — 存放於 GitHub Actions Run → Artifacts，保留 30 天
