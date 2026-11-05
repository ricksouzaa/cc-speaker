# Resumo em mensagem própria (0.19.0): plano de construção

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma escolha nova, `split` (desligada por padrão), faz a linha 🔊 sair numa mensagem própria ao fim da resposta, pedida pelo gancho de parada numa volta a mais, para o play do app do celular tocar só o resumo.

**Architecture:** `speak split on|off [all]` guarda-se como `mode` (campo `split` da sessão, arquivo geral `conf/split`). `speak say -` passa a devolver na saída o JSON do gancho de parada quando quer a volta a mais (`{"decision": "block", "reason": ...}`), guardando o corpo da resposta em `state/pending/<sessão>`; na parada seguinte, só a linha, ele junta corpo e linha, guarda como última resposta e fala. O gancho `hooks/speak-stop.py` só repassa a saída do `speak` e o campo `stop_hook_active`. O gancho de mensagem nova avisa o modelo, a cada mensagem com `split` ligado, para não fechar a resposta com a linha. Painel e regra ganham a escolha.

**Tech Stack:** Python 3, TypeScript do módulo, `unittest`, `claude plugin test`.

**Spec:** `docs/superpowers/specs/2026-11-05-resumo-sem-narracao-design.md` (parte 2). Depende da 0.18.0 (`power`, `silent_reason` com `quiet`).

## Global Constraints

- Texto ao usuário em português do Brasil; comentários do código em inglês.
- Testes: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests`, `claude plugin test .`, `claude plugin validate .`.
- Rótulos fixados: comando `speak split on|off [all]`; painel, linha "Resumo em mensagem própria" com "Não" / "Sim", só com a leitura em "só o resumo"; rodapé "O resumo passa a vir numa mensagem própria nesta sessão." / "O resumo volta a fechar a própria resposta nesta sessão." (ou "em todas as sessões"); `status` com `  resumo em mensagem própria: sim|não`; `status --json` com `split` (`on`/`off`) e `scope.split`.
- A separação só acontece quando a linha é pedida (`silent_reason()` é `None`: estados `on` e `quiet`) e no modo resumo. Nunca mais de uma volta a mais por resposta; a marca é o corpo pendente, não `stop_hook_active` (que, verdadeiro, apenas impede o bloqueio).
- Motivo do bloqueio: `speak: escreva agora, como mensagem própria, só a linha 🔊 com o resumo da resposta que acabou de dar (<tamanho>); nada mais.` com `<tamanho>` em `{'small': 'uma frase curta', 'medium': 'duas ou três frases', 'large': 'um parágrafo de quatro a seis frases'}`.
- Nota do gancho de mensagem nova com `split` ligado: `speak: o resumo vai numa mensagem própria: não termine esta resposta com a linha 🔊; o gancho de parada vai pedir a linha logo depois, e aí responda só com ela.` Com corpo pendente na sessão, o gancho não imprime nota nenhuma.
- Versão 0.19.0 pelo fluxo de `.claude/rules/git-workflow.md`.

## Review Focus

- Resposta que já vem com corpo e linha com `split` ligado (o modelo não separou): fala a linha, não bloqueia, apaga o pendente (teste na tarefa 2).
- Pendente de uma resposta anterior quando chega uma resposta nova com corpo e sem linha (a volta a mais nunca veio): bloqueia de novo com o corpo novo (teste na tarefa 2).
- `split` ligado com a voz `off` ou na leitura inteira: nada de bloqueio nem de nota (testes nas tarefas 2 e 3).
- `stop_hook_active` verdadeiro na primeira parada (outro gancho bloqueou antes): guarda e fala como hoje, sem bloquear (teste na tarefa 2).
- `last_assistant_message` trazendo corpo e linha na segunda parada (se o Claude Code mandar a rodada inteira): a junção não duplica o corpo, porque a resposta não é "só a linha" e o item "corpo e linha juntos" vale (teste na tarefa 2); conferido de verdade na tarefa 5.

---

### Task 1: A escolha `split` no `bin/speak`

**Files:**
- Modify: `bin/speak` (constantes perto de `MIC_FILE`, linha 101; `read_session` 314; `set_session`/`clear_all_sessions`; `status` 1898; `status_json`; `main`, ramo `mode` 2092)
- Test: `tests/test_speak.py` (classe `Session`)

**Interfaces:**
- Produces: `SPLIT_FILE = os.path.join(CONF, 'split')`; `SPLITS = ('on', 'off')`; `split(session=None) -> str` (`CLAUDE_SPEAK_SPLIT`, campo `split` da sessão, arquivo geral, senão `'off'`); comando `speak split on|off [all]` com a mesma forma do ramo `mode` (uso: `voz: use "speak split on" ou "speak split off" (com "all" no fim, vale para todas as sessões)`); `status()` imprime `  resumo em mensagem própria: sim|não` com a marca `· só nesta sessão`; `status_json()` ganha `'split': split(session)` e `scope['split']`.

- [ ] **Step 1: Testes** na classe `Session`:

```python
def test_split_is_off_by_default_and_follows_the_scopes(self):
    self.assertIn('resumo em mensagem própria: não', self.speak('status', session=self.me).stdout)
    self.speak('split', 'on', session=self.me)
    mine = self.speak('status', session=self.me).stdout
    self.assertIn('resumo em mensagem própria: sim · só nesta sessão', mine)
    self.assertIn('resumo em mensagem própria: não', self.speak('status', session=self.other).stdout)
    data = json.loads(self.speak('status', '--json', session=self.me).stdout)
    self.assertEqual((data['split'], data['scope']['split']), ('on', 'session'))
    self.speak('split', 'on', 'all', session=self.me)
    data = json.loads(self.speak('status', '--json', session=self.me).stdout)
    self.assertEqual((data['split'], data['scope']['split']), ('on', 'all'))
    self.assertEqual(self.speak('split', 'sim', session=self.me).returncode, 2)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest tests.test_speak.Session -k split -v 2>&1 | tail -5`
Expected: FAIL (linha ausente no `status`).

- [ ] **Step 3: Implementar** no `bin/speak`, copiando a forma de `mic`/`mode` (função de leitura, ramo em `main`, `read_session` aceitando `split` em `SPLITS`, `status` e `status_json`); o docstring de ajuda ganha `speak split on|off [all]`.

- [ ] **Step 4: Rodar a bateria**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add bin/speak tests/test_speak.py
git commit -m "feat: escolha split, o resumo numa mensagem própria"
```

