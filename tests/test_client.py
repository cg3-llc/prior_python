"""Tests for PriorClient with mocked HTTP."""

import json
from unittest.mock import patch, MagicMock

import pytest

from prior_tools.client import PriorClient


@pytest.fixture
def mock_config():
    return {
        "base_url": "https://test.example.com",
        "api_key": "ask_test_key",
        "agent_id": "ag_test_001",
    }


@pytest.fixture
def client(mock_config):
    with patch("prior_tools.client.load_config", return_value=mock_config):
        return PriorClient()


class TestSearch:
    def test_search_basic(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": [{"id": "k_1", "title": "Test"}]}
        mock_resp.content = b'{"results": []}'

        with patch("requests.request", return_value=mock_resp) as mock_req:
            result = client.search("test query", context={"runtime": "python"})
            mock_req.assert_called_once()
            call_kwargs = mock_req.call_args
            assert "/v1/knowledge/search" in call_kwargs[0][1]
            body = call_kwargs[1]["json"]
            assert body["context"] == {"runtime": "python"}

    def test_search_with_context(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.content = b'{"results": []}'

        with patch("requests.request", return_value=mock_resp) as mock_req:
            client.search("test", context={"runtime": "openclaw", "os": "windows"})
            body = mock_req.call_args[1]["json"]
            assert body["context"] == {"runtime": "openclaw", "os": "windows"}


class TestContribute:
    def test_contribute(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "k_new", "status": "active"}
        mock_resp.content = b'{}'

        with patch("requests.request", return_value=mock_resp) as mock_req:
            result = client.contribute("Title", "Content " * 20, tags=["test"], model="claude-opus-4")
            body = mock_req.call_args[1]["json"]
            assert body["title"] == "Title"
            assert body["tags"] == ["test"]
            assert body["model"] == "claude-opus-4"


class TestFeedback:
    def test_useful_feedback(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "recorded"}
        mock_resp.content = b'{}'

        with patch("requests.request", return_value=mock_resp) as mock_req:
            client.feedback("k_1", "useful", notes="worked great")
            body = mock_req.call_args[1]["json"]
            assert body["outcome"] == "useful"


class TestNoApiKey:
    def test_raises_when_no_key(self):
        config = {"base_url": "https://test.example.com", "api_key": None, "agent_id": None}
        with patch("prior_tools.client.load_config", return_value=config):
            with pytest.raises(RuntimeError, match="No API key configured"):
                PriorClient()


class TestStatus:
    def test_me(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"agentId": "ag_test", "credits": 100}
        mock_resp.content = b'{}'

        with patch("requests.request", return_value=mock_resp):
            result = client.me()
            assert result["agentId"] == "ag_test"
