# Menu de setas, alcance, dados na pasta do plugin e Mac: plano de construção

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/speak` com menu de setas que fica aberto, alcance guardado de verdade, tudo do plugin na pasta de dados dele (a desinstalação apaga) e o plugin rodando no macOS.

**Architecture:** O que depende do sistema sai de `bin/speak` para `lib/speak_os.py` (mesma interface no Linux e no Mac), e a raiz de dados para `lib/speak_paths.py`; `bin/speak` e os ganchos Python importam de `lib/`. O menu é um painel com um `Client` (`hooks/menu.tsx`) que trata as setas e manda cada troca ao módulo de ganchos (`hooks/register.tsx`), que roda o `bin/speak`.

**Tech Stack:** Python 3 só com a biblioteca padrão (ctypes no Mac), módulo de ganchos TSX do Claude Code 2.1.312, `unittest`, `claude plugin test`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-29-menu-dados-mac-design.md`

## Global Constraints

- Versão final 0.6.0 em `.claude-plugin/plugin.json` (e no teste que a fixa em `tests/test_speak.py`).
- Raiz de dados: `CLAUDE_PLUGIN_DATA`; senão derivada do lugar do script (`.../plugins/cache/<catálogo>/<plugin>/<versão>/...` → `.../plugins/data/<plugin>-<catálogo>`); senão `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/data/speak-cc-speaker`. Subpastas `engine/`, `config/`, `state/`. XDG deixa de valer.
- Linux e Mac; Windows fora. Sem dependência nova no Python do sistema (Mac: ctypes e `ps`, `afplay`).
- Textos ao humano em português do Brasil; comentários no estilo do código em volta.
- Ganchos sempre saem com código 0.
- Menu: linhas **Mudar em** (Todas as sessões / Só nesta sessão), **Voz** (Ligada / Desligada), **Leitura** (Resposta inteira / Só o resumo), **Tamanho do resumo** (Pequeno / Médio / Grande), **Voz de leitura** (Dora / Alex / Santa); marca `· só nesta sessão`; rodapé de ajuda `↑↓ ajuste · ←→ valor · Esc fecha`.
- Commits na main, sem push (o controlador envia no fim), mensagens `<tipo>: <assunto>` em português, sem linha de atribuição.

## Review Focus

- Pastas antigas e novas existindo ao mesmo tempo (a nova vence, nada é apagado das antigas além do que foi movido): coberto na Tarefa 2.
- Sessão aberta antes da mudança de pastas segue funcionando (arquivo de sessão migra com o estado): coberto na Tarefa 2.
- `ps` ausente ou com saída inesperada no Mac: `current_session()` devolve `None` sem exceção: coberto na Tarefa 1.
- Seta para os lados numa linha com o `speak` falhando (motor ausente): rodapé mostra o erro e o valor na tela volta ao lido do estado: coberto na Tarefa 5.
- Desinstalação com `--keep-data` e reinstalação: a pasta antiga é reaproveitada, sem baixar o motor de novo: coberto na Tarefa 2 (o motor existente na raiz nova não é rebaixado).

---

### Task 1: Peça por sistema para processos e sessão

**Files:**
- Create: `lib/speak_os.py`
- Modify: `bin/speak` (funções `_stat_fields`, `session_key`, `current_session`, `session_started`, `prune_tmp`, `is_speech` passam a chamar a peça)
- Test: `tests/test_speak_os.py`

**Interfaces:**
- Produces, em `lib/speak_os.py`: `SYSTEM: str` (`'linux'` ou `'mac'`, por `sys.platform`); `parent(pid: int) -> int | None`; `name(pid: int) -> str | None` (nome base do executável); `started(pid: int) -> str | None` (texto estável do início do processo, usado na chave); `started_at(pid: int) -> float | None` (segundos desde a época); `alive(pid: int) -> bool`; `argv(pid: int) -> list[str] | None`; `ancestors(pid: int) -> list[tuple[int, str]]` (para `speak check`).
- `bin/speak` passa a inserir no `sys.path` a pasta `lib/` ao lado da sua (`os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'lib')`), porque `python3 -I` não põe a pasta do script.

