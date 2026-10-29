---
name: on
description: Turn the spoken reply on, for this session or, with `all`, for all of them. Run only when the human names it (`/speak:on`).
disable-model-invocation: true
argument-hint: "[all]"
effort: low
---

# Speak on

Run `speak on $ARGUMENTS` through Bash.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz desta sessão está ligada."). Say "esta sessão" or "todas as sessões" according to whether `all` was given.

If the command fails, show its message and stop; do not try anything else.
