import importlib.util
from pathlib import Path
import tarfile
import zipfile

import pytest


def checker():
    spec = importlib.util.spec_from_file_location(
        "dist_check", Path(__file__).resolve().parents[1] / "scripts/check-dist.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "expression", ["MIT", "AGPL-3.0-only"], ids=["stale-licence", "missing-notices"]
)
def test_distributions_reject_stale_licensing_or_missing_notices(tmp_path, expression):
    with zipfile.ZipFile(tmp_path / "app.whl", "w") as wheel:
        wheel.writestr(
            "app.dist-info/entry_points.txt", "tays = type_as_you_speak.cli:main"
        )
        wheel.writestr("type_as_you_speak/gui.py", "")
        wheel.writestr(
            "app.dist-info/METADATA",
            f"Metadata-Version: 2.4\nLicense-Expression: {expression}\n",
        )
    with tarfile.open(tmp_path / "app.tar.gz", "w:gz"):
        pass
    with pytest.raises(ValueError, match="licen[cs]"):
        checker().check_distributions(tmp_path)
