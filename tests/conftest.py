def pytest_addoption(parser):
    parser.addoption(
        "--recognition-model",
        default=None,
        help="Verified local model directory for explicit recognition tests",
    )

    parser.addoption(
        "--recognition-installed-path",
        default=None,
        help="Require recognition to import the installed app from this directory",
    )

    parser.addoption(
        "--recognition-device",
        choices=("cpu", "cuda"),
        default="cpu",
        help="Explicit backend for opt-in recognition; cuda requires real GPU hardware",
    )