### Task 2: O corpo pendente e a volta a mais em `speak say -`

**Files:**
- Modify: `bin/speak` (`LAST`/`prune_sessions` ~391; `save_last`/`read_last` 402; o ramo `say` de `main` ~2200)
- Test: `tests/test_speak.py` (classe `Again`, 2587: usa `run_speak` em processo, com `_play` falso)

**Interfaces:**
- Consumes: `split(session)`, `silent_reason()`, `mode(session)`, `summary_size(session)`, `spoken_line(message)`.
- Produces: `PENDING = os.path.join(STATE, 'pending')`; `save_pending(session, body)`, `read_pending(session) -> str | None`, `drop_pending(session)`; `prune_sessions()` poda `PENDING` como `LAST`; `only_line(message) -> bool` (toda linha não vazia começa com `MARK` depois de tirar `>*_ `); `SPLIT_REASON` e `SIZE_SPOKEN` (os textos de Global Constraints); `block_output(reason) -> str` (uma linha JSON `{"decision": "block", "reason": reason}`); `speak say - [--active]`: `--active` é o `stop_hook_active` do gancho; imprime a linha JSON na saída quando bloqueia, senão nada; código 0 nos dois casos.

- [ ] **Step 1: Testes** na classe `Again` (`self.run_speak` devolve `(code, out, err)`; `speak.set_session(self.me, split='on')` liga a escolha; `self.spoken()` lista o que tocou):

