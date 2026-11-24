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
        assert len(commands) == 1
    else:
        assert result.returncode == 0, result.stderr
        assert commands[1] == ["release", "edit", "v9.9.9", "--draft=false"]
