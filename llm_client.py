import hashlib
import json
import logging
import os

import diskcache
from openai import OpenAI

logger = logging.getLogger(__name__)

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
MODEL = os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL)

cache = diskcache.Cache("./cache_dir")

SYSTEM_PROMPT = """You are a software project analyst. Given repository contents (directory tree and key files), produce a JSON object with exactly these fields:

- "summary": A clear, human-readable description of what the project does (2-4 sentences).
- "technologies": A JSON array of the main languages, frameworks, and libraries used.
- "structure": A brief description of how the project is organized (1-2 sentences).

Respond ONLY with valid JSON, no markdown fences, no extra text."""

answer_schema = {
  "type": "object",
  "properties": {
    "summary": {"type": "string"},
    "technologies": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "structure": {"type": "string"}
  },
  "required": ["summary", "technologies", "structure"],
  "additionalProperties": False
}


def _get_client() -> OpenAI:
    api_key = os.environ.get("NEBIUS_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        raise RuntimeError("NEBIUS_API_KEY environment variable is not set")
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key)


def _cache_key(repo_content: str) -> str:
    return hashlib.sha256(repo_content.encode()).hexdigest()


@cache.memoize(typed=True, tag="llm")
def _call_llm(content_hash: str, repo_content: str) -> str:
    """Call Nebius LLM API. Cached by content hash to avoid duplicate calls."""
    
    client = _get_client()
    logger.info("Calling LLM with model %s", MODEL)
    logger.info("Repo content: %s... (truncated)", repo_content[:100])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": repo_content
                    }
                ]
            }
        ],
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "answer",
            "strict": True,
            "schema": answer_schema
        }
    }
    )
    return response.choices[0].message.content


def _parse_response(raw: str) -> dict:
    """Parse and validate LLM JSON response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON response from LLM")
    
    if not isinstance(data.get("summary"), str):
        raise ValueError("Missing or invalid 'summary' field")
    if not isinstance(data.get("technologies"), list):
        raise ValueError("Missing or invalid 'technologies' field")
    if not isinstance(data.get("structure"), str):
        raise ValueError("Missing or invalid 'structure' field")
    
    return data


def summarize_repo(repo_content: str) -> dict:
    """Generate a structured summary from repo content. Returns dict with summary, technologies, structure."""
    content_hash = _cache_key(repo_content)
    raw = _call_llm(content_hash, repo_content)
    data = _parse_response(raw)
    return data
