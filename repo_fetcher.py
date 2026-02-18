from urllib.parse import urlparse

import requests

GITHUB_API = "https://api.github.com"

SKIP_DIRS = {
    "node_modules", "vendor", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".tox", ".nox",
    "env", ".eggs", "eggs", ".mypy_cache", ".pytest_cache",
    "bower_components", "jspm_packages", ".terraform", ".gradle",
}

SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".o", ".a", ".dylib", ".dll", ".exe",
    ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".jar", ".war",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".min.js", ".min.css", ".map",
    ".lock", ".sum",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock",
    "poetry.lock", "composer.lock", "Gemfile.lock", "go.sum",
    ".DS_Store", "Thumbs.db",
}

CONFIG_FILES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py",
    "setup.cfg", "Cargo.toml", "go.mod", "Gemfile", "composer.json",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".github/workflows", "tsconfig.json", "webpack.config.js",
    "vite.config.ts", "vite.config.js", "CMakeLists.txt", "pom.xml",
    "build.gradle", "build.gradle.kts",
}

MAX_CONTENT_CHARS = 60_000
MAX_FILE_SIZE = 50_000
MAX_TREE_FILES = 500

_CONFIG_NAMES_LOWER = {f.split("/")[-1].lower() for f in CONFIG_FILES}


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo from a GitHub URL. Raises ValueError on invalid input."""
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parsed = urlparse(url)
    if parsed.hostname not in ("github.com", "www.github.com"):
        raise ValueError(f"Not a GitHub URL: {url}")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from: {url}")
    return parts[0], parts[1]


def _should_skip(path: str) -> bool:
    parts = path.split("/")
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return True
    filename = parts[-1]
    if filename in SKIP_FILES:
        return True
    if any(filename.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    return False


def _file_priority(path: str) -> int:
    """Lower number = higher priority."""
    name = path.split("/")[-1].lower()
    if name.startswith("readme"):
        return 0
    if name in _CONFIG_NAMES_LOWER:
        return 1
    depth = path.count("/")
    if depth == 0:
        return 2
    return 3 + depth


def fetch_repo_tree(owner: str, repo: str) -> list[dict]:
    """Fetch the recursive file tree from GitHub API. Raises requests.HTTPError on failure."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [item for item in tree if item.get("type") == "blob"]


def build_tree_string(files: list[dict]) -> str:
    """Build a directory-tree string from file entries."""
    paths = sorted(f["path"] for f in files)
    if len(paths) > MAX_TREE_FILES:
        paths = paths[:MAX_TREE_FILES]
        truncated = True
    else:
        truncated = False
    lines = []
    for p in paths:
        indent = "  " * p.count("/")
        lines.append(f"{indent}{p.split('/')[-1]}")
    tree = "\n".join(lines)
    if truncated:
        tree += f"\n... ({len(files) - MAX_TREE_FILES} more files)"
    return tree


def fetch_file_content(owner: str, repo: str, path: str) -> str | None:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
    resp = requests.get(url, timeout=15)
    if resp.status_code != 200:
        return None
    if len(resp.content) > MAX_FILE_SIZE:
        return resp.text[:MAX_FILE_SIZE] + "\n... (truncated)"
    try:
        return resp.text
    except Exception:
        return None


def fetch_repo_content(github_url: str) -> str:
    """Main entry: fetch and assemble repo content for LLM consumption.

    Returns a formatted string with directory tree and prioritized file contents.
    Raises ValueError for invalid URLs, requests.HTTPError for API errors.
    """
    owner, repo = parse_github_url(github_url)
    all_files = fetch_repo_tree(owner, repo)

    relevant = [f for f in all_files if not _should_skip(f["path"])]
    relevant.sort(key=lambda f: _file_priority(f["path"]))

    tree_str = build_tree_string(all_files)
    parts = [f"# Repository: {owner}/{repo}\n\n## Directory Structure\n```\n{tree_str}\n```\n"]
    total_chars = len(parts[0])

    for f in relevant:
        if total_chars >= MAX_CONTENT_CHARS:
            break
        content = fetch_file_content(owner, repo, f["path"])
        if not content or not content.strip():
            continue
        section = f"\n## File: {f['path']}\n```\n{content}\n```\n"
        if total_chars + len(section) > MAX_CONTENT_CHARS:
            remaining = MAX_CONTENT_CHARS - total_chars
            if remaining > 200:
                section = f"\n## File: {f['path']}\n```\n{content[:remaining - 100]}\n... (truncated)\n```\n"
                parts.append(section)
                total_chars += len(section)
            break
        parts.append(section)
        total_chars += len(section)

    return "".join(parts)
