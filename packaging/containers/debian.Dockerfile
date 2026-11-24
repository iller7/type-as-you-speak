ARG BASE_IMAGE=ubuntu:24.04@sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b
FROM ${BASE_IMAGE} AS build
ENV DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1 QT_QPA_PLATFORM=offscreen
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates curl cmake build-essential \
    libfontconfig1 libegl1 libopengl0 libgl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3 \
    desktop-file-utils appstream && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /tools
ENV PATH="/tools/bin:${PATH}"
RUN pip install --no-cache-dir uv==0.13.9
ENV UV_PYTHON=/usr/bin/python3 UV_PYTHON_DOWNLOADS=never
WORKDIR /work
COPY . .
RUN uv sync --locked --python /usr/bin/python3 --extra gui
ENV PATH="/work/.venv/bin:/tools/bin:${PATH}"
RUN uv run --locked pytest && uv run --locked python -m build --no-isolation && uv run --locked twine check dist/*.whl dist/*.tar.gz
RUN desktop-file-validate data/type-as-you-speak.desktop && appstreamcli validate --no-net data/type-as-you-speak.metainfo.xml
RUN bash packaging/deb/build-deb.sh
FROM ${BASE_IMAGE} AS smoke
ENV DEBIAN_FRONTEND=noninteractive QT_QPA_PLATFORM=offscreen
COPY --from=build /work/dist/*.deb /packages/
RUN apt-get update && apt-get install -y --no-install-recommends /packages/*.deb && \
    tays --version && tays --help && \
    /usr/bin/python3 -c 'import sys; sys.path.insert(0,"/opt/type-as-you-speak/pydeps"); import numpy, onnxruntime, faster_whisper; from PySide6.QtWidgets import QApplication; app=QApplication([])'
FROM scratch AS artifacts
COPY --from=smoke /packages/ /
