# Voz com três estados (0.18.0): plano de construção

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A voz ganha o estado do meio, `quiet` (só o resumo escrito): não fala, mas a linha 🔊 continua a sair, no painel, por escrito e em palavras, com alcance por sessão ou geral.

**Architecture:** O valor geral da voz deixa de ser a existência de `conf/off` e vira o arquivo `conf/power` (`on`, `quiet`, `off`), migrado uma vez; o campo `voice` da sessão ganha o valor `quiet`. Uma função `power(session)` responde o estado com a precedência de hoje, `is_on()` passa a ser `power() == 'on'`, e `silent_reason()` (que alimenta o gancho de mensagem nova) só pede a linha fora quando o estado é `off` ou quando é `on` sem motor. Painel e regra ganham o valor novo.

**Tech Stack:** Python 3 (`bin/speak`, ganchos), TypeScript do módulo (`hooks/register.tsx`), `unittest`, `claude plugin test`.

**Spec:** `docs/superpowers/specs/2026-11-05-resumo-sem-narracao-design.md` (parte 1).

## Global Constraints

- Texto ao usuário em português do Brasil, com acentos; comentários e docstrings do código em inglês, como o resto do arquivo.
- Testes: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests`, `claude plugin test .`, `claude plugin validate .`.
- Rótulos fixados pelo desenho: comando `speak quiet [all]`; painel "Ligada" / "Só o resumo escrito" / "Desligada"; `status` com `voz: só o resumo escrito`, `geral: só o resumo escrito`, `esta sessão: só o resumo`; rodapé "A voz está calada nesta sessão; o resumo continua escrito." (ou "em todas as sessões").
- `status --json`: `on` continua booleano (falso em `quiet` e `off`); nasce `power` com `on`, `quiet` ou `off`.
- Em `quiet` a linha 🔊 é pedida mesmo sem motor; na leitura inteira (`mode full`) nada muda em relação a hoje (nenhuma linha).
- Uma pasta de dados antiga com `conf/off` continua a ler "desligada".
- Commits direto na `main`, sem linha de atribuição; a versão sobe para 0.18.0 e sai pelo fluxo de `.claude/rules/git-workflow.md`.

## Review Focus

- `CLAUDE_SPEAK=0` numa sessão `quiet`: a semente `muted` só entra quando a sessão não tem arquivo; uma sessão já em `quiet` continua `quiet` (teste na tarefa 1).
- `speak on all` depois de `speak quiet` numa sessão: a exceção da sessão some e ela segue a geral (teste na tarefa 1).
- `speak quiet` corta a fala em curso da sessão, como `off` (teste na tarefa 2).
- `speak forgot` e o lembrete do gancho de mensagem nova em `quiet` com o motor faltando: a linha é pedida e o lembrete repete, sem a nota "/speak install" (teste na tarefa 3).
- Painel com `status --json` antigo (sem `power`, vindo de um `speak` velho no cache): a linha "Voz" cai em `on`/`off` pelo booleano (teste na tarefa 4).

---

### Task 1: O estado `power` no `bin/speak`

**Files:**
- Modify: `bin/speak` (constantes perto de `OFF_FLAG`, linha 93; `read_session` 314; `session_choice` 341; `is_on` 426; `silent_reason` ~2003; `status` 1898; `status_json` ~2017; `main` 2040; `_translate_config`/`migrate` 1926)
- Test: `tests/test_speak.py` (classe `Session`, linha 1116; classe `Silent`, 2364; classe `Migration`, 1004)

**Interfaces:**
- Produces: `POWER_FILE = os.path.join(CONF, 'power')`; `POWERS = ('on', 'quiet', 'off')`; `general_power() -> str` (valor de `POWER_FILE`, senão `'off'` se `OFF_FLAG` existir, senão `'on'`); `power(session=None) -> str` (campo `voice` da sessão: `speaking`→`on`, `quiet`→`quiet`, `muted`→`off`, passando por `session_choice` para manter a semente de `CLAUDE_SPEAK=0`; fora de sessão com `CLAUDE_SPEAK=0`→`off`; senão `general_power()`); `is_on(session=None) -> bool` = `power(session) == 'on'`; `set_general_power(value)` (escreve `POWER_FILE` e apaga `OFF_FLAG`; `on` apaga os dois); `POWER_TEXT = {'on': 'ligada', 'quiet': 'só o resumo escrito', 'off': 'desligada'}`; o comando `speak quiet [all]`.

- [ ] **Step 1: Escrever os testes que falham** em `tests/test_speak.py`, classe `Session`:

```python
def test_quiet_mutes_this_session_and_keeps_the_line(self):
    self.speak('quiet', session=self.me)
    mine = self.speak('status', session=self.me).stdout
    self.assertIn('voz: só o resumo escrito · só nesta sessão', mine)
    self.assertIn('esta sessão: só o resumo', mine)
    self.assertIn('voz: ligada', self.speak('status', session=self.other).stdout)
    self.assertEqual(json.loads(self.speak('status', '--json', session=self.me).stdout)['power'], 'quiet')
    self.assertFalse(json.loads(self.speak('status', '--json', session=self.me).stdout)['on'])

