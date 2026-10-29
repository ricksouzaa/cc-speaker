---
name: voice
description: List the Portuguese voices, or choose one (dora, alex or santa) for every session. Run only when the human names it (`/speak:voice`).
disable-model-invocation: true
argument-hint: "[dora|alex|santa]"
effort: low
---

# Speak voice

Run `speak voice $ARGUMENTS` through Bash. With no arguments it lists the voices.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz agora é a do Alex."), or, when it only listed them, which one is in use.

If the command fails, show its message and stop; do not try anything else.
