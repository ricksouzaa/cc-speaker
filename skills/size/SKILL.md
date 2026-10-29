---
name: size
description: Set how long the spoken summary is (small, medium or large), for this session or, with `all`, for all of them. Without arguments it asks with a menu chosen by the arrow keys. Run only when the human names it (`/speak:size`).
disable-model-invocation: true
argument-hint: "[small|medium|large] [all]"
effort: low
---

# Speak size

With arguments, run `speak size $ARGUMENTS` through Bash and skip to the confirmation.

Without arguments, let the human choose with the arrow keys:

1. Run `speak status` through Bash to learn the summary size now in use.
2. Ask with the AskUserQuestion tool, in plain Portuguese, two questions in one call:
   - "Qual o tamanho do resumo falado?" (header "Tamanho"): "Pequeno" (uma frase curta), "Médio" (duas a três frases) and "Grande" (um parágrafo de quatro a seis frases), with " (atual)" on the size in use.
   - "Vale para quais sessões?" (header "Alcance"): "Só esta sessão" and "Todas as sessões".
3. Run `speak size small`, `speak size medium` or `speak size large`, with ` all` at the end for "Todas as sessões".

Then say in one sentence, in plain Portuguese, what now holds (for example: "O resumo falado passa a ser grande, nesta sessão."). Say "esta sessão" or "todas as sessões" according to the scope.

If the human cancels the question, change nothing and say so in one sentence. If the command fails, show its message and stop; do not try anything else.
