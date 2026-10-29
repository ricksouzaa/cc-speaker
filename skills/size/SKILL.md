---
name: size
description: Set how long the spoken summary is (small, medium or large), for this session or, with `all`, for all of them. Run only when the human names it (`/speak:size`).
disable-model-invocation: true
argument-hint: "small|medium|large [all]"
effort: low
---

# Speak size

Run `speak size $ARGUMENTS` through Bash.

Then say in one sentence, in plain Portuguese, what now holds (for example: "O resumo falado passa a ser grande, nesta sessão."). Say "esta sessão" or "todas as sessões" according to whether `all` was given.

If the command fails, show its message and stop; do not try anything else.