- [ ] **Step 1: Testes que falham** em `tests/test_speak_os.py`, carregando `lib/speak_os.py` como os testes atuais carregam `bin/speak`:
  - `test_linux_le_proc`: com `/proc` simulado (`mock.patch('builtins.open')` sobre `/proc/<pid>/stat`, `/proc/<pid>/comm`, `/proc/<pid>/cmdline`), `parent`, `name`, `started`, `argv` devolvem os valores do arquivo.
  - `test_mac_le_ps`: com `SYSTEM='mac'` e `subprocess.run` simulado: `ps -o ppid=,comm= -p 42` → `'  1 /Applications/Claude.app/Contents/MacOS/claude\n'` dá `parent(42)==1` e `name(42)=='claude'`; `ps -o lstart= -p 42` → `'Wed Oct 29 10:00:00 2026\n'` dá `started(42)` estável e `started_at(42)` em segundos; `ps -o command= -p 42` → `argv`.
  - `test_mac_node`: `name` devolve `'node'` e `argv` `['node', '/usr/local/bin/claude']`: `current_session()` em `bin/speak` acha esse ancestral (argumento de nome base `claude`).
  - `test_ps_falha`: `subprocess.run` levanta `OSError` ou devolve saída vazia: todas devolvem `None`/`False`/`[]`, sem exceção; `current_session()` devolve `None`.
- [ ] **Step 2:** `python3 -m unittest tests.test_speak_os -v` → FALHA (módulo ausente).
- [ ] **Step 3:** Implementar `lib/speak_os.py` (Linux: o código de hoje, movido; Mac: `ps`, `os.kill(pid, 0)` em `alive`) e trocar em `bin/speak` as leituras de `/proc` pelas funções da peça. `session_key(pid)` continua `'<pid>-<início>'`. `current_session()`: primeiro ancestral com `name == 'claude'`; senão, primeiro cujo `argv` tenha um item de nome base `claude`. `speak check` imprime `ancestors(os.getppid())` numa linha "processos acima: pid nome, ...".
- [ ] **Step 4:** `python3 -m unittest discover -s tests` → OK (os 117 de antes e os novos).
- [ ] **Step 5:** Commit `refactor: peça por sistema para processos e sessão (Linux e Mac)`.

### Task 2: Raiz de dados na pasta do plugin e mudança única

**Files:**
- Create: `lib/speak_paths.py`
- Modify: `bin/speak` (DATA, CONF, STATE, `migrate()`, `install()`), `hooks/speak-start.py`, `hooks/speak-cut.py`, `hooks/speak-stop.py` (importam de `lib/`)
- Test: `tests/test_speak_paths.py`, `tests/test_speak.py` (ajustar onde fixa caminhos XDG)

**Interfaces:**
- Consumes: nada da Tarefa 1.
- Produces, em `lib/speak_paths.py`: `root(script: str) -> str` (a regra das Global Constraints); `ENGINE`, `CONFIG`, `STATE` calculados por `paths(script) -> tuple[str, str, str]`; `migrate_old(root: str) -> list[str]` (move as pastas antigas, devolve o que moveu).
- `speak-start.py` escreve `export CLAUDE_PLUGIN_DATA=<raiz>` em `$CLAUDE_ENV_FILE` quando a variável do arquivo existir (acrescenta, sem duplicar a linha).

- [ ] **Step 1: Testes que falham** em `tests/test_speak_paths.py` (pastas num `tempfile.TemporaryDirectory` como `HOME`):
  - `test_raiz_pela_variavel`: `CLAUDE_PLUGIN_DATA=/x` → `root(...) == '/x'`.
  - `test_raiz_pelo_lugar_do_script`: script em `<home>/.claude/plugins/cache/cat/plug/1.0/bin/speak` → `<home>/.claude/plugins/data/plug-cat`.
  - `test_raiz_reserva`: script fora do cache, sem variável → `<home>/.claude/plugins/data/speak-cc-speaker`; com `CLAUDE_CONFIG_DIR=/c` → `/c/plugins/data/speak-cc-speaker`.
  - `test_muda_uma_vez`: com `~/.local/share/claude-speak/model.onnx`, `~/.config/claude-speak/voice`, `~/.local/state/claude-speak/sessions/k` → depois de `migrate_old`, os três estão em `engine/`, `config/`, `state/` e as antigas não existem; segunda chamada não faz nada.
  - `test_nova_vence`: raiz com `engine/` já existente → nada é movido e as antigas ficam intactas.
  - `test_env_file`: `speak-start.py` com `CLAUDE_ENV_FILE` apontando para um arquivo vazio escreve uma linha `export CLAUDE_PLUGIN_DATA=...`; rodado de novo, não duplica.
