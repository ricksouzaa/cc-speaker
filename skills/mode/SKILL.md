---
name: mode
description: Switch what is read aloud: the whole reply (full) or only the summary line (summary), and with the summary its size, for this session or, with `all`, for all of them. Without arguments it asks with a menu chosen by the arrow keys. Run only when the human names it (`/speak:mode`).
disable-model-invocation: true
argument-hint: "[full|summary] [all]"
effort: low
---

# Speak mode

With arguments, run `speak mode $ARGUMENTS` through Bash and skip to the confirmation.

Without arguments, let the human choose with the arrow keys:

1. Run `speak status` through Bash to learn the mode and the summary size now in use.
2. Ask with the AskUserQuestion tool, in plain Portuguese, two questions in one call:
   - "O que a voz lê?" (header "Leitura"): "Resposta inteira" (the prose and tables, without code, paths and links) and "Só o resumo" (only the 🔊 line at the end).
   - "Vale para quais sessões?" (header "Alcance"): "Só esta sessão" and "Todas as sessões".
   Add " (atual)" to the label of the mode in use.
3. When the answer is "Só o resumo", ask one more question with AskUserQuestion: "Qual o tamanho do resumo?" (header "Tamanho"): "Pequeno" (uma frase curta), "Médio" (duas a três frases) and "Grande" (um parágrafo de quatro a seis frases), with " (atual)" on the size in use.
4. Run `speak mode full` or `speak mode summary`, then, for the summary, `speak size small|medium|large`; add ` all` at the end of each when the answer was "Todas as sessões".

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz passa a ler só o resumo, em tamanho médio, nesta sessão."). Say "esta sessão" or "todas as sessões" according to the scope.

If the human cancels the question, change nothing and say so in one sentence. If a command fails, show its message and stop; do not try anything else.
