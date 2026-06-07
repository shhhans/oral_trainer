"""集中读取环境变量。所有外部 API key 只能从这里取,代码其它处不直接读 os.environ。"""
import logging
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    minimax_api_key: str = ""
    minimax_group_id: str = ""
    minimax_llm_model: str = "MiniMax-M2"
    minimax_tts_model: str = "speech-02-turbo"
    speechace_api_key: str = ""
    speechace_base_url: str = "https://api2.speechace.com"
    minimax_voice_en_us: str = "English_Insightful_Speaker"
    minimax_voice_en_gb: str = "English_Graceful_Lady"
    speechace_dialect: str = "en-us"
    dashscope_api_key: str = ""
    data_dir: str = "data"
    dialogue_history_window: int = 8


def get_settings() -> Settings:
    """Read env vars fresh on each call so tests can monkeypatch os.environ."""
    return Settings(
        minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
        minimax_group_id=os.getenv("MINIMAX_GROUP_ID", ""),
        minimax_llm_model=os.getenv("MINIMAX_LLM_MODEL", "MiniMax-M2"),
        minimax_tts_model=os.getenv("MINIMAX_TTS_MODEL", "speech-02-turbo"),
        speechace_api_key=os.getenv("SPEECHACE_API_KEY", ""),
        speechace_base_url=os.getenv("SPEECHACE_BASE_URL", "https://api2.speechace.com"),
        minimax_voice_en_us=os.getenv("MINIMAX_VOICE_EN_US", "English_Insightful_Speaker"),
        minimax_voice_en_gb=os.getenv("MINIMAX_VOICE_EN_GB", "English_Graceful_Lady"),
        speechace_dialect=os.getenv("SPEECHACE_DIALECT", "en-us"),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        data_dir=os.getenv("DATA_DIR", "data"),
        dialogue_history_window=int(os.getenv("DIALOGUE_HISTORY_WINDOW", "8")),
    )


def warn_missing_keys() -> list[str]:
    """Log warnings for unconfigured API keys. Returns list of missing key names."""
    s = get_settings()
    missing: list[str] = []
    checks = [
        (s.minimax_api_key, "MINIMAX_API_KEY"),
        (s.minimax_group_id, "MINIMAX_GROUP_ID"),
        (s.speechace_api_key, "SPEECHACE_API_KEY"),
    ]
    for value, name in checks:
        if not value:
            logger.warning("Missing environment variable: %s — API calls will fail", name)
            missing.append(name)
    return missing
