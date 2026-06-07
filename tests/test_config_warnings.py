import logging
import pytest
from app.config import warn_missing_keys


def test_warn_missing_keys_returns_missing_names(monkeypatch, caplog):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_GROUP_ID", raising=False)
    monkeypatch.delenv("SPEECHACE_API_KEY", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.config"):
        missing = warn_missing_keys()

    assert "MINIMAX_API_KEY" in missing
    assert "MINIMAX_GROUP_ID" in missing
    assert "SPEECHACE_API_KEY" in missing
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 3


def test_warn_missing_keys_no_warnings_when_all_set(monkeypatch, caplog):
    monkeypatch.setenv("MINIMAX_API_KEY", "key1")
    monkeypatch.setenv("MINIMAX_GROUP_ID", "grp1")
    monkeypatch.setenv("SPEECHACE_API_KEY", "key2")

    with caplog.at_level(logging.WARNING, logger="app.config"):
        missing = warn_missing_keys()

    assert missing == []
    assert not any(r.levelno == logging.WARNING for r in caplog.records)


def test_warn_missing_keys_partial(monkeypatch, caplog):
    monkeypatch.setenv("MINIMAX_API_KEY", "key1")
    monkeypatch.setenv("MINIMAX_GROUP_ID", "grp1")
    monkeypatch.delenv("SPEECHACE_API_KEY", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.config"):
        missing = warn_missing_keys()

    assert missing == ["SPEECHACE_API_KEY"]
