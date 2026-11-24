---
title: "Project direction and options"
---

# Project direction and options

These recommendations support the prioritised tasks in [GitHub Issues](https://github.com/iller7/type-as-you-speak/issues). We reviewed the sources on 24 November 2026; hosting limits, reference projects and dependency licences can change. Architecture and licence decisions remain open until we choose them explicitly.

## What we can learn from the reference apps

| Reference                                                                                                           | Useful pattern                                                                                    | Application here                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| [VoiceStudio installation](https://github.com/debpalash/VoiceStudio/blob/main/docs/install/linux.md)                | Separate platform guides, verified downloads, packaged-launch checks and explicit hardware limits | Split the README, make install choices clear, verify installed artifacts and track real hardware QA                                   |
| [VoiceStudio structure](https://github.com/debpalash/VoiceStudio/blob/main/docs/STRUCTURE.md)                       | Named responsibility boundaries and a documented home for each type of content                    | Retain our src layout, separate user guides from contributor material, and split large modules when their responsibilities justify it |
| [VoiceStudio model inventory](https://github.com/debpalash/VoiceStudio/blob/main/docs/licensing/model-inventory.md) | Track model terms separately from the application licence                                         | Audit weights, Python/native dependencies, Qt and input tools under [T007](https://github.com/iller7/type-as-you-speak/issues/10)     |
| [OpenMausBot platform guide](https://github.com/milind-soni/OpenMausBot/blob/main/docs/linux-desktop.md)            | Platform-specific assets and candid support boundaries                                            | Distinguish recipe, build-checked, runtime-tested and published support                                                               |
| [OpenMausBot releasing](https://github.com/milind-soni/OpenMausBot/blob/main/docs/releasing.md)                     | Release a pinned commit, test the packaged result and document signing/update ownership           | Rehearse publication, test upgrades/rollback, and plan macOS/Windows signing separately                                               |

VoiceStudio currently uses Electron with a Python backend; its older Tauri application is archived. OpenMausBot also uses Electron. This shows viable choices for those products, not evidence that our smaller dictation UI needs the same stack. We reviewed their patterns and wrote our own project guidance; their code and agent skills have not been copied.

VoiceStudio's [FastAPI skill](https://github.com/debpalash/VoiceStudio/blob/main/.agents/skills/fastapi-python/SKILL.md) addresses an API server, asynchronous routes and databases. Our [Python desktop guide](https://github.com/iller7/type-as-you-speak/blob/master/.agents/guides/python-desktop.md) addresses Qt, audio, lifecycle, subprocesses and local models. A plain guide linked from AGENTS.md works with local agents that do not discover SKILL.md files automatically.

## Language and desktop shell

The current harness combines a Python speech backend, Qt settings and Linux integration. The maintainer's preference for less Python/shell belongs in the decision, alongside measured runtime and maintenance costs.

| Option                                                | Benefit to evaluate                                                                   | Cost to evaluate                                                                                                      |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Keep Python/PySide6                                   | Preserve the current recognition integration and UI while completing reliability work | Python/native dependency packaging and large mixed-responsibility modules                                             |
| Rust orchestration with an existing inference backend | Stronger lifecycle/type boundaries and less Python/shell in the harness               | Inference bindings, GPU support, UI choice and platform adapters still need implementation and tests                  |
| Rust core with a Python worker                        | Move the harness incrementally while retaining recognition behaviour                  | Two runtimes and an IPC/process lifecycle contract                                                                    |
| Electron UI with an existing backend                  | Web UI tooling and established installer/update tooling                               | Adds Chromium/Node, IPC boundaries and a runtime/security update obligation; it does not remove the inference backend |
| Tauri or another native UI                            | Evaluate a smaller shell and Rust integration                                         | System webview/native prerequisites and OS-specific differences remain                                                |

Recommendation: establish known-audio, lifecycle and package baselines first, then compare a small Rust harness prototype against them. Keep the existing UI while measuring unless a UI requirement justifies replacing it. Compare startup, resident memory, package size, speech accuracy, latency, build effort, local-agent maintainability and input/permission behaviour. Keep [T018](https://github.com/iller7/type-as-you-speak/issues/21)/[T019](https://github.com/iller7/type-as-you-speak/issues/22) as decisions, not a commitment to Python indefinitely.

Electron is an option if we choose web UI development; adopting it only to simplify Python packaging would add another runtime. Its [security guidance](https://www.electronjs.org/docs/latest/tutorial/security) requires attention to Chromium/Node updates, sandboxing and IPC. Tauri's [architecture](https://v2.tauri.app/concept/architecture/) uses system webviews, with a different platform-dependency trade-off.

## Folder structure

Keep the current top-level responsibilities and grow them only when needed:

| Location                 | Responsibility                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `src/type_as_you_speak/` | Application code; keep CLI entry points thin as the app evolves                                    |
| `tests/`                 | Fast behaviour tests; add explicit audio, integration and desktop fixtures/suites when implemented |
| `docs/`                  | Focused user guides and researched project decisions                                               |
| `packaging/`             | Distro recipes, verified native helpers and build containers                                       |
| `scripts/`               | Small maintenance/release utilities that do not belong in the runtime package                      |
| `.github/`               | CI, release automation, contribution templates and ownership                                       |
| `.agents/guides/`        | Concise local-agent development guidance, independent of a cloud provider                          |
| `TODO.md`                | Concise roadmap linking to GitHub Issues, which owns status and evidence                           |

The [Python Packaging Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) documents the src layout we already use. A large apps/packages monorepo would add ceremony here. Under [T017](https://github.com/iller7/type-as-you-speak/issues/20), first consider extracting audio capture, inference/model management, streaming session logic, input injection and GUI responsibilities, with behaviour-preserving tests before moving public entry points.

## Known-audio testing

Add a reviewed fixture manifest with audio path/hash, licence/provenance, language, expected transcript or accepted variants, model/revision, configuration and thresholds. Cover silence, noise, accents, pauses, numbers/names, hotwords, repetition, cancellation and long utterances. Record word/character error rate, first-word latency, finalisation latency and duplicate/missing words.

Use a small CPU suite in CI and local generation or redistributable recordings. Keep large model/dataset downloads and hardware-specific matrices separate. A local TTS generator avoids requiring a cloud service to create fixtures. GPU floating-point results may differ, so define normalisation and tolerances rather than assuming byte-identical text. Run through dry input boundaries to avoid typing into a contributor's desktop. [T001](https://github.com/iller7/type-as-you-speak/issues/4)–[T005](https://github.com/iller7/type-as-you-speak/issues/8) remain open; the current regression suite is a foundation, not a full speech/desktop certification.

## Free website and concise documentation

Recommendation for [T013](https://github.com/iller7/type-as-you-speak/issues/19): GitHub Pages with Markdown guides and a small static landing page. The selected default address is `https://iller7.github.io/type-as-you-speak/`; it is not a claim that a site has been published. [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) supports public repositories on GitHub Free and supplies the github.io address, so no domain purchase is required.

Start with product purpose, a real screenshot/demo, supported downloads, a quick start, privacy and links to guides. Keep README as the short repository entry point. Prefer the simplest static generator or built-in Pages theme that meets those needs; a documentation site does not require adopting Electron, React or a paid host. Add publication/link checks and ensure installation examples match actual release assets.

## GitHub Free and build simplification

This repository is public. Standard GitHub-hosted runner compute for public repositories is free; larger runners are billed and should not become a requirement. GitHub's current [billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) lists a 500 MB artifact-storage allowance pooled at account/plan level with GitHub Packages, and a separate 10 GB cache allowance per repository. The general included compute allowance is currently expressed as credit rather than a fixed minute count; recheck the account's billing page before changing visibility or enabling paid features.

The current [limits](https://docs.github.com/en/actions/reference/limits) include 20 concurrent standard jobs, at most five concurrent macOS jobs and six hours per hosted job. There is no free hosted GPU assumption. A local GPU runner is an option to design and secure separately, not a cloud-provider prerequisite. These are documentation limits, not an audit of this account's bill.

Our package matrix produces large binaries, so compute being free does not remove the need for storage discipline. [T009](https://github.com/iller7/type-as-you-speak/issues/12) covers fast versus slow checks, [T030](https://github.com/iller7/type-as-you-speak/issues/14) covers retained artifacts/budget controls, and [T031](https://github.com/iller7/type-as-you-speak/issues/29) evaluates AppImage or a managed-runtime bundle as a way to simplify installation. Feature branches now validate through PRs instead of duplicating branch-push runs. Large package artifacts are uploaded only for tags/manual runs with one-day retention; native build/install/audit validation still runs on PRs. Existing artifacts have not been deleted. Further retention/account review remains open.

Simplify in this order: keep one local command surface, share backend/setup steps, run quick feedback first, select slow checks from relevant changes, and retain full native package validation for release candidates. Evaluate build caches with trust boundaries and lockfile hashes. Avoid replacing the current build with a new language or UI stack solely to hide packaging complexity.

## Licence decision

VoiceStudio uses [AGPL-3.0](https://github.com/debpalash/VoiceStudio/blob/main/LICENSE); OpenMausBot uses [Apache-2.0](https://github.com/milind-soni/OpenMausBot/blob/main/LICENSE). Their badges express different policies. Our first-party source remains MIT while [T007](https://github.com/iller7/type-as-you-speak/issues/10) is unresolved.

| Goal                                                                                | Licence direction to consider                                   |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Broad reuse, including closed-source derivatives, with notices retained             | [MIT](https://choosealicense.com/licenses/mit/)                 |
| Require corresponding source when covered modified/combined software is distributed | GPL-3.0, subject to the actual combination and applicable terms |
| Also cover modified software offered to users over a network                        | [AGPL-3.0](https://choosealicense.com/licenses/agpl-3.0/)       |

These licences allow commercial use; AGPL is not a non-commercial licence. Its network condition is relevant to modified hosted services, not a blanket requirement to publish private local edits. MIT is reasonable if permissive reuse is our goal; AGPL is worth choosing if source reciprocity, including hosted forks, is the goal. A desktop-only harness does not gain a runtime feature by changing its licence.

Before a switch, review contributor/copyright rights, future versus already-released code, dependencies and model terms. [Open Source Guides](https://opensource.guide/legal/#what-if-i-want-to-change-the-license-of-a-project) explains why relicensing needs care. Bundled ydotool is AGPL and Qt has [separate licence terms](https://doc.qt.io/qtforpython-6/licenses.html); the [GNU aggregation guidance](https://www.gnu.org/licenses/gpl-faq.html#MereAggregation) shows why the way components interact matters. Inventory and review the actual artifacts rather than assuming an MIT badge settles redistribution obligations. Do not copy reference-project code or switch the project licence before that decision.

## Badges, formatting and local guidance

The README now shows CI, release, current licence, downloads, Python range and Linux status. The metrics refer to real repository/release data. A page-view counter is deferred because a third-party tracking pixel adds little evidence of product health; useful download and test signals come first.

Use one Markdown paragraph or list item per source line and visual wrapping in the editor. `.prettierrc.json` sets `proseWrap: never`, `.editorconfig` removes the Markdown width target, and shared VS Code settings turn on display-only wrapping. EditorConfig support varies, so agent guidance and formatter configuration both state the rule. Python keeps the [PEP 8 four-space convention](https://peps.python.org/pep-0008/#indentation); other files default to two spaces, with Makefile tabs.

## K8s patterns to keep

Reuse pinned tools, one command surface, ownership, dependency maintenance, PR checks, explicit verification/rollback and documented release responsibilities. We already use these foundations and now keep a durable backlog and local-agent guide. Keep the app's current Makefile rather than adding a second task runner. Cluster/account configuration, Terraform/GitOps workflows and environment-promotion machinery do not serve this desktop app's present requirements.
