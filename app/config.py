"""集中读取环境变量。所有外部 API key 只能从这里取,代码其它处不直接读 os.environ。"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_group_id: str = os.getenv("MINIMAX_GROUP_ID", "")
    minimax_llm_model: str = os.getenv("MINIMAX_LLM_MODEL", "MiniMax-M2")
    minimax_tts_model: str = os.getenv("MINIMAX_TTS_MODEL", "speech-02-turbo")
    speechace_api_key: str = os.getenv("SPEECHACE_API_KEY", "")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    data_dir: str = os.getenv("DATA_DIR", "data")
    dialogue_history_window: int = int(os.getenv("DIALOGUE_HISTORY_WINDOW", "8"))


def get_settings() -> Settings:
    return Settings()