- [ ] **Step 2:** `python3 -m unittest tests.test_speak_paths -v` → FALHA.
- [ ] **Step 3:** Implementar `lib/speak_paths.py`; `bin/speak` e os três ganchos passam a usar `paths(__file__)` (ganchos inserem `lib/` no `sys.path` como `bin/speak`); `migrate()` chama `migrate_old` antes da migração de `claude-voz`. Depois de mover, se o python do ambiente do motor (`engine/venv/bin/python`) não rodar `-c pass`, `install()` reconstrói só o ambiente com o `uv`, sem baixar o modelo nem as vozes de novo (conferir o que o `uv venv` grava; o mais simples que funcione). O módulo `register.tsx` passa `env: { CLAUDE_PLUGIN_DATA }` em `$.process.run` se os tipos derem a pasta de dados do plugin (procurar `data` em `PluginInfo`/`$.plugin` nos tipos); se não derem, não passa (o script deriva pelo lugar).
- [ ] **Step 4:** `python3 -m unittest discover -s tests` → OK.
- [ ] **Step 5:** Commit `feat: motor, escolhas e estado na pasta de dados do plugin`.

### Task 3: Instalação automática numa máquina limpa

O Ricardo precisou rodar `speak install` à mão no Ubuntu 24 depois de instalar o plugin. Causa ainda desconhecida (a correção do `pw-play` antigo, `635ecd3`, é sobre tocar, não sobre instalar).

**Files:**
- Modify: o que a causa apontar (provável `hooks/speak-start.py` ou `bin/speak install`)
- Test: `tests/test_speak.py`

- [x] **Step 1:** Reproduzir com `superpowers:systematic-debugging`: `HOME` temporário, sem motor, `uv` real no PATH, rodar o gancho de começo como o Claude Code roda (`python3 -I hooks/speak-start.py` com a entrada JSON de `SessionStart`, `CLAUDE_PLUGIN_ROOT` e `CLAUDE_PLUGIN_DATA` definidos) e esperar o `install.log` e o resultado. Registrar a causa em "Decisões tomadas na execução" deste plano. Se não reproduzir, registrar o que foi tentado, acrescentar ao `speak check` a linha do último `install.log` (as três últimas linhas) e pedir ao Ricardo o arquivo do Ubuntu; não inventar correção.
- [x] **Step 2:** Teste que falha pela causa achada.
- [x] **Step 3:** Correção.
- [x] **Step 4:** `python3 -m unittest discover -s tests` → OK.
- [x] **Step 5:** Commit `fix: <causa>`.

### Task 4: Alcance de verdade

**Files:**
- Modify: `bin/speak` (`set_all_sessions`, `status`, `status_json`, `migrate`)
- Test: `tests/test_speak.py`

**Interfaces:**
- Produces: `clear_all_sessions(*fields: str) -> None` (remove os campos de todos os arquivos de sessão, mantendo o arquivo); `status --json` com `scope: {"on": "session"|"all", "mode": ..., "size": ...}`.

- [x] **Step 1: Testes que falham:**
  - `test_all_remove_das_sessoes`: duas sessões com `mode: full`; `speak mode summary all` → arquivo geral `summary`, as duas sessões sem o campo `mode`, `mode(sessão) == 'summary'`.
  - `test_on_all_marca_e_remove`: `speak on all` → `ALL_MARK` atualizado e campo `voice` removido das sessões; uma sessão semeada por `CLAUDE_SPEAK=0` aberta antes fica falando.
  - `test_status_marca`: sessão com `size: large` própria → linha `tamanho do resumo: large · só nesta sessão`; sem campo → sem a marca; voz de leitura nunca marcada.
  - `test_status_json_scope`: o mesmo caso dá `scope.size == 'session'`, `scope.mode == 'all'`.
  - `test_limpa_copias_antigas`: sessão com `mode` igual ao geral antes da mudança → depois de `migrate()`, sem `mode`; `voice` mantido.