```python
def test_split_asks_for_the_line_once_and_joins_it(self):
    speak.set_session(self.me, split='on')
    code, out, _ = self.run_speak('say', '-', stdin='Fiz tudo.')
    self.assertEqual(code, 0)
    self.assertEqual(json.loads(out)['decision'], 'block')
    self.assertIn('duas ou três frases', json.loads(out)['reason'])
    self.assertEqual(self.spoken(), [])
    self.assertEqual(speak.read_pending(self.me), 'Fiz tudo.')
    code, out, _ = self.run_speak('say', '-', stdin='🔊 Fiz tudo, pode testar.')
    self.assertEqual((code, out), (0, ''))
    self.assertEqual(self.spoken(), ['Fiz tudo, pode testar.'])
    self.assertEqual(speak.read_last(self.me), ('Fiz tudo.\n\n🔊 Fiz tudo, pode testar.', 'summary'))
    self.assertIsNone(speak.read_pending(self.me))

def test_split_never_blocks_twice_and_a_line_already_there_is_spoken(self):
    speak.set_session(self.me, split='on')
    self.run_speak('say', '-', stdin='Primeira sem linha.')
    code, out, _ = self.run_speak('say', '-', stdin='Ainda sem linha.')  # the model ignored the request
    self.assertEqual((code, out), (0, ''))
    self.assertEqual(self.spoken(), [])
    self.assertIsNone(speak.read_pending(self.me))
    self.assertEqual(speak.read_last(self.me), ('Ainda sem linha.', 'summary'))
    code, out, _ = self.run_speak('say', '-', stdin='Corpo e linha juntos.\n🔊 Juntos.')
    self.assertEqual(out, '')
    self.assertEqual(self.spoken(), ['Juntos.'])

def test_a_stale_pending_body_is_replaced_by_a_new_reply(self):
    speak.set_session(self.me, split='on')
    self.run_speak('say', '-', stdin='Antiga.')
    _, out, _ = self.run_speak('say', '-', stdin='Corpo e linha.\n🔊 Linha.')
    self.assertEqual(out, '')
    self.assertIsNone(speak.read_pending(self.me))
    _, out, _ = self.run_speak('say', '-', stdin='Nova sem linha.')
    self.assertEqual(json.loads(out)['decision'], 'block')
    self.assertEqual(speak.read_pending(self.me), 'Nova sem linha.')

def test_split_does_nothing_when_the_line_is_not_wanted_or_the_hook_is_active(self):
    speak.set_session(self.me, split='on')
    with mock.patch.object(speak, 'silent_reason', lambda: 'off'):
        _, out, _ = self.run_speak('say', '-', stdin='Sem linha.')
    self.assertEqual(out, '')
    speak.set_session(self.me, mode='full')
    _, out, _ = self.run_speak('say', '-', stdin='Sem linha.')
    self.assertEqual(out, '')
    speak.set_session(self.me, mode='summary')
    _, out, _ = self.run_speak('say', '-', '--active', stdin='Sem linha.')
    self.assertEqual(out, '')
    self.assertIsNone(speak.read_pending(self.me))

def test_pending_of_a_dead_session_is_pruned(self):
    speak.set_session(self.other, split='on')
    self.run_speak('say', '-', stdin='Corpo.', session=self.other)
    self.sleep.kill(); self.sleep.wait()
    self.run_speak('on')  # set_session prunes the dead sessions
    self.assertNotIn(self.other, os.listdir(speak.PENDING))
```

Na classe `Hook` (2263), um teste de que o gancho repassa a saída e o campo: com o `speak` falso de `plugin()` gravando os argumentos, uma entrada `{"last_assistant_message": "oi", "stop_hook_active": true}` faz o falso receber `say - --active|oi`; e um `speak` falso que imprime `{"decision": "block", "reason": "x"}` faz o gancho sair com código 0 e essa linha na saída.

- [ ] **Step 2: Rodar e ver falhar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest tests.test_speak.Again tests.test_speak.Hook -v 2>&1 | tail -12`
Expected: FAIL (`read_pending` ausente; saída vazia).

- [ ] **Step 3: Implementar** no `bin/speak` o bloco Interfaces; o ramo `say` de `main` passa a testar `rest[:1] == ['-']` (e `'--active' in rest[1:]`) em vez de `text == '-'`; com `-` fica: lê a mensagem; `wanted = split(session) == 'on' and how == 'summary' and silent_reason() is None`; `pending = read_pending(session)`; se `wanted` e sem linha e `pending is None` e não `--active`: `save_pending`, `print(block_output(SPLIT_REASON % SIZE_SPOKEN[summary_size(session)]))`, `return 0`; se `wanted` e `pending is not None` e `only_line(message)`: `message = pending.rstrip() + '\n\n' + message.strip()`; `drop_pending(session)`; `save_last` e `speak_background` como hoje. Em `hooks/speak-stop.py`: `args = ['say', '-'] + (['--active'] if data.get('stop_hook_active') else [])`, `stdout=subprocess.PIPE`, e `sys.stdout.write(r.stdout.decode('utf-8', 'replace'))` quando não vazio; docstring atualizado.

- [ ] **Step 4: Rodar a bateria**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add bin/speak hooks/speak-stop.py tests/test_speak.py
git commit -m "feat: o gancho de parada pede a linha 🔊 numa mensagem própria com split ligado"
```

### Task 3: Gancho de mensagem nova e regra

**Files:**
- Modify: `hooks/speak-cut.py` (`mode_note`, linha 45; constantes)
- Modify: `bin/speak` (`read_session`: `told` aceita `'split'`; `rule()`/`RULE_LINE`)
- Modify: `rules/speak.md`
- Test: `tests/test_speak.py` (classe `Silent`)

