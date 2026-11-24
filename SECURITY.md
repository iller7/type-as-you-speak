# Security

Security fixes target the latest release. Run a supported Python profile (3.11–3.14 with PyPI dependencies; Fedora 45 also supports 3.15 with its native ONNX Runtime) and install distro security updates. Releases bundle native Python dependencies, so update the application as well as the OS.

Report vulnerabilities privately through [GitHub security advisories](https://github.com/iller7/type-as-you-speak/security/advisories/new). Include affected versions, a synthetic reproducer and impact. Never attach real dictation, audio, hotword lists or credentials. If private reporting is unavailable, email faizal.sahebdin@gmail.com.

See [privacy and network access](docs/privacy.md) for enforced telemetry opt-outs and their verification limits. Audio is processed locally. The first model download needs network access; dependencies and model downloads have their own upstream trust boundaries. Normal diagnostics record timing, model/device and character counts, not dictated text. Older versions logged transcript excerpts: review existing `~/.local/state/type-as-you-speak/live.log` before sharing it and remove it yourself if it contains private information.

Input injection can type into whichever application has focus. The ydotool daemon has input-device privileges; do not expose its socket to other users or grant world-write access to `/dev/uinput`. Prefer a narrowly scoped udev rule and the distro's daemon service. Membership of the `input` group can expose other input devices and should not be the default setup advice.

CI audits the actual bundled third-party versions and fails on any known advisory or scanner error. There is no severity-based bypass. Any exception requires an explicit advisory ID, rationale and expiry reviewed in a pull request; do not add blanket ignores or disable audit failures.

Current microphone capture flows through an ffmpeg pipe into in-memory buffers; the normal dictation path does not save a microphone recording. `live.log` contains operational diagnostics, not audio samples or dictated text in current code. Public, licensed audio fixtures committed for tests are separate from microphone capture. Memory/OS services and the app receiving typed text remain trust boundaries; this is not a secure-memory-erasure guarantee.