- [x] **Step 2:** Rodar → FALHA.
- [x] **Step 3:** Implementar: os ramos `all` de on/off, mode e size chamam `clear_all_sessions` no lugar de `set_all_sessions`; status e json conforme a seção 2 do desenho.
- [x] **Step 4:** `python3 -m unittest discover -s tests` → OK.
- [x] **Step 5:** Commit `fix: alcance guardado; todas as sessões apaga as exceções em vez de copiar`.

### Task 5: Som e microfone no Mac

**Files:**
- Modify: `lib/speak_os.py`, `bin/speak` (`play`, `player_command`, `player_found`, `current_recordings`, `install` mensagens), `hooks/speak-start.py` (mensagem do tocador)
- Test: `tests/test_speak_os.py`

**Interfaces:**
- Produces, em `lib/speak_os.py`: `player() -> list[str] | None` (Linux: os três de hoje com o teste do `--raw`; Mac: `['afplay']` se existir); `streams() -> bool` (Linux `True`: lê da entrada; Mac `False`: toca um arquivo por pedaço); `mic_busy() -> bool | None` (Linux: `pw-dump` como hoje; Mac: CoreAudio por ctypes, `kAudioDevicePropertyDeviceIsRunningSomewhere` em cada dispositivo com canais de entrada; `None` quando não dá para ler).
- `play()` no Mac grava cada pedaço sintetizado num WAV em `state/` (`soundfile`, já no ambiente do motor), toca com `afplay <arquivo>`, apaga, e segue para o próximo; o corte pelo microfone mata o `afplay` em curso.

- [x] **Step 1: Testes que falham:** `test_mac_player_afplay` (com `shutil.which` simulado); `test_mac_mic_ctypes` (CoreAudio trocado por um objeto falso que diz um dispositivo de entrada rodando → `True`; nenhum → `False`; erro → `None`); `test_play_mac_arquivo_por_pedaco` (com síntese e `subprocess.Popen` falsos: dois pedaços → duas chamadas `afplay <wav>` e nenhum WAV sobrando).
- [x] **Step 2:** Rodar → FALHA.
- [x] **Step 3:** Implementar. Mensagens: Mac sem `afplay` (raro) e sem `uv` com o texto do Mac (`brew install uv` ou o instalador do site).
- [x] **Step 4:** `python3 -m unittest discover -s tests` → OK.
- [x] **Step 5:** Commit `feat: som e microfone no Mac`.

### Task 6: Menu de setas no `/speak`

**Files:**
- Create: `hooks/menu.tsx` (módulo de superfície do `Client`)
- Modify: `hooks/register.tsx` (sai o fluxo de `$.ui.ask`), `hooks/register.test.tsx`
- Referência: o protótipo testado pelo Ricardo em `/home/ricardo/.claude/dev-mods/5ac3a0af-a9e9-4494-ba16-8f491c360bbf/menu-demo/hooks/` (`menu.tsx`, `register.tsx`); tipos em `/tmp/claude-1000/bundled-skills/2.1.312/c65c5e130751e49a41af128eff0348dd/plugin-authoring/types/claude-code.d.ts` (`ClientSurface`, `ClientKeyEvent`, `'ui.message'`).

**Interfaces:**
- Consumes: `speak status --json` com `scope` (Tarefa 4).
- Produces: props do `Client` `{ rows: { key: 'where'|'power'|'mode'|'size'|'voice', label: string, values: { value: string, label: string }[], value: string, own: boolean }[], focus: string, note: string }`; mensagem `post({ key, value })`. O módulo guarda `where` (`'all'`|`'session'`) e `note` em `$.state` (contrato em `types/index.d.ts`, nomeado no `plugin.json`), começando em `'all'` a cada abertura do `/speak`.

