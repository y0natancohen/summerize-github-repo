import pytest
from unittest.mock import patch, MagicMock

from repo_fetcher import (
    parse_github_url,
    _should_skip,
    _file_priority,
    build_tree_string,
    fetch_repo_content,
)


class TestParseGithubUrl:
    def test_standard_url(self):
        assert parse_github_url("https://github.com/psf/requests") == ("psf", "requests")

    def test_trailing_slash(self):
        assert parse_github_url("https://github.com/psf/requests/") == ("psf", "requests")

    def test_git_suffix(self):
        assert parse_github_url("https://github.com/psf/requests.git") == ("psf", "requests")

    def test_www_prefix(self):
        assert parse_github_url("https://www.github.com/psf/requests") == ("psf", "requests")

    def test_with_extra_path(self):
        owner, repo = parse_github_url("https://github.com/psf/requests/tree/main/src")
        assert (owner, repo) == ("psf", "requests")

    def test_invalid_host(self):
        with pytest.raises(ValueError, match="Not a GitHub URL"):
            parse_github_url("https://gitlab.com/user/repo")

    def test_missing_repo(self):
        with pytest.raises(ValueError, match="Cannot parse owner/repo"):
            parse_github_url("https://github.com/psf")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            parse_github_url("")


class TestShouldSkip:
    def test_skip_node_modules(self):
        assert _should_skip("node_modules/package/index.js") is True

    def test_skip_lock_file(self):
        assert _should_skip("package-lock.json") is True

    def test_skip_binary_ext(self):
        assert _should_skip("image.png") is True

    def test_skip_pyc(self):
        assert _should_skip("module/__pycache__/foo.pyc") is True

    def test_allow_python(self):
        assert _should_skip("src/main.py") is False

    def test_allow_readme(self):
        assert _should_skip("README.md") is False

    def test_skip_nested_vendor(self):
        assert _should_skip("some/vendor/lib.go") is True


class TestFilePriority:
    def test_readme_highest(self):
        assert _file_priority("README.md") == 0

    def test_config_high(self):
        assert _file_priority("package.json") == 1

    def test_root_file(self):
        assert _file_priority("main.py") == 2

    def test_nested_lower(self):
        assert _file_priority("src/utils/helper.py") > _file_priority("src/main.py")

    def test_priority_order(self):
        files = ["src/lib/deep.py", "setup.py", "README.md", "src/app.py"]
        sorted_files = sorted(files, key=_file_priority)
        assert sorted_files[0] == "README.md"


class TestBuildTreeString:
    def test_basic_tree(self):
        files = [{"path": "README.md"}, {"path": "src/main.py"}]
        tree = build_tree_string(files)
        assert "README.md" in tree
        assert "main.py" in tree


class TestFetchRepoContent:
    @patch("repo_fetcher.fetch_file_content")
    @patch("repo_fetcher.fetch_repo_tree")
    def test_assembles_content(self, mock_tree, mock_file):
        mock_tree.return_value = [
            {"path": "README.md", "type": "blob"},
            {"path": "src/main.py", "type": "blob"},
        ]
        mock_file.side_effect = lambda o, r, p: f"content of {p}"

        result = fetch_repo_content("https://github.com/test/repo")
        assert "test/repo" in result
        assert "README.md" in result
        assert "content of README.md" in result

    @patch("repo_fetcher.fetch_file_content")
    @patch("repo_fetcher.fetch_repo_tree")
    def test_skips_binary_files(self, mock_tree, mock_file):
        mock_tree.return_value = [
            {"path": "README.md", "type": "blob"},
            {"path": "logo.png", "type": "blob"},
        ]
        mock_file.return_value = "readme content"

        result = fetch_repo_content("https://github.com/test/repo")
        assert "logo.png" not in result or "```\nreadme content" in result
