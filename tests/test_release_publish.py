import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
@pytest.mark.parametrize("upload_failure", [False, True])
def test_release_is_only_published_after_draft_asset_uploads(tmp_path, upload_failure):
    script = Path(__file__).resolve().parents[1] / "scripts/publish-release.sh"
    fake = tmp_path / "gh"
    fake.write_text("""#!/usr/bin/env python3
import json, os, sys
with open(os.environ['TAYS_GH_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[2] == 'create' and os.environ['TAYS_UPLOAD_FAIL'] == '1':
    sys.exit(1)
""")
    fake.chmod(0o755)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "example.whl").write_text("public test artifact")
    log = tmp_path / "commands"
    env = dict(
        os.environ,
        PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        TAYS_GH_LOG=str(log),
        TAYS_UPLOAD_FAIL=str(int(upload_failure)),
    )
    result = subprocess.run(
        ["bash", str(script), "v9.9.9", str(assets)],
        env=env,
        capture_output=True,
        text=True,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert "--draft" in commands[0] and "--generate-notes" in commands[0]
    assert str(assets / "example.whl") in commands[0]
    if upload_failure:
        assert result.returncode != 0
        assert not any(command[1] == "edit" for command in commands)
    else:
        assert result.returncode == 0, result.stderr
        assert commands[1] == ["release", "edit", "v9.9.9", "--draft=false"]


@pytest.mark.skipif(os.name == "nt", reason="release publisher runs on Linux")
@pytest.mark.parametrize(
    "draft,remote_asset,upload_failure,success",
    [
        ("true", "example.whl", False, True),
        ("true", "", False, True),
        ("true", "example.whl", True, False),
        ("false", "example.whl", False, False),
        ("true", "unexpected.whl", False, False),
        ("true", "../private.whl", False, False),
        ("unknown", "example.whl", False, False),
    ],
)
@pytest.mark.parametrize("tag_exists", [True, False])
def test_retry_only_resumes_a_matching_draft(
    tmp_path, draft, remote_asset, upload_failure, success, tag_exists
):
    script = Path(__file__).resolve().parents[1] / "scripts/publish-release.sh"
    fake = tmp_path / "gh"
    fake.write_text("""#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
with open(os.environ['TAYS_GH_LOG'], 'a') as log:
    log.write(json.dumps(args)+'\\n')
if args[0]=='api' and os.environ['TAYS_TAG_EXISTS']=='0': sys.exit(1)
if args[1]=='create': sys.exit(1)
if args[1]=='view':
    print(os.environ['TAYS_DRAFT'] if 'isDraft' in args else os.environ['TAYS_REMOTE_ASSET'])
if args[1]=='upload' and os.environ['TAYS_UPLOAD_FAIL']=='1': sys.exit(1)
""")
    fake.chmod(0o755)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "example.whl").write_text("public artifact")
    (tmp_path / "private.whl").write_text("outside the asset inventory")
    log = tmp_path / "commands"
    env = dict(
        os.environ,
        PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        TAYS_GH_LOG=str(log),
        TAYS_TAG_EXISTS=str(int(tag_exists)),
        TAYS_DRAFT=draft,
        TAYS_REMOTE_ASSET=remote_asset,
        TAYS_UPLOAD_FAIL=str(int(upload_failure)),
    )
    result = subprocess.run(
        ["bash", str(script), "v9.9.9", str(assets)],
        env=env,
        capture_output=True,
        text=True,
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    edits = [c for c in commands if c[1] == "edit"]
    uploads = [c for c in commands if c[1] == "upload"]
    success = success and tag_exists
    assert (result.returncode == 0) is success
    assert bool(edits) is success
    if success:
        assert "--clobber" in uploads[0]
        assert str(assets / "example.whl") in uploads[0]
    if draft != "true" or remote_asset not in ("", "example.whl") or not tag_exists:
        assert uploads == []


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