- [x] **Step 1: Testes que falham** em `hooks/register.test.tsx` (montar o painel `speak` na superfície `terminal`, agir por `ui.key` no `Client` e conferir o argv de `process.run`):
  - abre com "Mudar em" em Todas as sessões e o foco nela; `/speak mode` abre com o foco em Leitura;
  - baixo, direita na Voz → `speak off all` (com Todas) e rodapé com a frase de `said()`;
  - direita em "Mudar em" não roda nada; depois direita em Leitura → `speak mode <valor>` sem `all`;
  - linha com campo próprio (`scope.mode == 'session'`) mostra `· só nesta sessão`;
  - esquerda no primeiro valor vai ao último;
  - `speak` com código 1 → rodapé com a mensagem de erro e valor lido de volta do estado;
  - superfície sem `Client` ou `isPlaced` falso → resposta em texto com USAGE;
  - os testes de escrita completa (`/speak voice alex`, `status`, `stop`, `install`) continuam.
- [x] **Step 2:** `claude plugin test .` → FALHA.
- [x] **Step 3:** Implementar a partir do protótipo: `Client` desenha as linhas e trata cima/baixo/esquerda/direita; Enter não faz nada; o gancho `ui.message` roda a mudança (com `all` quando `where == 'all'`, exceto voz de leitura), relê o estado e devolve `{ props }`.
- [x] **Step 4:** `claude plugin test .` → todos passam; `claude plugin validate .` → `✔ Validation passed` (só avisos já conhecidos).
- [x] **Step 5:** Commit `feat: /speak abre menu de setas que fica aberto`.

### Task 6b: Linha do resumo só no modo resumo **(Ricardo, 29/10/2026)**

Na leitura inteira (`mode full`) a linha `🔊` é pulada pela voz e fica na tela sem uso; ela passa a ser escrita só no modo resumo.

**Files:**
- Modify: `rules/speak.md`, `bin/speak` (`rule()`), `hooks/speak-cut.py`
- Test: `tests/test_speak.py`

- [ ] **Step 1: Testes que falham:** `test_regra_sem_linha_no_full` (`speak rule` com o modo da sessão `full` diz para não escrever a linha; com `summary`, mantém o texto de hoje com o tamanho); `test_aviso_full` (com a voz ligada e modo `full`, o gancho de mensagem nova imprime a nota `speak: a leitura é da resposta inteira; não termine esta resposta com a linha 🔊.`; com `summary`, nenhuma nota; com a voz desligada, a nota de hoje).
- [ ] **Step 2:** Rodar → FALHA.
- [ ] **Step 3:** Implementar: marcador novo em `rules/speak.md` trocado por `rule()` conforme o modo; o gancho de mensagem nova lê o modo em vigor da sessão.
- [ ] **Step 4:** `python3 -m unittest discover -s tests` → OK.
- [ ] **Step 5:** Commit `feat: linha do resumo só no modo resumo`.

Também na Tarefa 2: a mudança única apaga a pasta `state/phone` que sobrou do modo celular retirado.

**Padrões de instalação (Ricardo, 29/10/2026):** voz ligada, modo `summary`, tamanho `medium`, voz `dora`. Hoje o padrão do modo é `'full'` (`bin/speak`, `mode()`); passa a ser `'summary'`, com teste (`test_padrao_summary`: sem escolha nenhuma gravada, `speak status --json` dá `mode == 'summary'`, `size == 'medium'`, `voice == 'dora'`, `on == true`). Quem já gravou `mode` no arquivo geral mantém a escolha. Versão 0.5.7.

### Task 6c: Fim de sessão corta a fala daquela sessão **(Ricardo, 29/10/2026)**

Hoje, ao sair de uma sessão (`exit`) no meio da leitura, a fala continua até o fim: não há gancho `SessionEnd`. Pela documentação do Claude Code, `SessionEnd` roda quando a sessão termina (motivos `clear`, `resume`, `logout`, `prompt_input_exit`, `other`), não bloqueia e os ganchos dele dividem um orçamento de 1,5 s.

**Files:**
- Create: `hooks/speak-end.py`
- Modify: `hooks/hooks.json`, `bin/speak` (um `stop` só da sessão, se a fila ainda não souber de quem é cada fala)
- Test: `tests/test_speak.py`

