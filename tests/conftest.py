def pytest_addoption(parser):
    parser.addoption(
        "--recognition-model",
        default=None,
        help="Verified local model directory for explicit recognition tests",
    )
