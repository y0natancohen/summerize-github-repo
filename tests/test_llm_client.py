import json
from unittest.mock import patch, MagicMock

import pytest

from llm_client import _parse_response, _cache_key, summarize_repo


class TestParseResponse:
    def test_valid_json(self):
        raw = json.dumps({
            "summary": "A test project.",
            "technologies": ["Python"],
            "structure": "Simple layout.",
        })
        result = _parse_response(raw)
        assert result["summary"] == "A test project."
        assert result["technologies"] == ["Python"]
        assert result["structure"] == "Simple layout."

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"summary": "Test", "technologies": ["Go"], "structure": "Flat."}\n```'
        result = _parse_response(raw)
        assert result["summary"] == "Test"

    def test_missing_summary(self):
        raw = json.dumps({"technologies": ["Python"], "structure": "Flat."})
        with pytest.raises(ValueError, match="summary"):
            _parse_response(raw)

    def test_missing_technologies(self):
        raw = json.dumps({"summary": "Test", "structure": "Flat."})
        with pytest.raises(ValueError, match="technologies"):
            _parse_response(raw)

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_response("not json at all")


class TestCacheKey:
    def test_deterministic(self):
        assert _cache_key("hello") == _cache_key("hello")

    def test_different_inputs(self):
        assert _cache_key("hello") != _cache_key("world")


class TestSummarizeRepo:
    @patch("llm_client._call_llm")
    def test_returns_parsed_result(self, mock_call):
        mock_call.return_value = json.dumps({
            "summary": "A web app.",
            "technologies": ["Python", "Flask"],
            "structure": "Standard layout.",
        })
        result = summarize_repo("some repo content")
        assert result["summary"] == "A web app."
        assert "Flask" in result["technologies"]
        mock_call.assert_called_once()

    @patch("llm_client._call_llm")
    def test_raises_on_bad_llm_response(self, mock_call):
        mock_call.return_value = "this is not json"
        with pytest.raises(json.JSONDecodeError):
            summarize_repo("some content")
