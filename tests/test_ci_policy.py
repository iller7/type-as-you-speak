import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def policy():
    spec = importlib.util.spec_from_file_location(
        "ci_policy", ROOT / "scripts/ci-policy.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "docs/install.md",
        "docs/assets/site.css",
        "docs/_data/navigation.yml",
    ],
)
def test_static_documentation_is_eligible(path):
    assert policy().documentation_only([("100644", "100644", path)])


@pytest.mark.parametrize(
    "path",
    [
        "src/app.py",
        "tests/test_app.py",
        "scripts/check.py",
        "packaging/containers/fedora.Dockerfile",
        "pyproject.toml",
        "uv.lock",
        "LICENSE",
        "NOTICE",
        "COMMERCIAL.md",
        ".github/workflows/ci.yml",
        "docs/tool.py",
        "docs/setup.sh",
        "docs/default.toml",
        "other/README.md",
        "../docs/index.md",
        "/docs/index.md",
        "docs/../src/readme.md",
        "docs/\nindex.md",
    ],
)
def test_runtime_unknown_and_ambiguous_paths_require_full_validation(path):
    assert not policy().documentation_only([("100644", "100644", path)])


@pytest.mark.parametrize(
    "modes",
    [
        ("120000", "100644"),
        ("000000", "120000"),
        ("100755", "100644"),
        ("100644", "100755"),
    ],
)
def test_symlinks_and_executable_files_require_full_validation(modes):
    assert not policy().documentation_only([(*modes, "docs/install.md")])


def test_empty_or_mixed_changes_require_full_validation():
    module = policy()
    assert not module.documentation_only([])
    assert not module.documentation_only(
        [("100644", "100644", "README.md"), ("100644", "100644", "src/app.py")]
    )
    assert module.documentation_only(
        [("100644", "000000", "docs/old.md"), ("000000", "100644", "docs/new.md")]
    )


@pytest.mark.parametrize(
    "event", ["push", "schedule", "workflow_dispatch", "merge_group", "unknown"]
)
def test_non_pr_events_always_require_full_validation(event):
    assert policy().full_validation(event, None)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [],
        {"pull_request": {}},
        {"pull_request": {"base": {"sha": "invalid"}, "head": {"sha": "also-invalid"}}},
    ],
)
def test_missing_or_invalid_event_data_falls_back_to_full_validation(payload):
    assert policy().full_validation("pull_request", payload)


@pytest.mark.parametrize(
    "full,required,conditional,expected",
    [
        ("true", ["success"], "success", True),
        ("true", ["success", "success"], "success", True),
        ("false", ["success"], "skipped", True),
        ("false", ["success", "success"], "skipped", True),
        ("true", ["success"], "skipped", False),
        ("true", ["success"], "failure", False),
        ("true", ["success"], "cancelled", False),
        ("false", ["success"], "failure", False),
        ("false", ["success"], "cancelled", False),
        ("false", ["success"], "success", False),
        ("true", ["failure"], "success", False),
        ("false", ["skipped"], "skipped", False),
        ("true", ["success", "cancelled"], "success", False),
        ("false", ["success", "failure"], "skipped", False),
        ("true", [], "success", False),
        ("", ["success"], "skipped", False),
        ("garbage", ["success"], "success", False),
        ("false", ["success"], "", False),
    ],
)
def test_required_gate_rejects_failures_cancellations_and_unexpected_skips(
    full, required, conditional, expected
):
    assert policy().gate_passes(full, required, conditional) is expected


@pytest.mark.parametrize(
    "raw",
    [
        b"not-raw",
        b":100644 100644 a b R100\0docs/a.md\0",
        b":100644 100644 a b M\0docs/\xff.md\0",
    ],
)
def test_malformed_git_output_is_rejected(raw):
    with pytest.raises((ValueError, UnicodeError)):
        policy().parse_changes(raw)


@pytest.mark.skipif(
    shutil.which("git") is None, reason="Git is required to reproduce a PR merge"
)
@pytest.mark.parametrize(
    "changed_path,rename_from,expected_full",
    [
        ("docs/guide.md", None, False),
        ("src/app.py", None, True),
        ("docs/app.md", "src/app.py", True),
        ("docs/readme.md", "README.md", False),
    ],
)
def test_actual_merge_diff_and_checkout_identity(
    tmp_path, changed_path, rename_from, expected_full
):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=tmp_path,
            env=env,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

    git("init", "-b", "main")
    git("config", "user.name", "CI test")
    git("config", "user.email", "ci@example.invalid")
    (tmp_path / "README.md").write_text("base\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("base code\n")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-b", "feature")
    target = tmp_path / changed_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if rename_from:
        shutil.move(tmp_path / rename_from, target)
    else:
        target.write_text("change\n")
    git("add", ".")
    git("commit", "-m", "change")
    head = git("rev-parse", "HEAD")
    payload = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
    assert policy().full_validation("pull_request", payload, tmp_path)
    git("checkout", "main")
    git("merge", "--no-ff", "feature", "-m", "PR merge")
    assert policy().full_validation("pull_request", payload, tmp_path) is expected_full
    payload["pull_request"]["head"]["sha"] = base
    assert policy().full_validation("pull_request", payload, tmp_path)


def test_selection_cli_publishes_only_a_known_boolean(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci-policy.py"), "select"],
        env={
            **os.environ,
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output.read_text() == "full=true\n"


@pytest.mark.parametrize(
    "full,conditional,expected",
    [
        ("true", "success", 0),
        ("true", "skipped", 1),
        ("false", "skipped", 0),
        ("false", "failure", 1),
    ],
)
def test_gate_cli_exit_status(full, conditional, expected):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ci-policy.py"),
            "gate",
            "--full",
            full,
            "--required",
            "success",
            "--conditional",
            conditional,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected


@pytest.mark.parametrize(
    "error",
    [
        OSError("git unavailable"),
        subprocess.CalledProcessError(1, "git"),
        subprocess.TimeoutExpired("git", 20),
    ],
)
def test_git_failure_or_timeout_requires_full_validation(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "check_output", fail)
    payload = {"pull_request": {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}}
    assert policy().full_validation("pull_request", payload)
