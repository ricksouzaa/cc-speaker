---
name: mode
description: Switch what is read aloud: the whole reply (full) or only the summary line (summary), for this session or, with `all`, for all of them. Run only when the human names it (`/speak:mode`).
disable-model-invocation: true
argument-hint: "full|summary [all]"
effort: low
---

# Speak mode

Run `speak mode $ARGUMENTS` through Bash.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz passa a ler só o resumo, nesta sessão."). Say "esta sessão" or "todas as sessões" according to whether `all` was given.

If the command fails, show its message and stop; do not try anything else.
