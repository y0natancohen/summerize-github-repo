import json
from unittest.mock import patch

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestSummarizeEndpoint:
    def test_missing_body(self, client):
        resp = client.post("/summarize", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_github_url(self, client):
        resp = client.post("/summarize", json={"foo": "bar"})
        assert resp.status_code == 400
        assert "github_url" in resp.get_json()["message"]

    def test_empty_github_url(self, client):
        resp = client.post("/summarize", json={"github_url": ""})
        assert resp.status_code == 400

    def test_invalid_github_url(self, client):
        resp = client.post("/summarize", json={"github_url": "https://gitlab.com/a/b"})
        assert resp.status_code == 400
        assert "Not a GitHub URL" in resp.get_json()["message"]

    @patch("app.summarize_repo")
    @patch("app.fetch_repo_content")
    def test_success(self, mock_fetch, mock_summarize, client):
        mock_fetch.return_value = "repo content here"
        mock_summarize.return_value = {
            "summary": "A Python library.",
            "technologies": ["Python"],
            "structure": "Standard layout.",
        }
        resp = client.post("/summarize", json={"github_url": "https://github.com/psf/requests"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data
        assert "technologies" in data
        assert "structure" in data

    @patch("app.fetch_repo_content")
    def test_repo_not_found(self, mock_fetch, client):
        from requests.exceptions import HTTPError
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = HTTPError(response=mock_resp)
        mock_fetch.side_effect = exc

        resp = client.post("/summarize", json={"github_url": "https://github.com/nonexistent/repo"})
        assert resp.status_code == 404

    @patch("app.summarize_repo")
    @patch("app.fetch_repo_content")
    def test_llm_error(self, mock_fetch, mock_summarize, client):
        mock_fetch.return_value = "content"
        mock_summarize.side_effect = Exception("API timeout")

        resp = client.post("/summarize", json={"github_url": "https://github.com/psf/requests"})
        assert resp.status_code == 502
        assert "error" in resp.get_json()["status"]