**Interfaces:**
- Consumes: `speak split`, `speak say -` com pendente (tarefa 2), `speak told`.
- Produces: `NOTE_SPLIT` (texto de Global Constraints); `speak told split`; um comando `speak pending` que sai com 0 quando a sessão tem corpo pendente (como `speak forgot`).

- [ ] **Step 1: Testes** na classe `Silent`, no estilo de `test_a_voz_que_volta_avisa_uma_vez`:

```python
def test_split_tells_the_model_at_each_message_and_the_return_once(self):
    self.env['CLAUDE_SPEAK_SESSION'] = speak.session_key(os.getpid())
    def run(*args, stdin=None):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, env=self.env, input=stdin)
    run('rule')
    run('quiet')  # no engine here: in quiet the line is still wanted and nothing plays
    run('split', 'on')
    self.assertIn('mensagem própria', self.cut())
    self.assertIn('mensagem própria', self.cut())
    run('say', '-', stdin='Corpo sem linha.')  # blocked: pending body, the continuation turn
    self.assertEqual(self.cut(), '')
    run('say', '-', stdin='🔊 Linha.')
    self.assertIn('mensagem própria', self.cut())
    run('split', 'off')
    self.assertIn('termine esta resposta com a linha 🔊', self.cut())
    self.assertEqual(self.cut(), '')

def test_split_is_silent_with_the_voice_off_or_the_full_reading(self):
    self.engine()
    self.env['CLAUDE_SPEAK_SESSION'] = speak.session_key(os.getpid())
    def run(*args):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, env=self.env)
    run('rule'); run('split', 'on'); run('off')
    self.assertIn('desligada', self.cut())
    run('on'); run('mode', 'full')
    self.assertIn('inteira', self.cut())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest tests.test_speak.Silent -k split -v 2>&1 | tail -6`
Expected: FAIL (nota ausente).

- [ ] **Step 3: Implementar**: em `mode_note()` de `hooks/speak-cut.py`, no ramo `summary`: se `split` ligado (lido do mesmo `status --json`): com `speak pending` em 0, não imprime nada; senão `speak told split` e devolve `NOTE_SPLIT`; se `split` desligado e `told == 'split'`, `speak told summary` e `NOTE_BACK`; o lembrete de `forgot` só sem `split`. Em `bin/speak`: `read_session` aceita `told == 'split'`; o comando `pending`; `rule()` acrescenta, com `split` ligado no modo resumo, a frase "The summary goes in its own message (`speak split on`): do not end the reply with the `🔊` line; the Stop hook asks for it right after, and then you answer with only that line." Em `rules/speak.md`: um item "The summary in its own message ('manda o resumo numa mensagem separada', 'resumo em mensagem própria'; back: 'resumo junto com a resposta de novo'): `speak split on` or `speak split off`. With it on, a `speak:` note at each message says to leave the line out of the reply; the Stop hook then asks for it, and the answer is only the `🔊` line."; a lista de `/speak` ao fim inclui `split` (com `all`).

- [ ] **Step 4: Rodar a bateria**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add hooks/speak-cut.py bin/speak rules/speak.md tests/test_speak.py
git commit -m "feat: o modelo é avisado do resumo em mensagem própria"
```

### Task 4: Painel e comando escrito

**Files:**
- Modify: `hooks/register.tsx` (`State`; tabelas perto de `MODES`, linha 25; `USAGE`; `said`; `direct`; `ROWS`; `shown` 437; `argumentHint`)
- Test: `hooks/register.test.tsx`

**Interfaces:**
- Consumes: `status --json` com `split` e `scope.split`; `speak split on|off [all]`.
- Produces: `SPLITS = { off: 'Não', on: 'Sim' }`; linha `{ key: 'split', label: 'Resumo em mensagem própria', ... }` logo depois de `size`; `Key` ganha `'split'`.

- [ ] **Step 1: Testes**: no `process.run` falso, `if (args[0] === 'split') st.split = args[1]!` e `split: 'off'` e `scope.split: 'all'` no estado inicial. Atualizar as listas de chaves esperadas: `['where', 'power', 'mode', 'size', 'split', 'voice', 'mic']` no modo resumo e `['where', 'power', 'mode', 'voice', 'mic']` na leitura inteira (a linha some com o tamanho). Testes novos:

```ts
test('a linha do resumo em mensagem própria roda speak split e diz o que vale', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  const s = await selects(ui)
  expect(s.split.label).toMatch(/^Resumo em mensagem própria\s*$/)
  expect(s.split.options.map((o: any) => o.label)).toEqual(['Não', 'Sim'])
  await ui.select({ key: 'split', value: 'on' })
  expect(changes(ran)).toEqual(['split on all'])
  expect(await footer(ui)).toBe('O resumo passa a vir numa mensagem própria em todas as sessões.')
  await ui.select({ key: 'split', value: 'off' })
  expect(await footer(ui)).toBe('O resumo volta a fechar a própria resposta em todas as sessões.')
  await ui.unmount()
})

