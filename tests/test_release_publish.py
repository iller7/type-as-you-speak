"""The publisher seals a DRAFT release only after every verified asset is on it.

release-please creates the draft (with notes) when the release PR merges; the
publisher's job is to supply the assets and seal. A published release is never
modified, and a draft carrying unrecognised assets is reviewed, not clobbered.
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['TAYS_GH_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if args[0] != 'release':
    sys.exit(0)
cmd = args[1]
if cmd == 'view' and 'isDraft' in args:
    state = os.environ.get('TAYS_STATE', 'missing')
    if state == 'missing':
        sys.exit(1)
    print('true' if state == 'draft' else 'false')
elif cmd == 'view' and 'assets' in args:
    for name in filter(None, os.environ.get('TAYS_REMOTE_ASSETS', '').split(',')):
        print(name)
elif cmd == 'create' and os.environ.get('TAYS_CREATE_FAIL') == '1':
    sys.exit(1)
elif cmd == 'upload' and os.environ.get('TAYS_UPLOAD_FAIL') == '1':
    sys.exit(1)
"""


def run_publisher(tmp_path, env_overrides):
    script = Path(__file__).resolve().parents[1] / "scripts/publish-release.sh"
    fake = tmp_path / "gh"
    fake.write_text(FAKE_GH)
    fake.chmod(0o755)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "example.whl").write_text("public test artifact")
    (tmp_path / "private.whl").write_text("outside the asset inventory")
    log = tmp_path / "commands"
    env = dict(
        os.environ,
        PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        TAYS_GH_LOG=str(log),
        **env_overrides,
    )
    result = subprocess.run(
        ["bash", str(script), "v9.9.9", str(assets)],
        env=env,
        capture_output=True,
        text=True,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    return result, assets, commands


def assert_outcome(result, commands, expect, assets):
    creates = [c for c in commands if c[1] == "create"]
    uploads = [c for c in commands if c[1] == "upload"]
    edits = [c for c in commands if c[1] == "edit"]
    assert (result.returncode == 0) is expect["success"], (
        result.stderr,
        commands,
    )
    assert bool(creates) is expect["create"]
    if expect["create"]:
        assert "--draft" in creates[0] and "--generate-notes" in creates[0]
    assert bool(uploads) is expect["upload"]
    if expect["upload"]:
        assert "--clobber" in uploads[0]
        assert str(assets / "example.whl") in uploads[0]
    sealed = bool(edits) and edits[-1] == ["release", "edit", "v9.9.9", "--draft=false"]
    assert sealed is expect["seal"]
    if expect["seal"]:
        assert edits[-1] == commands[-1]


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
@pytest.mark.parametrize(
    "state,remote_assets",
    [
        pytest.param("draft", "", id="release-please-draft"),
        pytest.param("draft", "example.whl", id="resume-partial-draft"),
    ],
)
def test_seals_the_release_draft_once_assets_are_uploaded(
    tmp_path, state, remote_assets
):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": state, "TAYS_REMOTE_ASSETS": remote_assets},
    )
    assert_outcome(
        result,
        commands,
        {"success": True, "create": False, "upload": True, "seal": True},
        assets,
    )


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
def test_upload_failure_keeps_the_release_unsealed(tmp_path):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": "draft", "TAYS_UPLOAD_FAIL": "1"},
    )
    assert_outcome(
        result,
        commands,
        {"success": False, "create": False, "upload": True, "seal": False},
        assets,
    )


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
def test_published_release_is_never_modified(tmp_path):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": "published"},
    )
    assert_outcome(
        result,
        commands,
        {"success": False, "create": False, "upload": False, "seal": False},
        assets,
    )
    assert "Refusing" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
def test_manual_tag_gets_a_draft_then_seal(tmp_path):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": "missing"},
    )
    assert_outcome(
        result,
        commands,
        {"success": True, "create": True, "upload": True, "seal": True},
        assets,
    )


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
def test_manual_tag_create_failure_stops_before_upload(tmp_path):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": "missing", "TAYS_CREATE_FAIL": "1"},
    )
    assert_outcome(
        result,
        commands,
        {"success": False, "create": True, "upload": False, "seal": False},
        assets,
    )


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
@pytest.mark.parametrize(
    "remote_asset",
    [
        pytest.param("unexpected.whl", id="foreign-asset"),
        pytest.param("../private.whl", id="path-traversal"),
    ],
)
def test_unrecognised_draft_assets_are_reviewed_not_clobbered(tmp_path, remote_asset):
    result, assets, commands = run_publisher(
        tmp_path,
        {"TAYS_STATE": "draft", "TAYS_REMOTE_ASSETS": remote_asset},
    )
    assert_outcome(
        result,
        commands,
        {"success": False, "create": False, "upload": False, "seal": False},
        assets,
    )


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
def test_empty_inventory_fails_before_contacting_github(tmp_path):
    fake = tmp_path / "gh"
    marker = tmp_path / "called"
    fake.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
    fake.chmod(0o755)
    assets = tmp_path / "assets"
    assets.mkdir()
    script = Path(__file__).resolve().parents[1] / "scripts/publish-release.sh"
    result = subprocess.run(
        ["bash", str(script), "v9.9.9", str(assets)],
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "No release assets" in result.stderr
    assert not marker.exists()
