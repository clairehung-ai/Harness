import os

MAX_ROUNDS: int = 3
MAX_RED_LIGHT_ROUNDS: int = 2
MODEL: str = os.environ.get("HARNESS_MODEL", "nvidia/nemotron-3-nano-omni")
SANDBOX_TIMEOUT: int = 10

# LLM Server 設定（OpenAI 相容 endpoint）
LLM_BASE_URL: str = os.environ.get("HARNESS_BASE_URL", "http://192.168.71.25:1234/v1")
LLM_API_KEY: str = os.environ.get("HARNESS_API_KEY", "none")
LLM_MAX_TOKENS: int = int(os.environ.get("HARNESS_MAX_TOKENS", "4096"))
