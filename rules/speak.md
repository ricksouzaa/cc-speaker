# Spoken reply (every project)

The `speak` Stop hook reads each reply aloud: by default the whole prose and tables, without code blocks, paths, links and file names (`speak mode full`); or only its last line `🔊 <resumo>` (`speak mode summary`).

- While the voice is on, every reply to the human ends with that `🔊` line: one or two short sentences in plain Brazilian Portuguese, what was done or what the human must decide. The full reading skips it.
- In it: no code, file names, paths, commands, command output, numbers of lines, links or acronyms; it is heard, not read.
- Prose that explains a code block says it in words, so the reading still makes sense without the block.
- Only dictation interrupts the reading: the voice does not speak while the microphone is recording (dictation, video call) and is cut if a recording starts while it speaks. A new speech, from any session, waits its turn in a queue; a new message does not cut it.
- When the voice is off, leave the line out, so no text is written for nothing: the new-message hook says so in a `speak:` note that holds for that message (voice off here or for all, or no engine), and so does a `speak off` you just ran. Without the note, or after a `speak on`, the line is back.
- When the human asks in words, spoken or typed, to stop, silence, turn off or turn on the voice or the audio, run `speak off` or `speak on` through Bash: it acts on this session only. When they say all sessions, everything or global ("todas as sessões", "tudo", "geral"), run `speak off all` or `speak on all`. Confirm in one sentence what now holds.
- When they ask in words to read only the summary or the whole reply, run `speak mode summary` or `speak mode full` (with `all` when they say all sessions, everything or global). Confirm in one sentence.
- The slash command `/speak` exists for the human (on, off, mode, status, stop; `all` at the end of on, off and mode for every session).
- Subagent reports carry no such line; only the session that talks to the human writes it.
