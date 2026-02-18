import hashlib
import json
import os

import diskcache
from openai import OpenAI

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
  "required": ["title", "bullets", "confidence"],
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
    print(f"Calling LLM with model {MODEL}")
    print(f"Repo content: {repo_content[:1000]}... (truncated)")
        
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
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
    print(type(response.choices[0].message.content))
    print(response.choices[0].message.content)
    return response.choices[0].message.content


def _parse_response(raw: str) -> dict:
    """Parse and validate LLM JSON response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    data = json.loads(text)
    if not isinstance(data.get("summary"), str):
        raise ValueError("Missing or invalid 'summary' field")
    if not isinstance(data.get("technologies"), list):
        raise ValueError("Missing or invalid 'technologies' field")
    if not isinstance(data.get("structure"), str):
        raise ValueError("Missing or invalid 'structure' field")
    return {
        "summary": data["summary"],
        "technologies": data["technologies"],
        "structure": data["structure"],
    }


def summarize_repo(repo_content: str) -> dict:
    """Generate a structured summary from repo content. Returns dict with summary, technologies, structure."""
    content_hash = _cache_key(repo_content)
    raw = _call_llm(content_hash, repo_content)
    return _parse_response(raw)
