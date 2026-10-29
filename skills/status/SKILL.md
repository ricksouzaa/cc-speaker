---
name: status
description: Show whether the voice is on, its mode, summary size, engine and voice. Run only when the human names it (`/speak:status`).
disable-model-invocation: true
effort: low
---

# Speak status

Run `speak status` through Bash.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz está ligada, no modo completo, com resumo médio.").

If the command fails, show its message and stop; do not try anything else.
