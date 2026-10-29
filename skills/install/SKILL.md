---
name: install
description: Install the voice engine (Kokoro, about 350 MB, no sudo, needs uv). Run only when the human names it (`/speak:install`).
disable-model-invocation: true
effort: low
---

# Speak install

Run `speak install` through Bash with a timeout of 600000 milliseconds; the download takes minutes. If it ends by the timeout, run it again: it resumes where files already exist.

Then say in one sentence, in plain Portuguese, what now holds: that the engine is installed and the voice is ready, or what is missing.

If the command fails, show its message and stop; do not try anything else.