- [ ] **Step 1: Testes que falham:** `test_fim_corta_so_a_sessao` (duas falas na fila, uma de cada sessão, e a da sessão A tocando → o gancho de fim da sessão A corta a que toca e tira da fila só as de A; a de B continua na fila); `test_fim_sem_fala` (nada da sessão na fila → sai com 0 sem mexer em nada); `test_fim_rapido` (o gancho termina bem abaixo de 1,5 s e sai com 0 mesmo com erro).
- [ ] **Step 2:** Rodar → FALHA.
- [ ] **Step 3:** Implementar: o gancho lê `session_id` da entrada JSON e chama o corte só daquela sessão; registrar em `hooks/hooks.json` em `SessionEnd`, sem filtro de motivo. Conferir no código da fila como cada fala sabe a sessão de origem; se não souber, gravar a sessão no bilhete da fila.
- [ ] **Step 4:** `python3 -m unittest discover -s tests` → OK; `claude plugin validate .` → passa.
- [ ] **Step 5:** Commit `feat: fim de sessão corta a fala daquela sessão`. Versão 0.5.8.

### Task 7: Documentos, versão e testes no GitHub nos dois sistemas

**Files:**
- Create: `.github/workflows/tests.yml`
- Modify: `README.md`, `rules/speak.md`, `docs/proximos-passos.md`, `docs/superpowers/specs/2026-10-28-menu-design.md` (nota no topo), `.claude-plugin/plugin.json`, `tests/test_speak.py` (versão)

- [ ] **Step 1:** Fluxo `tests.yml`: em `push` e `pull_request`, matriz `ubuntu-latest` e `macos-latest`, Python 3.12, `python3 -m unittest discover -s tests`.
- [ ] **Step 2:** README: requisitos por sistema (Linux: tocador `pw-play`/`paplay`/`aplay`; Mac: `afplay`, já vem), "desinstalar o plugin apaga o motor, as escolhas e o estado, a menos que use `--keep-data`", o menu de setas e a marca `· só nesta sessão`, tira "Por enquanto, só Linux". `rules/speak.md`: `/speak` sozinho abre o menu de setas, que fica aberto até Esc. `proximos-passos.md`: Mac sai dos pedidos para depois; feito atualizado; comandos por ação recusados. Nota no desenho do menu antigo apontando para o novo. Versão 0.6.0.
- [ ] **Step 3:** `python3 -m unittest discover -s tests` → OK; `claude plugin test .` → todos passam; `claude plugin validate .` → passa.
- [ ] **Step 4:** Commit `docs: menu de setas, pasta de dados e Mac (0.6.0)`.

### Task 8: Verificação final

- [ ] **Step 1:** O controlador repete: `python3 -m unittest discover -s tests`, `claude plugin test .`, `claude plugin validate .`, e cola as saídas.
- [ ] **Step 2:** Revisão final do ramo (`harness-final-reviewer`) contra o desenho.
- [ ] **Step 3:** Envio (`git push origin main`), fluxo do GitHub verde nos dois sistemas (`gh run watch`).
- [ ] **Step 4:** Atualizar o plugin instalado aqui (`claude plugin marketplace update cc-speaker`, `claude plugin update speak@cc-speaker`) e pedir ao Ricardo: menu e alcance neste computador; instalação limpa no Ubuntu 24; desinstalação apaga a pasta; Mac pelo conhecido (com `speak check` se a sessão não for achada).
- [ ] **Step 5:** O plano e o desenho saem por `git rm` no commit de fechamento, com o que deve durar passado ao `docs/proximos-passos.md`.

## Decisões tomadas na execução

- Versão por tarefa (Ricardo, 29/10/2026): sem subir o número, a atualização não chega aos outros computadores. Cada tarefa aprovada sobe a versão de correção e é enviada na hora (0.5.2 = Tarefas 1 e 2; 0.5.3 = Tarefa 3; ...); o fechamento é 0.6.0 na Tarefa 7.
- Mac por último (Ricardo, 29/10/2026): o código do Mac entra na ordem do plano; o teste num Mac de verdade fica para o fim, depois de tudo.

