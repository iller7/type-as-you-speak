---
title: Real-time dictation with privacy built in
body_class: home
---

<div class="hero">
  <p class="eyebrow">Real-time dictation · privacy first</p>
  <h1>Speak freely.<br>Keep control.</h1>
  <p class="lead">Turn your voice into text in the app you are using. Dictation that fits your desktop, with strict offline processing enabled by default.</p>
  <div class="actions"><a class="button" href="{{ '/install.html' | relative_url }}">Get started →</a><a class="button secondary" href="{{ '/privacy.html' | relative_url }}">Explore privacy controls</a></div>
  <div class="chips"><span>Linux desktop today</span><span>macOS &amp; Windows planned</span><span>Optional cloud planned</span></div>
</div>

<div class="notice">Privacy hardening is available in the current source checkout. Existing v0.5.1 binaries predate these protections; an updated release has not been published. <a href="{{ '/install.html' | relative_url }}">Check installation guidance.</a></div>

## Less typing. More choice.

<p class="section-intro">Use focused text fields across your desktop, subject to application compatibility and input permissions. No cloud dictation account is required for the implemented local engine.</p>

<div class="cards">
  <article class="card"><span class="number">01 / DICTATE</span><h3>Stay in your flow</h3><p>Use a shortcut, speak, and type into the focused app. KDE/GNOME and Wayland/X11 are the integration targets.</p><a href="{{ '/usage.html' | relative_url }}">Using dictation →</a></article>
  <article class="card"><span class="number">02 / CONTROL</span><h3>Private by default</h3><p>Download models explicitly, then keep dictation offline. Telemetry opt-outs remain enforced in every mode. Live microphone audio is processed in memory, not saved as a recording by default.</p><a href="{{ '/privacy.html' | relative_url }}">Read the privacy boundaries →</a></article>
  <article class="card"><span class="number">03 / CONFIGURE</span><h3>Make it yours</h3><p>Choose your model, CPU/GPU settings, language and hotwords. Use the settings window or a readable configuration file.</p><a href="{{ '/configuration.html' | relative_url }}">Configure your setup →</a></article>
</div>

## Know what is ready

<div class="platforms">
  <div><span class="status">Current desktop target</span><h3>Linux</h3><p>Debian, Ubuntu and Fedora package checks; Arch build validation. Real microphone, input and GPU compatibility still needs desktop QA.</p></div>
  <div><span class="status planned">Planned desktop ports</span><h3>macOS &amp; Windows</h3><p>Shared-code tests run on both systems. Desktop dictation, installers and OS privacy enforcement are not available yet.</p></div>
  <div><span class="status planned">Planned option</span><h3>Cloud dictation</h3><p>No hosted service exists today. Future cloud features must respect strict offline mode and require separate, explicit opt-in.</p></div>
</div>

## Find your next step

[Installation](install.md) · [Troubleshooting](troubleshooting.md) · [Testing matrix](testing.md) · [Architecture](architecture.md) · [Issues and roadmap](https://github.com/iller7/type-as-you-speak/issues)

First-party code is [AGPL-3.0-only](licensing.md), with a separate commercial-licensing enquiry path. Dependencies, model weights and input tools keep their own terms. The focused app receiving your text has its own privacy behaviour.
