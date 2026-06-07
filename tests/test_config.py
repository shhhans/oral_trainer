from app.config import get_settings


def test_settings_have_defaults():
    s = get_settings()
    assert s.minimax_llm_model  # 默认非空
    assert s.data_dir == "data"
