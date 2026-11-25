ARG BASE_IMAGE=fedora:45@sha256:a7d72ba2745b100a3351087472e5ee7b2450af7cf331e7673007e3817612839c
FROM ${BASE_IMAGE} AS build
ARG EXPECTED_FEDORA
RUN test -z "$EXPECTED_FEDORA" || test "$(rpm -E %fedora)" = "$EXPECTED_FEDORA"
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 QT_QPA_PLATFORM=offscreen HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1
RUN dnf install -y python3-devel python3-pip rpm-build findutils gcc \
    desktop-file-utils appstream && dnf clean all
RUN if python3 -c 'import sys; sys.exit(sys.version_info < (3, 15))'; then \
      dnf install -y python3-onnxruntime && printf 'export TAYS_NATIVE_ONNX=1\n' > /build-profile.env; \
    else printf 'export TAYS_NATIVE_ONNX=0\n' > /build-profile.env; fi
RUN python3 -m venv /tools
ENV PATH="/tools/bin:${PATH}"
RUN pip install --no-cache-dir uv==0.13.9
ENV UV_PYTHON=/usr/bin/python3 UV_PYTHON_DOWNLOADS=never
WORKDIR /work
COPY . .
RUN python3 -c 'import subprocess; deps=subprocess.check_output(["rpmspec", "--query", "--buildrequires", "packaging/fedora/type-as-you-speak.spec"], text=True).splitlines(); subprocess.run(["dnf", "install", "-y", *deps], check=True)'
RUN . /build-profile.env && if [ "$TAYS_NATIVE_ONNX" = 1 ]; then \
      uv venv --system-site-packages --python /usr/bin/python3 .venv && \
      uv sync --locked --python /usr/bin/python3 --extra gui --no-install-package onnxruntime; \
    else uv sync --locked --python /usr/bin/python3 --extra gui; fi
ENV PATH="/work/.venv/bin:/tools/bin:${PATH}" UV_NO_SYNC=1
RUN python -m pip check && uv run --locked pytest && uv run --locked python -m build --no-isolation && \
    . /build-profile.env && bash scripts/prepare-wheelhouse.sh
RUN mkdir -p /root/rpmbuild/SOURCES && cp dist/*.tar.gz /root/rpmbuild/SOURCES/ && \
    tar -czf /root/rpmbuild/SOURCES/wheelhouse.tar.gz -C dist/wheelhouse .
RUN rpmbuild -ba --define '_binary_payload w3.zstdio' packaging/fedora/type-as-you-speak.spec && \
    rpm -qp --qf '%{NAME} %{ARCH}: %{PAYLOADCOMPRESSOR} flags=%{PAYLOADFLAGS}\n' /root/rpmbuild/RPMS/*/*.rpm && \
    ls -l /root/rpmbuild/RPMS/*/*.rpm
FROM ${BASE_IMAGE} AS smoke
ENV QT_QPA_PLATFORM=offscreen
COPY --from=build /root/rpmbuild/RPMS/ /packages/
RUN dnf install -y /packages/*/*.rpm && tays --version && tays --help && \
    /usr/bin/python3 -c 'import sys; from pathlib import Path; sys.path.insert(0,"/opt/type-as-you-speak/pydeps"); import numpy, onnxruntime, faster_whisper; from PySide6.QtWidgets import QApplication; app=QApplication([]); Path("/native-onnx-version").write_text(onnxruntime.__version__)'
FROM build AS verify
COPY --from=smoke /opt/type-as-you-speak/pydeps /installed-pydeps
COPY --from=smoke /native-onnx-version /native-onnx-version
RUN PYTHONPATH=/installed-pydeps python -c 'from pathlib import Path; import onnxruntime; assert onnxruntime.__version__ == Path("/native-onnx-version").read_text()'
RUN python scripts/prepare-test-model.py --output /tmp/recognition-model && \
    HF_HUB_OFFLINE=1 python -m pytest -m recognition tests/test_recognition.py -q -s \
      -o pythonpath=/installed-pydeps --recognition-installed-path /installed-pydeps --recognition-model /tmp/recognition-model && \
    rm -rf /tmp/recognition-model
RUN mkdir /out && SBOM="/out/fedora$(rpm -E %fedora)-dependencies.cdx.json" && \
    . /build-profile.env && if [ "$TAYS_NATIVE_ONNX" = 1 ]; then \
      python scripts/audit.py /installed-pydeps --system-package onnxruntime --format cyclonedx-json --output "$SBOM"; \
    else python scripts/audit.py /installed-pydeps --format cyclonedx-json --output "$SBOM"; fi
RUN cp /root/rpmbuild/RPMS/*/*.rpm /root/rpmbuild/SRPMS/*.rpm /out/
FROM scratch AS artifacts
COPY --from=verify /out/ /
