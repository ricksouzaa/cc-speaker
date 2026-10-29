---
name: phone
description: Send each reply as an mp3 file to the phone (Remote Control) instead of speaking it on the computer, or go back to the computer's speaker, for this session or, with `all`, for all of them. Without arguments it asks with a menu chosen by the arrow keys. Run only when the human names it (`/speak:phone`).
disable-model-invocation: true
argument-hint: "[on|off] [all]"
effort: low
---

# Speak phone

With arguments, run `speak phone $ARGUMENTS` through Bash and skip to the confirmation.

Without arguments, let the human choose with the arrow keys:

1. Run `speak status` through Bash to learn the output now in use (the "saída" line).
2. Ask with the AskUserQuestion tool, in plain Portuguese, two questions in one call:
   - "Para onde vai o áudio das respostas?" (header "Saída"): "Celular (mp3 pelo controle remoto)" and "Alto-falante do computador", with " (atual)" on the one in use.
   - "Vale para quais sessões?" (header "Alcance"): "Só esta sessão" and "Todas as sessões".
3. Run `speak phone on` for "Celular" or `speak phone off` for "Alto-falante", with ` all` at the end for "Todas as sessões".

Then say in one sentence, in plain Portuguese, what now holds (for example: "As respostas passam a chegar no celular como áudio mp3, nesta sessão."). Say "esta sessão" or "todas as sessões" according to the scope.

If the human cancels the question, change nothing and say so in one sentence. If the command fails, show its message and stop; do not try anything else.