- Task 3 (instalação automática): o gancho de começo funciona (testado com `uv` real, com PATH mínimo, no HEAD e no `635ecd3`; Ubuntu 26.04, Claude Code 2.1.312). As causas reais, que levam a rodar `speak install` à mão: (1) enquanto a instalação de fundo roda, `speak status` e `speak test` diziam "não instalado (rode: speak install)", ignorando a trava; (2) um `speak install` manual não esperava o que já rodava (só o gancho tomava `state/install.lock`) e os dois gravavam o mesmo `<arquivo>.part`, dando `[Errno 2] ... .part` e um `install.failed` falso, que depois impedia o gancho de tentar de novo. O registro do Ubuntu 24 segue pendente (o `speak check` agora mostra as três últimas linhas do `install.log` quando falta o motor). Desenho: a trava `fcntl.flock` em `state/install.lock` passou para dentro de `speak install` (`install_marked`), bloqueante, com a mensagem "outra instalação está em andamento; esperando ela terminar"; o gancho só sonda a trava (ocupada: 'installing'; livre: solta e inicia o filho, sem `pass_fds`); dois ganchos em corrida podem iniciar dois filhos, o segundo espera e acha tudo instalado. Download temporário por processo (`.part-<pid>`, removido na falha). `status` (texto e `--json`, campo novo `installing`) e `test` dizem "sendo instalado em segundo plano (registro em ...)". Versão 0.5.3.
- Task 4 (alcance de verdade): `clear_all_sessions(*fields)` substitui `set_all_sessions` (que foi removida); `speak on/off all` grava o geral, marca `ALL_MARK` e remove só `voice` das sessões; `mode`/`size` `all` removem o campo. O arquivo de sessão que fica vazio é mantido. `status` passou a mostrar o valor em vigor da sessão (antes mostrava o geral) em voz, modo e tamanho, com a marca `· só nesta sessão` quando o campo é próprio da sessão; o rótulo `modo:` foi mantido (o desenho citava `leitura:` só como exemplo do menu). `status --json` ganhou `scope` (`on`, `mode`, `size`). A limpeza única (`_drop_copied_fields`, no fim de `migrate()`) tira `mode`/`size` iguais ao geral das sessões e grava o marcador `state/scope` para não apagar exceções futuras; erro de escrita na pasta de estado é ignorado e tenta de novo na próxima chamada. Dois testes antigos (`test_mode_here_does_not_touch_other_sessions`, `test_mode_all_sets_every_session_and_the_general`) e `test_session_size_stays_in_the_session_and_all_sets_every_one` foram ajustados ao modelo novo (remover, não copiar). Versão 0.5.4.
- Task 5 (som e microfone no Mac): `lib/speak_os.py` ganhou `player()`, `streams()`, `recordings_now()` e `mic_busy()`; os três tocadores do Linux e o teste do `--raw` se mudaram para lá, e em `bin/speak` `player_command`, `current_recordings` e `recordings` só repassam a ela (os testes do Linux ficaram como estavam). `recordings_now()` no Mac devolve `{'input'}` / conjunto vazio / `None`, para a fila continuar usando `mic_busy(current_recordings())` sem mudar. No Mac, `play` usa `FilePlayer`: um WAV `state/.tmp-<pid>-<hex>.wav` por pedaço (o nome casa com a limpeza de órfãos `prune_tmp`), `afplay <wav>`, apaga ao fim; o corte pelo microfone mata o `afplay` e apaga o arquivo. CoreAudio fica numa classe pequena (`_CoreAudio`) carregada só por `_coreaudio()`, que devolve `None` fora do `darwin`; qualquer erro vira `None`. Constantes e layout de `AudioBufferList` escritos de memória, NÃO verificados num Mac. Mensagens do `uv` e do tocador ausente têm texto do Mac (gancho e `bin/speak`). Versão 0.5.5.
- Task 5, correção rodada 1 (microfone no Mac): `DeviceIsRunningSomewhere` vale para o dispositivo inteiro, então num fone ou monitor com entrada e saída o próprio `afplay` pareceria uma gravação e cortaria a fala. A conta do microfone ignora a saída padrão ('dOut') e a saída padrão do sistema ('sOut'). Limite conhecido: ditar no microfone do mesmo dispositivo em que a voz toca não corta a fala no Mac. Se não der para ler as saídas padrão, a resposta é `None` (não corta). Dispositivo que dá erro em 'slay' ou 'gone' é pulado. O CDLL e a classe `Address` ficam guardados no módulo. As mensagens de `uv` e tocador do Mac vêm de `speak_os.notice_uv()` e `speak_os.player_names()`; o gancho não pergunta o sistema.
- Task 5, correção rodada 2 (Mac toca pelo sounddevice): decisão do Ricardo, a forma mais prática e compatível. O Mac toca em fluxo pelo `sounddevice` (`sd.OutputStream` na taxa da síntese) e cai para o `afplay` (arquivo por pedaço, `FilePlayer`) em qualquer falha do caminho (importar, abrir o dispositivo, escrever no meio da fala), para o resto da mesma fala e a partir do pedaço que falhou, que o `afplay` toca de novo. `MacPlayer` guarda a escolha; o corte pelo microfone aborta e fecha o fluxo (ou mata o `afplay`) e, se a falha de escrita foi o próprio corte, nada mais toca. O fluxo é sempre fechado (`finally`). Nada mexe em volume nem em dispositivo padrão. `speak install` no Mac instala `sounddevice` num passo separado depois do `kokoro-onnx`; se falhar, imprime `voz: sounddevice não instalou; o Mac toca pelo afplay` e termina com 0; motor já instalado sem ele usa o `afplay` até um novo `speak install`. O Linux segue nativo (pw-play, paplay, aplay) porque o PortAudio, de que o `sounddevice` depende, não vem num Ubuntu novo.
- Task 5, correção rodada 3 (nada no Mac prende o áudio): a escrita e o `stop` do fluxo têm prazo (duração do pedaço mais `STREAM_SLACK`, 2 s), rodando numa thread daemon com `join(timeout)`; ao estourar o fluxo é abortado sem esperar (também em thread daemon, pois o `abort` e o `close` podem travar num dispositivo que sumiu) e o resto da fala segue pelo `afplay`. O `stop` final que estoura só encerra a fala. Se `start()` falhar, o fluxo criado é fechado antes de propagar. O `close` do fluxo é protegido por trava. Não há prazo para abrir o `OutputStream` (fica como limite conhecido).
- Task 6 (menu de setas): `hooks/menu.tsx` é o módulo de superfície do `Client` (recebe `{ rows, focus, note }` por props, guarda só a linha em foco, `post({ key, value })` a cada troca); `hooks/register.tsx` abre o painel `speak` com `$.ui.open({ id: 'speak', focus: true, closeOnEscape: true })`, desenha o `Client` no `ui.render` do `Pane` e roda a troca no `ui.message`, que devolve `{ props }`. O estado `where`, `note` e `focus` fica em `$.state` (contrato `types/index.d.ts`, nomeado no `plugin.json` em `types`); `where` volta a `all` e `note` a vazio a cada abertura. Decisões: (1) "sem `Client`" é decidido por `$.session.surfaces()` não conter `terminal` (a mesma tabela de elementos do `Client` é a do terminal) ou `isPlaced` falso; nos dois casos a resposta é o texto com USAGE. (2) A resposta do comando ao abrir o menu é `{}` (sem texto), pois o painel é a resposta. (3) `/speak mode all` (ação sem valor, com `all`) abre o menu como `/speak mode`: o alcance agora é a primeira linha, que sempre abre em Todas as sessões. (4) O gancho `ui.message` valida `key` e `value` contra as tabelas antes de rodar o speak, pois o dado vem do código do `Client`. (5) A voz de leitura aparece com o nome curto (Dora, Alex, Santa), sem "(feminina)". (6) Duas teclas na mesma moldura: o `Client` calcula o próximo valor sobre as props que tem, então a segunda só vale depois das props novas voltarem. (7) Enter ignorado. (8) README e `rules/speak.md` ajustados à frase do menu. Versão 0.5.6.