test('/speak split escrito roda direto; sem valor abre o painel na linha', async ($, on) => {
  const { ran, opened } = await setup($, on)
  const r = await $.command.run({ command: 'speak', args: 'split on' })
  expect(changes(ran)).toEqual(['split on'])
  expect(r.text).toBe('O resumo passa a vir numa mensagem própria nesta sessão.')
  await $.command.run({ command: 'speak', args: 'split' })
  expect(opened.length).toBe(1)
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `claude plugin test . 2>&1 | tail -12`
Expected: FAIL nos novos e nas listas de chaves.

- [ ] **Step 3: Implementar** em `hooks/register.tsx`: `State.split?: string` e `scope.split`; `SPLITS`; a linha em `ROWS` com `current: s => s.split ?? 'off'` e `own: s => s.scope?.split === 'session'`; `shown` esconde `split` como `size` no modo `full`; `direct` com `case 'split': return value ? runChoice($, 'split', value, SPLITS, tail) : undefined`; `said` com as duas frases; `USAGE`, `argumentHint` e o comentário do topo.

- [ ] **Step 4: Rodar**

Run: `claude plugin test . 2>&1 | tail -4 && claude plugin validate . 2>&1 | tail -2`
Expected: todos passam; validação limpa.

- [ ] **Step 5: Commit**

```bash
git add hooks/register.tsx hooks/register.test.tsx
git commit -m "feat: painel e /speak split"
```

### Task 5: Conferência numa sessão de verdade

**Files:**
- Nenhum arquivo do projeto muda; só um gancho de registro descartável fora do repositório.

- [ ] **Step 1: Ver o que chega ao gancho de parada na volta a mais**: numa sessão do Claude Code com `--plugin-dir .` (ou com o plugin publicado depois), ligar `speak split on`, pedir uma resposta qualquer e conferir no `state/pending/` e no `state/last/<sessão>` da pasta de dados: o pendente some, a última resposta tem corpo e linha uma vez só, e a fala toca a linha. Se `last_assistant_message` na segunda parada trouxer corpo e linha, o item "corpo e linha juntos" já cobre (fala sem duplicar), mas a separação não acontece: registrar em `docs/proximos-passos.md` e parar aqui para decidir com o Ricardo.

- [ ] **Step 2: Ver se o gancho de mensagem nova dispara na volta a mais**: na mesma sessão, olhar o `told` da sessão e a saída do `/speak status`; se a nota do `split` tiver aparecido na volta (visível no transcript como `speak:`), a tarefa 3 já cobre pelo pendente; confirmar que nenhuma nota saiu nessa volta.

- [ ] **Step 3: Ver o que o terminal mostra** do motivo do bloqueio e anotar em `docs/proximos-passos.md`. Se a tela mostrar um erro de gancho feio, trocar `block_output` por `{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": reason}}` e repetir o passo 1: se o modelo continuar e escrever a linha, fica essa forma; senão volta ao `block`.

### Task 6: Documentação e versão 0.19.0

**Files:**
- Modify: `README.md` (tabela do painel: linha nova depois de "Tamanho do resumo"; tabela de comandos: `/speak split on` · `off`; "Em palavras"; uma frase sobre o custo: uma chamada a mais do modelo por resposta, só com a escolha ligada, feita para o play do app do celular tocar só o resumo)
- Modify: `CHANGELOG.md`, `.claude-plugin/plugin.json`, `tests/test_speak.py` (teste da versão), `docs/proximos-passos.md` (em "Feito": 0.19.0; em "Pendências": o teste no celular do Ricardo, noutro repositório e conta, com a reserva da chamada de ferramenta se o app não mostrar o play próprio)

- [ ] **Step 1: Documentar** como acima; CHANGELOG `## [0.19.0] - <data>` em "Adicionado", para quem usa.

- [ ] **Step 2: Verificar tudo**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -3; claude plugin test . 2>&1 | tail -3; claude plugin validate . 2>&1 | tail -2`
Expected: `OK`, módulo passando, validação limpa.

- [ ] **Step 3: Publicar** pelo fluxo de `.claude/rules/git-workflow.md`: `chore: versão 0.19.0`, marca `v0.19.0`, push, release com as notas da seção, `claude plugin marketplace update cc-speaker` e `claude plugin update speak@cc-speaker`.
