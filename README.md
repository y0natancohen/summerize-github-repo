# GitHub Repository Summarizer API

A Flask API that takes a GitHub repository URL and returns a structured summary using an LLM.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key in `.env`:

```
NEBIUS_API_KEY=your_actual_key_here
```

Optionally set the LLM model (default: `meta-llama/Llama-3.3-70B-Instruct`):

```
NEBIUS_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

## Run

```bash
python app.py
```

Server starts on `http://localhost:8000`.

## Usage

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

## Tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

## Design Decisions

**Model**: Configurable via `NEBIUS_MODEL` env var (default: `meta-llama/Llama-3.3-70B-Instruct`). Fast, strong at instruction following and structured JSON output, cost-effective for summarization tasks.

**Repo processing**: Files are fetched via the GitHub REST API (no cloning). The tree is retrieved recursively, then filtered to skip binary files, lock files, vendor directories, `node_modules/`, dotfiles (names starting with `.`), images, and compiled artifacts. Remaining files are prioritized: README first, then config/manifest files (`package.json`, `pyproject.toml`, etc.), then top-level source files, then deeper files. Content is accumulated up to a ~60k character budget to stay within context limits.

**Caching**: All LLM API calls are wrapped with a `diskcache.memoize` decorator. Identical repo contents (by SHA-256 hash) return cached results without making API calls.

## Troubleshooting

**Model 404 error** (model does not exist): Model availability can vary by Nebius account, project, or region. List models available for your account:

```bash
curl -s "https://api.tokenfactory.nebius.com/v1/models" \
  -H "Authorization: Bearer $NEBIUS_API_KEY" | jq '.data[].id'
```

Set `NEBIUS_MODEL` in `.env` to one of the returned IDs. Nebius-documented alternatives: `meta-llama/Meta-Llama-3.1-8B-Instruct`, `meta-llama/Meta-Llama-3.1-8B-Instruct-fast`, `meta-llama/Llama-3.3-70B-Instruct`.
