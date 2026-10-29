# Menu de setas, alcance de verdade, dados na pasta do plugin e Mac: desenho

Data: 29/10/2026. O Ricardo mandou seguir ("sim prossiga") e deixou o desenho comigo; o que ele pediu ou decidiu está marcado **(Ricardo)**, o resto **(minha decisão)**. Versão alvo: 0.6.0.

## Intenção

Quatro partes que mexem nos mesmos arquivos (`bin/speak`, `hooks/register.tsx`, ganchos, README), feitas juntas para o Ricardo testar de uma vez nos dois computadores (Linux) e com o conhecido do Mac:

1. o `/speak` sozinho abre um menu que fica aberto, desenhado pelo plugin, operado só pelas setas;
2. o alcance ("só esta sessão" ou "todas as sessões") deixa de ser um modo de gravar e vira informação guardada, que o menu e o status mostram;
3. motor, escolhas e estado vão para a pasta de dados do plugin, para que desinstalar remova tudo;
4. o plugin roda no macOS.

## Fora

Windows; filtro melhor do que se narra; uma voz por sessão; avisos falados; estilo Jarvis (continuam em `docs/proximos-passos.md`).

## 1. Menu de setas **(Ricardo)**

Protótipo testado pelo Ricardo em 29/10/2026 (`/menu-setas`): painel aberto por `$.ui.open({ id: 'speak', title: 'Voz', focus: true, closeOnEscape: true })` com um `Client` (módulo de superfície próprio, `hooks/menu.tsx`) que trata as teclas por `surface.onKey`. As setas chegaram sem clique, e o painel apareceu no lugar do campo de digitação, onde ele queria.

- Linhas, nesta ordem: **Mudar em** (Todas as sessões / Só nesta sessão), **Voz** (Ligada / Desligada), **Leitura** (Resposta inteira / Só o resumo), **Tamanho do resumo** (Pequeno / Médio / Grande), **Voz de leitura** (Dora / Alex / Santa).
- Cima e baixo mudam de linha; esquerda e direita trocam o valor da linha, em volta (do último ao primeiro); cada troca vale na hora (roda o `bin/speak`) e o menu redesenha com o estado lido de volta (`speak status --json`). Esc fecha. Enter não faz nada: não há submenu nesta etapa **(minha decisão: com cinco linhas e no máximo três valores, submenu e item Voltar não têm o que guardar)**.
- Uma linha de rodapé: a frase do que passou a valer (a de `said()`) ou o erro do `speak`; sem nada, a ajuda "↑↓ ajuste · ←→ valor · Esc fecha".
- Fluxo entre o módulo de superfície e o de ganchos: o `Client` recebe o estado por `props` e manda cada troca por `post({ setting, value })`; o gancho `ui.message` roda a mudança, relê o estado e devolve `{ props }` novas. O `Client` não guarda valores próprios além da linha em foco.
- `/speak <ação>` sem valor (`/speak mode`) abre o mesmo menu com o foco naquela linha. Escrita completa, `status`, `stop`, `install`: como hoje, sem menu.
- Onde não há `Client` (vscode, mobile) ou o painel não abre (`isPlaced` falso, execução `-p`): resposta em texto com a forma escrita (USAGE), como hoje.
- A caixa nativa (`$.ui.ask`, versão 0.5.0) sai.

## 2. Alcance de verdade **(defeito relatado pelo Ricardo; modelo meu)**

Hoje "todas as sessões" grava o arquivo geral **e** copia o valor para dentro de cada arquivo de sessão (`set_all_sessions`), e o painel/caixa não guardam o alcance. Resultado que o Ricardo viu: ao reabrir, o menu volta a "Só esta sessão", e o status não diz nada do alcance.

Modelo novo:

- O arquivo de uma sessão guarda só o que **difere** do geral (campos `voice`, `mode`, `size`). Campo ausente = segue o geral.
- `speak <ajuste> <valor> all` grava o geral e **remove** aquele campo de todos os arquivos de sessão (não copia). Para on/off, continua marcando `ALL_MARK` (vence a semente do `CLAUDE_SPEAK=0`).
- `speak <ajuste> <valor>` dentro de uma sessão grava o campo só nela, como hoje.
- `speak status` mostra, em cada ajuste, o valor em vigor e de onde vem: sem marca quando é o geral e `· só nesta sessão` quando é exceção; a voz de leitura é sempre geral. `status --json` ganha `scope: { on, mode, size }` com `session` ou `all`.
- No menu **(acertado com o Ricardo em 29/10/2026, com o esboço abaixo)**: a primeira linha se chama **Mudar em** e diz só onde as próximas trocas são gravadas; não é um ajuste e não é guardada: abre sempre em "Todas as sessões". Trocá-la não roda nada. Cada ajuste que é exceção desta sessão (campo próprio no arquivo da sessão) leva a marca `· só nesta sessão` ao lado do valor; sem marca, é o geral. Trocar um valor com "Todas as sessões" grava o geral e apaga aquele campo de todas as sessões abertas (as exceções das outras sessões também, como hoje); com "Só nesta sessão", grava a exceção aqui.

  ```
    Mudar em          ‹ Todas as sessões ›
  ❯ Voz               ‹ Ligada ›
    Leitura           ‹ Só o resumo ›    · só nesta sessão
    Tamanho do resumo ‹ Médio ›
    Voz de leitura    ‹ Dora ›
  ```

- O status usa a mesma marca: `leitura: só o resumo · só nesta sessão`.
- Neste repositório o `.claude/settings.local.json` põe `CLAUDE_SPEAK=0`, que semeia `voice: muted` na sessão; a linha Voz mostrará a marca `· só nesta sessão` aqui, o que é verdade. Sem mudança nessa semente.

## 3. Dados na pasta do plugin **(Ricardo: a desinstalação remove tudo; caminho meu)**

O Claude Code não avisa o plugin da desinstalação, mas `claude plugin uninstall` apaga a pasta de dados do plugin (`~/.claude/plugins/data/speak-cc-speaker/`) a menos que se peça `--keep-data`. Então:

- Uma raiz só, `ROOT`: `$CLAUDE_PLUGIN_DATA` quando definida; senão `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/data/speak-cc-speaker` (o terminal do modelo não recebe a variável; conferido em 29/10/2026). Dentro: `engine/` (o antigo DATA), `config/` (CONF), `state/` (STATE). Vale igual no Linux e no Mac; as variáveis XDG deixam de valer.
- Mudança única: se a raiz nova não tem `engine/` e existem as pastas antigas (`~/.local/share/claude-speak` etc., com XDG), mover cada uma (`os.rename`, ou cópia e remoção entre discos), uma vez, como o `migrate()` atual faz com `claude-voz`. O motor não é baixado de novo.
- O ambiente virtual do motor guarda caminhos absolutos; depois de mover, `speak` confere se o python do ambiente roda e, se não, reconstrói só o ambiente (`uv`), sem baixar o modelo de novo **(o implementador confere o que o `uv venv` grava e escolhe o mais simples que funcione)**.
- README: "desinstalar o plugin apaga o motor, as escolhas e o estado (a menos que use `--keep-data`)".

## 4. Mac **(Ricardo: Linux e Mac, peça trocável por sistema)**

Uma peça por sistema dentro de `bin/` (por exemplo `bin/speak_os.py`, importada por `bin/speak` e pelos ganchos), com a mesma interface no Linux e no Mac; o resto do código não pergunta o sistema. O que entra nela:

| Função | Linux (hoje) | Mac |
| --- | --- | --- |
| achar a sessão: ancestral chamado `claude` e a chave `<pid>-<início>` | `/proc/<pid>/comm`, `/proc/<pid>/stat` | `ps -o ppid=,comm= -p <pid>` e o início por `ps -o lstart=` (ou `sysctl kern.proc` por ctypes) |
| saber se um processo existe e quando começou | `/proc`, `/proc/stat` btime | `os.kill(pid, 0)` e `ps` |
| linha de comando de um processo (achar a fala em curso) | `/proc/<pid>/cmdline` | `ps -o command= -p <pid>` |
| tocar o som | `pw-play --raw` (≥ 1.1), `paplay`, `aplay`, lendo da entrada | `afplay` não lê da entrada: gravar um WAV temporário em `state/` e tocar, apagando depois |
| microfone gravando | `pw-dump` | CoreAudio por ctypes: `kAudioDevicePropertyDeviceIsRunningSomewhere` em cada dispositivo de entrada, sem dependência nova |
| travas | `fcntl.flock` | o mesmo (existe no Mac) |
| parar a fala | `os.killpg` / `os.kill` | o mesmo |

