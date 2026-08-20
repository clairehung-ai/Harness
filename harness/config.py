import os
import re
import time
from langchain_openai import ChatOpenAI

MAX_ROUNDS: int = 3
MAX_RED_LIGHT_ROUNDS: int = 2
MODEL: str = os.environ.get("HARNESS_MODEL", "llama-3.3-70b-versatile")
SANDBOX_TIMEOUT: int = int(os.environ.get("HARNESS_SANDBOX_TIMEOUT", "30"))

# 代碼導出設定
AUTO_EXPORT: bool = os.environ.get("HARNESS_AUTO_EXPORT", "true").lower() == "true"
EXPORT_DIR: str = os.environ.get("HARNESS_EXPORT_DIR", "./output")
EXPORT_TESTS: bool = os.environ.get("HARNESS_EXPORT_TESTS", "true").lower() == "true"

# Git worktree 設定
GIT_ENABLED: bool = os.environ.get("HARNESS_GIT_ENABLED", "true").lower() == "true"

# LLM Server 設定（可透過環境變數切換後端，例如 Groq 或 Anthropic）
LLM_BASE_URL: str = os.environ.get("HARNESS_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: str = os.environ.get("HARNESS_API_KEY", "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")
LLM_MAX_TOKENS: int = int(os.environ.get("HARNESS_MAX_TOKENS", "4096"))

# 可透過環境變數注入額外 header（例如 Anthropic 需要 anthropic-version）
_anthropic_version = os.environ.get("HARNESS_ANTHROPIC_VERSION", "")
LLM_DEFAULT_HEADERS: dict = (
    {"anthropic-version": _anthropic_version} if _anthropic_version else {}
)


def make_llm() -> ChatOpenAI:
    """統一建立 ChatOpenAI instance。"""
    return ChatOpenAI(
        model=MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=0,
        max_tokens=LLM_MAX_TOKENS,
        default_headers=LLM_DEFAULT_HEADERS,
    )


def call_llm_with_retry(prompt: str, max_retries: int = 5) -> str:
    """呼叫 LLM，遇到 429 rate limit 時自動等待後重試。"""
    for attempt in range(max_retries):
        try:
            return make_llm().invoke(prompt).content
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower():
                # 從錯誤訊息解析需等待秒數，例如 "Please try again in 28m34.176s"
                wait = 60  # 預設等 60 秒
                m = re.search(r'(\d+)m(\d+(?:\.\d+)?)s', msg)
                if m:
                    wait = int(m.group(1)) * 60 + float(m.group(2)) + 5
                else:
                    m2 = re.search(r'in (\d+(?:\.\d+)?)s', msg)
                    if m2:
                        wait = float(m2.group(1)) + 5
                print(f"\n⏳ Rate limit 觸發，等待 {wait:.0f} 秒後重試 (第 {attempt+1}/{max_retries} 次)...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"已重試 {max_retries} 次，仍然失敗")
