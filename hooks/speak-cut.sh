#!/usr/bin/env bash
# UserPromptSubmit hook: a new message from the human cuts nothing; a speech playing goes on, and a new speech
# waits its turn in the queue (only dictation cuts the one playing). When this session will not speak
# (`speak silent`, or `speak` not installed), it prints a note that Claude reads with the message: leave out the
# 🔊 line. Exits 0 in every case.
cat >/dev/null
v="$(command -v speak || echo "$HOME/.local/bin/speak")"
if [ ! -x "$v" ] || "$v" silent >/dev/null 2>&1; then
  echo "speak: a voz está desligada nesta sessão; não termine esta resposta com a linha 🔊."
fi
exit 0