def test_quiet_all_is_general_and_on_all_clears_it(self):
    self.speak('quiet', 'all', session=self.me)
    self.assertIn('geral: só o resumo escrito', self.speak('status', session=self.other).stdout)
    self.speak('quiet', session=self.other)
    self.speak('on', 'all', session=self.me)
    other = self.speak('status', session=self.other).stdout
    self.assertIn('voz: ligada', other)
    self.assertIn('segue a geral', other)

def test_env_mute_does_not_overwrite_a_quiet_session(self):
    self.speak('quiet', session=self.me)
    self.assertIn('esta sessão: só o resumo', self.speak('status', session=self.me, CLAUDE_SPEAK='0').stdout)

def test_quiet_with_bad_scope_is_refused(self):
    r = self.speak('quiet', 'todas', session=self.me)
    self.assertEqual(r.returncode, 2)
    self.assertIn('speak quiet', r.stderr)
```

Classe `Silent` (usa `self.engine()`, `self.silent()`):

```python
def test_quiet_asks_for_the_line_with_or_without_the_engine(self):
    subprocess.run([sys.executable, '-I', SPEAK, 'quiet'], capture_output=True, env=self.env)
    self.assertEqual(self.silent().returncode, 1)  # no engine: the line is still wanted
    self.engine()
    self.assertEqual(self.silent().returncode, 1)
```

Classe `Migration` (ver como os outros testes dela montam a pasta `conf`): com `conf/off` presente e sem `conf/power`, `speak status` diz `voz: desligada` e `geral: desligada`, e depois existe `conf/power` com `off` e `conf/off` sumiu.

- [ ] **Step 2: Rodar e ver falhar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest tests.test_speak.Session tests.test_speak.Silent tests.test_speak.Migration -v 2>&1 | tail -20`
Expected: os testes novos falham (`speak quiet` devolve o uso, código 2; `power` ausente do JSON).

- [ ] **Step 3: Implementar** em `bin/speak`: as constantes e funções do bloco Interfaces; `read_session` aceita `voice` em `('muted', 'speaking', 'quiet')`; `status()` usa `POWER_TEXT[power(session)]` na linha `voz:`, `POWER_TEXT[general_power()]` em `geral:` e `{'muted': 'muda', 'speaking': 'falando', 'quiet': 'só o resumo'}` em `esta sessão:`; `status_json()` ganha `'power': power(session)`; `silent_reason()` devolve `'off'` quando `power(...) == 'off'`, `None` quando `'quiet'`, e segue como hoje em `'on'`; em `main`, o ramo `if cmd in ('on', 'off')` vira `('on', 'off', 'quiet')`, com a mensagem de uso citando `speak quiet`, `quiet` gravando `set_session(session, voice='quiet')` + `stop_if_mine(session)` (sessão) ou `set_general_power('quiet')` + `mark_all()` + `clear_all_sessions('voice')` + `stop_current()` (`all`); `off all` passa por `set_general_power('off')` e `on all` por `set_general_power('on')`; `migrate()` chama uma `_migrate_off_flag()` que, com `OFF_FLAG` presente e `POWER_FILE` ausente, grava `off` e apaga o `OFF_FLAG` (erros de SO ignorados). O docstring de ajuda no topo do arquivo lista `speak on | quiet | off [all]`.

- [ ] **Step 4: Rodar a bateria inteira**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -5`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add bin/speak tests/test_speak.py
git commit -m "feat: estado quiet da voz, só o resumo escrito"
```

### Task 2: `quiet` corta a fala como `off`

**Files:**
- Test: `tests/test_speak.py` (classe que tem `test_off_here_cuts_only_my_speech`, linha 1373, e `test_off_in_a_session_drops_only_its_speeches`, 1706)

**Interfaces:**
- Consumes: o comando `speak quiet` da tarefa 1.

- [ ] **Step 1: Escrever os testes** copiando `test_off_here_cuts_only_my_speech` e `test_off_in_a_session_drops_only_its_speeches` com `quiet` no lugar de `off` (nomes `test_quiet_here_cuts_only_my_speech` e `test_quiet_in_a_session_drops_only_its_speeches`).

