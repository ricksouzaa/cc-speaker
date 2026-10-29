# Spoken reply

The `speak` Stop hook reads each reply aloud: by default the whole prose and tables, without code blocks, paths, links and file names (`speak mode full`); or only its last line `🔊 <resumo>` (`speak mode summary`).

- While the voice is on, every reply to the human ends with that `🔊` line, in plain Brazilian Portuguese: {size}. The full reading skips it.
- In it: no code, file names, paths, commands, command output, numbers of lines, links or acronyms; it is heard, not read.
- Prose that explains a code block says it in words, so the reading still makes sense without the block.
- Only dictation interrupts the reading: the voice does not speak while the microphone is recording (dictation, video call) and is cut if a recording starts while it speaks. A new speech, from any session, waits its turn in a queue; a new message does not cut it.
- When the voice is off, leave the line out, so no text is written for nothing: the new-message hook says so in a `speak:` note that holds for that message (voice off here or for all, or no engine), and so does a `speak off` you just ran. Without the note, or after a `speak on`, the line is back.
- Every slash command below can also be asked in words, typed or dictated, in any phrasing ("voz", "narração", "narrador", "leitura", "áudio" all mean the voice). Run the matching `speak` command through Bash and confirm in one sentence what now holds. It acts on this session only; when they say all sessions, everything or global ("todas as sessões", "tudo", "geral"), add `all` (on, off, mode, size). When the request names no choice ("muda a voz", "ajusta o tamanho do resumo"), ask with AskUserQuestion, one question per choice (the options of the matching setting, then scope: "Só esta sessão" or "Todas as sessões"), then run it.
  - Turn on or off ("ativa a narração", "desativa a narração", "silêncio", "volta a falar"): `speak on` or `speak off`.
  - Cut the speech playing now and empty the queue, keeping the voice on ("para de falar agora", "corta essa fala", "pula"): `speak stop`.
  - Only the summary or the whole reply ("lê só o resumo", "lê tudo"): `speak mode summary` or `speak mode full`.
  - A bigger or smaller summary ("resumo maior", "resumo curto"): `speak size large`, `speak size medium` or `speak size small`; from then on the new size holds for the `🔊` line, as `speak off` holds for the voice.
  - Change the voice ("troca para a voz do Alex", "quero uma voz feminina"): `speak voice <name>` (dora, alex or santa).
  - How the voice is set ("como está a narração?"): `speak status`, then say it in plain words.
  - Install the engine ("instala a voz"): `speak install`, with a timeout of 600000 ms.
- The slash command `/speak` exists for the human: alone it opens choice boxes below the input field, one question at a time; `/speak on`, `off`, `mode`, `size`, `voice`, `status`, `stop` and `install` also work typed (`all` at the end of on, off, mode and size for every session). The module answers it without you; do not run it for the human.
- Subagent reports carry no such line; only the session that talks to the human writes it.
