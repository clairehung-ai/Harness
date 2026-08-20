# Self-Hosted Runner 安裝指南

本文件說明如何在 Windows 電腦上設定 GitHub Actions self-hosted runner，
讓 `Asset_inventory` repo 的 Issue 能自動觸發 Harness 執行。

## 前置條件

- Windows 10/11
- Python 3.10+（含 Harness 依賴套件）
- Git（已加入 PATH）
- `gh` CLI（已登入：`gh auth login`）
- Harness 安裝在 `D:\projects\Harness`（或修改 `HARNESS_DIR` 變數）

## 安裝 Runner

### 1. 在 GitHub 取得 runner 安裝指令

前往：`https://github.com/clairehung-ai/Asset_inventory/settings/actions/runners/new`

選擇：
- Operating System: **Windows**
- Architecture: **x64**

複製頁面上的 `config.cmd` 和 `run.cmd` 指令。

### 2. 建立 runner 目錄

```powershell
New-Item -ItemType Directory -Path "C:\actions-runner" -Force
Set-Location "C:\actions-runner"
```

### 3. 下載並設定 runner（使用頁面提供的指令）

```powershell
# 從 GitHub 設定頁面複製實際指令，例如：
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.xxx.x/actions-runner-win-x64-2.xxx.x.zip -OutFile actions-runner-win-x64.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD\actions-runner-win-x64.zip", "$PWD")

# 設定 runner（使用 GitHub 設定頁面提供的 token）
.\config.cmd --url https://github.com/clairehung-ai/Asset_inventory --token <YOUR_TOKEN>
```

設定時選擇：
- Runner name: `harness-runner`（或任意名稱）
- Runner group: `Default`
- Labels: `self-hosted,windows`（保留預設即可）

### 4. 啟動 runner

**手動執行（測試用）：**
```powershell
Set-Location "C:\actions-runner"
.\run.cmd
```

**安裝為 Windows 服務（長期運行）：**
```powershell
Set-Location "C:\actions-runner"
.\svc.cmd install
.\svc.cmd start
```

## 設定 GitHub Repository 變數和 Secrets

前往：`https://github.com/clairehung-ai/Asset_inventory/settings`

### Repository Variables（Settings → Secrets and variables → Actions → Variables）

| 變數名稱 | 值 | 說明 |
|---------|-----|------|
| `HARNESS_DIR` | `D:\projects\Harness` | Harness 安裝路徑 |
| `EXPORT_DIR` | `D:\projects\Asset_inventory` | 生成專案路徑 |
| `HARNESS_MODEL` | `llama-3.3-70b-versatile` | LLM 模型 |
| `HARNESS_MAX_TOKENS` | `16000` | 最大 token 數 |

### Repository Secrets（Settings → Secrets and variables → Actions → Secrets）

| Secret 名稱 | 說明 |
|------------|------|
| `HARNESS_API_KEY` | LLM API Key（Groq / Anthropic） |
| `HARNESS_BASE_URL` | LLM API Base URL（例如 `https://api.groq.com/openai/v1`） |

> `GITHUB_TOKEN` 由 GitHub Actions 自動提供，不需要手動設定。

## 驗證

1. Runner 啟動後，前往 `https://github.com/clairehung-ai/Asset_inventory/settings/actions/runners`，確認 runner 狀態顯示 **Idle**。

2. 在 `Asset_inventory` repo 開一個新 Issue（例如標題：`測試 Harness 觸發`）。

3. 前往 `https://github.com/clairehung-ai/Asset_inventory/actions`，確認 workflow 已觸發。

4. 若成功，Issue 下方應出現 Harness 的留言，包含 PR 連結。

## 停止 Runner

```powershell
# 若是服務模式
Set-Location "C:\actions-runner"
.\svc.cmd stop

# 若是手動模式，按 Ctrl+C
```