- [ ] **Step 2: Rodar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests -k quiet 2>&1 | tail -5`
Expected: `OK` (a tarefa 1 já corta; se falhar, o corte ficou fora do ramo `quiet` em `main`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_speak.py
git commit -m "test: quiet corta a fala como off"
```

### Task 3: Gancho de mensagem nova e regra

**Files:**
- Modify: `hooks/speak-cut.py` (`NOTE_REMIND`, linha 21; docstring)
- Modify: `rules/speak.md` (itens "When the voice is off" e "Turn on or off"; a lista de `/speak` ao fim)
- Modify: `bin/speak` (`RULE_LINE['summary']`, linha 105)
- Test: `tests/test_speak.py` (classe `Silent`: `test_the_reminder_repeats_until_a_reply_has_the_line`, 2523, e vizinhos)

**Interfaces:**
- Consumes: `speak quiet`, `speak silent` da tarefa 1.
- Produces: `NOTE_REMIND = ('speak: a linha 🔊 está pedida e a sua última resposta ficou sem ela; termine esta resposta com a linha 🔊. Os avisos anteriores de "não escreva a linha" não valem mais.')`.

- [ ] **Step 1: Escrever os testes** na classe `Silent`, no estilo de `test_the_reminder_follows_the_voice_coming_back`:

```python
def test_quiet_brings_the_line_back_and_reminds_without_the_engine(self):
    """Off then quiet, no engine: the model is told once the line is back, then reminded while replies lack it."""
    self.env['CLAUDE_SPEAK_SESSION'] = speak.session_key(os.getpid())
    def run(*args, stdin=None):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, env=self.env, input=stdin)
    run('rule')
    run('off')
    self.assertIn('desligada', self.cut())
    run('quiet')
    self.assertIn('termine esta resposta com a linha 🔊', self.cut())
    run('say', '-', stdin='Sem linha.')
    note = self.cut()
    self.assertIn('ficou sem ela', note)
    self.assertNotIn('/speak install', note)
    run('say', '-', stdin='Com linha.\n🔊 Pronto.')
    self.assertEqual(self.cut(), '')
```

E trocar o texto esperado `remind` em `test_the_reminder_repeats_until_a_reply_has_the_line` pelo novo `NOTE_REMIND`. Na classe que testa `speak rule` (procurar `run('rule')` ou `test_rule`): a regra impressa contém `speak quiet`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest tests.test_speak.Silent -v 2>&1 | tail -8`
Expected: falham no texto do lembrete e na regra.

- [ ] **Step 3: Implementar**: `NOTE_REMIND` novo e docstring de `hooks/speak-cut.py` citando `quiet`; em `bin/speak`, `RULE_LINE['summary']` começa com "While the voice is on or quiet (`speak quiet`: silent, the line kept), every reply to the human ends with..."; em `rules/speak.md`: o item "When the voice is off, leave the line out" ganha "With `speak quiet` the voice is silent but the line stays, written as when the voice is on; a `speak quiet` you just ran brings the line back."; o item "Turn on or off" vira "Turn on, off or silent with the summary kept ('cala a voz mas deixa o resumo', 'só o resumo escrito', 'sem áudio, só o texto'): `speak on`, `speak off` or `speak quiet`; plain 'silêncio' or 'desliga a voz' is `speak off`."; a lista final de `/speak` inclui `quiet` entre os que aceitam `all`.

- [ ] **Step 4: Rodar a bateria inteira**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -5`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add hooks/speak-cut.py rules/speak.md bin/speak tests/test_speak.py
git commit -m "feat: a regra e o gancho de mensagem nova conhecem o estado quiet"
```

### Task 4: Painel e comando escrito no módulo

**Files:**
- Modify: `hooks/register.tsx` (`State` linha 13; `POWER` 30; `USAGE` 32; `said` 317; `direct` 349; `ROWS` 429; `argumentHint` 606)
- Test: `hooks/register.test.tsx` (`setup`, o `process.run` falso, linha ~80; os testes que enumeram `['where', 'power', ...]`)

**Interfaces:**
- Consumes: `status --json` com `power` (tarefa 1); `speak quiet [all]`.
- Produces: `POWER = { on: 'Ligada', quiet: 'Só o resumo escrito', off: 'Desligada' }`; `State.power?: string`.

- [ ] **Step 1: Escrever os testes** em `hooks/register.test.tsx`: no `process.run` falso, `if (args[0] === 'on' || args[0] === 'off' || args[0] === 'quiet') { st.on = args[0] === 'on'; st.power = args[0] }` e `power: 'on'` no estado inicial `st`. Testes novos:

```ts
test('a linha Voz tem o valor do meio e ele roda speak quiet', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  expect((await selects(ui)).power.options.map((o: any) => o.label)).toEqual(['Ligada', 'Só o resumo escrito', 'Desligada'])
  await ui.select({ key: 'power', value: 'quiet' })
  expect(changes(ran)).toEqual(['quiet all'])
  expect((await selects(ui)).power.value).toBe('quiet')
  expect(await footer(ui)).toBe('A voz está calada em todas as sessões; o resumo continua escrito.')
  await ui.unmount()
})

