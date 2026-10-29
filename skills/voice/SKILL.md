---
name: voice
description: Choose the Portuguese voice (dora, alex or santa) for every session. Without arguments it asks with a menu chosen by the arrow keys. Run only when the human names it (`/speak:voice`).
disable-model-invocation: true
argument-hint: "[dora|alex|santa]"
effort: low
---

# Speak voice

With an argument, run `speak voice $ARGUMENTS` through Bash and skip to the confirmation.

Without arguments, let the human choose with the arrow keys:

1. Run `speak voice` through Bash: it lists the voices, with `*` on the one in use.
2. Ask with the AskUserQuestion tool, in plain Portuguese, one question: "Qual voz você quer?" (header "Voz"), one option per voice listed, labelled by its short name with a capital letter and its kind (for example "Dora (feminina)"), with " (atual)" on the one in use.
3. Run `speak voice <short name>` with the one chosen.

Then say in one sentence, in plain Portuguese, what now holds (for example: "A voz agora é a do Alex, em todas as sessões."). The voice holds for every session.

If the human cancels the question, change nothing and say so in one sentence. If the command fails, show its message and stop; do not try anything else.
