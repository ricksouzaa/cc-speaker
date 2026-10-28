---
name: speak
description: Turn the spoken reply on or off, switch its mode (whole reply or only the summary line), show its status or cut the speech now and empty the queue of waiting speeches, for this session or for all of them. Run only when the human names it (`/speak`).
disable-model-invocation: true
argument-hint: "[on|off|mode full|mode summary] [all] | status | stop"
effort: low
---

# Speak

Run `speak $ARGUMENTS` through Bash. With no arguments, run `speak status`.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz desta sessão está desligada." or "A voz passa a ler só o resumo, em todas as sessões."). Say "esta sessão" or "todas as sessões" according to whether `all` was given.

If the command fails, show its message and stop; do not try anything else.
