import json
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from llm_client import summarize_repo
from repo_fetcher import fetch_repo_content

app = Flask(__name__)


def _error(message: str, status_code: int):
    return jsonify({"status": "error", "message": message}), status_code


@app.post("/summarize")
def summarize():
    body = request.get_json(silent=True)
    if not body or not isinstance(body.get("github_url"), str):
        logger.warning("Invalid request: missing or invalid github_url")
        return _error("Missing or invalid 'github_url' in request body", 400)

    github_url = body["github_url"].strip()
    if not github_url:
        logger.warning("Invalid request: github_url cannot be empty")
        return _error("'github_url' cannot be empty", 400)

    logger.info("Summarize request for github_url=%s", github_url)
    try:
        repo_content = fetch_repo_content(github_url)
    except ValueError as e:
        logger.warning("Invalid github_url: %s", e)
        return _error(str(e), 400)
    except Exception as e:
        logger.warning("Failed to fetch repo: %s", e)
        status = getattr(getattr(e, "response", None), "status_code", 500)
        if status == 404:
            return _error("Repository not found (may be private or does not exist)", 404)
        if status == 403:
            return _error("GitHub API rate limit exceeded or access denied", 403)
        return _error(f"Failed to fetch repository: {e}", 502)

    logger.info("Fetched repo content, size=%d chars", len(repo_content))
    try:
        result = summarize_repo(repo_content)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON response")
        return _error("LLM returned invalid JSON response", 502)
    except RuntimeError as e:
        logger.warning("LLM config error: %s", e)
        return _error(str(e), 500)
    except Exception as e:
        logger.warning("LLM summarization failed: %s", e)
        return _error(f"LLM summarization failed: {e}", 502)

    logger.info("Summarization complete for %s", github_url)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
