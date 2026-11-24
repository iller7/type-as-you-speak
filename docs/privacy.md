# Privacy and network access

These controls apply to the current source checkout. Existing v0.5.1 release binaries predate them; no updated release has been published yet.

## Strict offline dictation

**Strict offline dictation is enabled by default.** In the GUI, use General → **Strict offline dictation**, save, then stop and restart dictation. The status panel shows the active session's protection separately from your saved preference. An older session with no protection status is shown as unknown; restart it.

Download the selected model with the GUI's **Download** button, `tays download`, or `tays setup --download-model` before dictating. `tays download tiny.en` downloads a particular model; it does not change your selected model. Setup/download processes can contact upstream hosting services, exposing ordinary connection metadata such as your IP address. They do not send your dictation. Model download access remains available when strict mode is selected.

Strict dictation uses cached/local model files only, including GPU and CPU fallbacks. Models are initialized before microphone capture. If a model is missing, or Linux network protection cannot be installed, dictation stops with an error. It never silently downgrades to an online session. Invalid `strict_offline` values retain strict mode; `DICTATE_STRICT_OFFLINE` is an explicit per-process override. The GUI shows that override and disables the checkbox while it is present; saving other settings does not overwrite the stored privacy preference.

Linux applies a process-local seccomp filter before starting session helpers or importing inference code. Only Unix-domain sockets are allowed, preserving local audio/input/desktop IPC. Other socket families and io_uring are blocked; the restriction covers existing threads and inherited child processes. Inherited non-Unix sockets and io_uring descriptors cause startup to fail. This needs `libseccomp2` on Debian/Ubuntu or `libseccomp` on Fedora/Arch; native DEB/RPM packages declare it. No root access or system firewall changes are needed.

The restriction covers the dictation process and its children. Existing desktop services, privileged drivers, the OS and applications receiving typed text remain separate trust boundaries. Allowed Unix IPC could be used by deliberately hostile code to ask another service to make connections; this is not a malware sandbox. macOS/Windows desktop ports and their OS network enforcement are not implemented. Disabling strict mode permits automatic model retrieval again; it does not enable a cloud transcription service or telemetry. No cloud dictation service exists today. Future cloud features must be rejected in strict mode and require their own explicit opt-in otherwise.

## Telemetry controls

The app enforces these before inference imports, including in setup/model-download children and the public test-model preparation tool:

| Dependency | Control and reviewed scope |
| --- | --- |
| ONNX Runtime (locked 1.32; Fedora-native 1.26) | `ORT_DISABLE_TELEMETRY=1` before import, plus the API event opt-out before model/VAD construction. The early setting prevents 1DS initialization; the API additionally covers legacy Windows events. |
| Hugging Face Hub 1.16.1 | `HF_HUB_DISABLE_TELEMETRY=1` and `DO_NOT_TRACK=1`; these suppress its telemetry helper without disabling explicit model downloads. |
| Native hf-xet 1.8.0 downloader | The Hub opt-out also applies; `HF_XET_TELEMETRY_ENABLED=0` is set explicitly. |
| HTTPX/httpcore/anyio and HTTP/TLS support | Used for explicit Hub transfers, not a separate analytics integration. Download requests still disclose connection metadata; disabling telemetry does not make downloads anonymous. |
| faster-whisper, CTranslate2, tokenizers, NumPy and PyAV | Reviewed the used loading/inference paths and network delegation. No additional telemetry switch was identified. Strict-mode OS restrictions and the network regression check provide independent protection/evidence. |
| PySide6 Essentials / Qt | The app does not integrate Qt Insight, a crash uploader or an analytics SDK. GUI model downloads have the same telemetry policy. User-requested documentation links open in your browser, which has its own privacy settings. |

These opt-outs override inherited telemetry-enabling values and remain enforced when strict mode is off. CLI help/version do not load inference libraries. Importing the app into a process that already initialized dependencies cannot undo earlier activity; use the normal `tays` entry point in a fresh process. See [ONNX privacy documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md), [Hub controls](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hfhubdisabletelemetry) and [Xet telemetry](https://huggingface.co/docs/hub/main/en/xet/telemetry).

## Verification and diagnostics

Linux CI uses `strace` during real recognition/VAD with pinned public assets, including a deliberate Hub telemetry call and a 15-second idle window. A positive control must observe sockets in a thread and child process first. Any networking syscall, tracer warning, missing control or probe failure fails the check; trace arguments are raw and temporary files are removed. This is a regression check for the exercised configuration, not proof about every future execution, model, device or platform. Broader native-build/desktop/GPU and macOS/Windows verification remains tracked in [issue #45](https://github.com/iller7/type-as-you-speak/issues/45).

Normal diagnostics contain model/device, timing and character counts rather than dictated text. Review existing logs before sharing them, especially logs from older releases. Audio capture and typing cross local trust boundaries: dictation goes to whichever application has focus, and input helpers must be restricted to your user. See [security guidance](https://github.com/iller7/type-as-you-speak/blob/master/SECURITY.md). The optional gTTS development extra is an online text-to-speech service, excluded from the ordinary runtime/GUI installation and local-inference tests; do not use it for private content.
