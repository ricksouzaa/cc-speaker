---
name: off
description: Turn the spoken reply off, for this session or, with `all`, for all of them. Run only when the human names it (`/speak:off`).
disable-model-invocation: true
argument-hint: "[all]"
effort: low
---

# Speak off

Run `speak off $ARGUMENTS` through Bash.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz desta sessão está desligada."). Say "esta sessão" or "todas as sessões" according to whether `all` was given.

If the command fails, show its message and stop; do not try anything else.