test('/speak quiet escrito roda direto e diz o que vale', async ($, on) => {
  const { ran } = await setup($, on)
  const r = await $.command.run({ command: 'speak', args: 'quiet' })
  expect(changes(ran)).toEqual(['quiet'])
  expect(r.text).toBe('A voz está calada nesta sessão; o resumo continua escrito.')
})

test('sem o campo power no estado, a linha Voz cai no ligada/desligada', async ($, on) => {
  const { st } = await setup($, on, { init: { power: undefined, on: false } })
  const { ui } = await openMenu($)
  expect((await selects(ui)).power.value).toBe('off')
  await ui.unmount()
})
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `claude plugin test . 2>&1 | tail -15`
Expected: os três falham (valor `quiet` desconhecido, texto do rodapé).

- [ ] **Step 3: Implementar** em `hooks/register.tsx`: `POWER` com três valores; `State.power?: string`; a linha `power` de `ROWS` com `current: s => s.power ?? (s.on ? 'on' : 'off')`; `said` com `case 'quiet': return \`A voz está calada ${where(all)}; o resumo continua escrito.\``; `direct` com `case 'quiet'` junto de `on`/`off`; `USAGE` e `argumentHint` com `quiet`; o comentário do topo do arquivo cita o valor.

- [ ] **Step 4: Rodar**

Run: `claude plugin test . 2>&1 | tail -5 && claude plugin validate . 2>&1 | tail -3`
Expected: todos passam; validação sem erros.

- [ ] **Step 5: Commit**

```bash
git add hooks/register.tsx hooks/register.test.tsx
git commit -m "feat: painel e /speak quiet com o estado só o resumo escrito"
```

### Task 5: Documentação e versão 0.18.0

**Files:**
- Modify: `README.md` (tabelas do painel e dos comandos, linhas 54 e 75; "Em palavras", 92; "Enquanto o motor falta, o Claude não escreve a linha 🔊", ~116)
- Modify: `CHANGELOG.md`, `.claude-plugin/plugin.json`, `tests/test_speak.py:3834`, `docs/proximos-passos.md`

- [ ] **Step 1: Documentar**: README, linha "Voz" da tabela do painel: "ligada (padrão), só o resumo escrito (a voz cala e a linha 🔊 continua saindo, mesmo sem o motor; na leitura inteira vale como desligada) ou desligada"; tabela de comandos: `/speak on` · `/speak quiet` · `/speak off`; "Em palavras" ganha "cala a voz mas deixa o resumo"; a frase do motor faltando ganha "a não ser que a voz esteja em só o resumo escrito". CHANGELOG: `## [0.18.0] - 2026-11-05` com "Adicionado" descrevendo o estado para quem usa (reunião: ler sem ouvir; "Ouvir de novo" continua), link ao pé e "Não lançado" comparando com `v0.18.0`. `plugin.json` e o teste da versão em 0.18.0. `docs/proximos-passos.md`: em "Feito", a entrada da 0.18.0; em "Pedidos para depois", a entrada do pedido de 05/11/2026 passa a dizer que o item 1 saiu na 0.18.0 e aponta o desenho; nas decisões, os nomes `quiet` e `split` e o gancho de parada.

- [ ] **Step 2: Verificar tudo**

Run: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests 2>&1 | tail -3; claude plugin test . 2>&1 | tail -3; claude plugin validate . 2>&1 | tail -2`
Expected: `OK`, testes do módulo passando, validação limpa.

- [ ] **Step 3: Publicar** pelo fluxo de `.claude/rules/git-workflow.md`: commit `chore: versão 0.18.0`, marca `v0.18.0`, `git push origin main v0.18.0`, `gh release create v0.18.0 --title "v0.18.0" --notes-file <seção do CHANGELOG> --verify-tag`, `claude plugin marketplace update cc-speaker` e `claude plugin update speak@cc-speaker`.