- `speak install` no Mac: o mesmo `uv` e as mesmas bibliotecas (kokoro-onnx, onnxruntime, soundfile, espeakng-loader têm pacotes para Mac). Aviso de tocador ausente e de `uv` ausente com o texto do Mac.
- README: requisitos por sistema e "testado no Linux; Mac testado por um conhecido".
- Testes automáticos: cada função da peça com testes nos dois sistemas por simulação (saídas de `ps`, de `pw-dump`, ctypes trocado por um falso); um fluxo do GitHub Actions em `macos-latest` e `ubuntu-latest` rodando `python3 -m unittest discover -s tests` **(minha decisão; som e microfone de verdade, só com o testador)**.

## Respostas à revisão do construtor **(minhas decisões, 29/10/2026)**

- **Sessão no Mac:** o ancestral cujo nome base do executável (`os.path.basename` do `ps -o comm=`) é `claude`; se nenhum, o primeiro cujo `ps -o command=` tenha um argumento de nome base `claude` (instalação por node). `speak check` passa a imprimir a cadeia de ancestrais (pid, nome) para o testador do Mac mandar quando não achar. Risco aceito: só o testador confirma.
- **Raiz de dados em qualquer instalação:** a ordem é `CLAUDE_PLUGIN_DATA`; depois a pasta derivada do lugar do script (`.../plugins/cache/<catálogo>/<plugin>/<versão>/bin` → `.../plugins/data/<plugin>-<catálogo>`); por último `speak-cc-speaker`. Além disso, o gancho de começo (que recebe `CLAUDE_PLUGIN_DATA`) escreve `export CLAUDE_PLUGIN_DATA=...` em `$CLAUDE_ENV_FILE`, para o terminal do modelo herdar a mesma raiz; o módulo passa a mesma variável em `$.process.run` (`env`) quando ele a conhece **(o implementador confere nos tipos de onde o módulo lê a pasta de dados)**.
- **Uma regra só para a raiz e o sistema:** os ganchos Python importam de `bin/` (inserem a pasta `bin/` do plugin no `sys.path`, que `-I` não põe); nada de cópia da regra no `speak-start.py`.
- **`all` e a semente:** só on/off marcam `ALL_MARK` (a semente só mexe na voz). Um arquivo de sessão que fica vazio é mantido (vazio = segue o geral em tudo; ele já existe, então a semente não volta para quem marcou `all` depois de abrir, e para quem não marcou continua valendo a regra de hoje).
- **Arquivos de sessão antigos com valores copiados:** a mudança única remove de cada arquivo de sessão os campos `mode` e `size` iguais ao geral (o `voice` fica, porque pode ser a semente).

## Fora, por decisão do Ricardo

Um comando por ação (`/speak-on` e outros), pedido pela sessão do smart-platform: recusado pelo Ricardo em 29/10/2026; `/speak on` e os demais já bastam.

## Regra e documentos

- `rules/speak.md`: `/speak` sozinho abre o menu de setas; o status mostra de onde vem cada valor.
- README, `docs/proximos-passos.md` (Mac sai dos pedidos para depois; feito atualizado), nota no topo de `docs/superpowers/specs/2026-10-28-menu-design.md` apontando para este.

## Verificação

- `python3 -m unittest discover -s tests` passa, com testes novos: alcance (`all` remove os campos das sessões; status e `--json` com a origem; semente do `CLAUDE_SPEAK=0`), mudança de pastas (antigas movidas uma vez, nova vence, motor não rebaixado), raiz por variável e sem ela, peça por sistema nos dois sistemas.
- `claude plugin test .` passa, com testes do menu: abrir, setas (linha e valor, em volta), troca roda o argv certo, "Mudar em" abre em todas e não roda nada; marca de exceção nas linhas certas, `/speak mode` abre na linha certa, sem `Client` responde texto.
- `claude plugin validate .` sem erros.
- Fluxo do GitHub nos dois sistemas verde.
- Com o Ricardo: menu e alcance neste computador; instalação limpa no Ubuntu 24 (sem `speak install` à mão); desinstalação apaga a pasta; Mac pelo conhecido.
