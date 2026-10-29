# Plugin `speak` (cc-speaker): desenho da primeira etapa

Data: 28/10/2026. O Ricardo pediu que eu tomasse as decisões e seguisse com a construção sem ele (ordem direta, em modo remoto); ele revisa ao voltar. O que ele decidiu está marcado **(Ricardo)**; o resto é **(minha decisão)**.

## Intenção

Transformar a voz do ai-harness num plugin do Claude Code que funciona como a de hoje, no Linux, e que se instala a partir deste repositório, que é também o catálogo. Junto, entram já duas evoluções **(Ricardo)**: escolher a voz entre as vozes em português do motor, e o tamanho do resumo falado (pequeno, médio, grande).

## Fora desta etapa

Mac e a peça trocável por sistema, filtro melhor do que se narra (códigos de commit, HEAD, ramos), uma voz por sessão, avisos falados durante o trabalho, modo remoto, estilo Jarvis, licença.

## Nomes

- Repositório e catálogo: `cc-speaker` **(Ricardo, repositório; minha decisão, catálogo)**.
- Plugin: `speak` **(proposta minha, não contestada)**. Instalação: `speak@cc-speaker`.
- Um comando de barra por ação **(Ricardo gostou da ideia)**: `/speak:on`, `/speak:off`, `/speak:mode`, `/speak:size`, `/speak:voice`, `/speak:status`, `/speak:stop`, `/speak:install`. Todos com `disable-model-invocation: true`; cada um roda `speak <ação> $ARGUMENTS` pelo Bash e confirma em uma frase.

## Estrutura

```
.claude-plugin/plugin.json        name speak, version 0.1.0, descrição em português, autor, repositório
.claude-plugin/marketplace.json   name cc-speaker, owner, plugins: [{name: speak, source: "./"}]
bin/speak                         o comando (o Claude Code põe bin/ no PATH do Bash do modelo)
hooks/hooks.json                  SessionStart (startup|resume|clear|compact), UserPromptSubmit, Stop
hooks/speak-start.py              novo: injeta a regra e o aviso de motor ausente
hooks/speak-cut.py                o speak-cut.sh passado a Python (decisão do Ricardo para o Mac; feito já)
hooks/speak-stop.py               o de hoje
rules/speak.md                    texto da regra, lido por `speak rule` (não é mais arquivo de regras do usuário)
skills/<ação>/SKILL.md            um por comando de barra; skills/speak sai
```

Os ganchos chamam o `speak` do próprio plugin, pelo caminho relativo ao arquivo do gancho (`../bin/speak`), nunca pelo PATH: a documentação não garante `bin/` no PATH dos ganchos, e durante a troca o `~/.local/bin/speak` antigo ganharia. Comandos nos `hooks.json` com `${CLAUDE_PLUGIN_ROOT}` e `python3 -I`, sempre terminando com saída 0.

## Pastas **(minha decisão)**

Motor, configuração e estado continuam em `~/.local/share/claude-speak`, `~/.config/claude-speak`, `~/.local/state/claude-speak` (com XDG). Não em `${CLAUDE_PLUGIN_DATA}`: a troca aproveita o motor já baixado e as escolhas de hoje, e desinstalar o plugin não apaga o motor.

## Troca sem buraco **(minha decisão, para a ordem do Ricardo)**

Enquanto a voz do ai-harness estiver instalada, os três ganchos do plugin não fazem nada: assim o plugin pode ser instalado e ligado já, sem falar em dobro nem injetar a regra duas vezes. Sinal: existe `~/.claude/hooks/speak-stop.py` ou `~/.claude/hooks/speak-cut.sh` (os ganchos globais que o ai-harness liga). Variável `CLAUDE_SPEAK_PLUGIN_FORCE=1` ignora o sinal (testes). Quando a sessão do ai-harness tira de lá o comando, os ganchos, a regra e o `/speak`, o plugin assume na sessão seguinte, sem passo extra. Essa guarda é temporária: sai numa versão seguinte, depois da troca.

A guarda foi retirada na versão 0.1.2, depois da troca.

## Regra no começo da sessão

`hooks/speak-start.py` imprime a saída de `speak rule` (texto puro no stdout vai ao contexto). Se o motor não estiver pronto, acrescenta: o motor não está instalado; na primeira resposta, ofereça ao humano instalar (`speak install`, cerca de 350 MB, sem sudo, precisa do uv); não instale sem o sim. Se não houver tocador (pw-play, paplay, aplay), diz isso no lugar.

`speak rule` lê `rules/speak.md` (ao lado de `bin/`, pelo caminho real do script) e troca o marcador `{size}` pela descrição do tamanho em vigor nesta sessão. Texto da regra: o de hoje, com estas mudanças:
- a linha 🔊 tem o tamanho do resumo em vigor (marcador);
- pedidos em palavras para resumo maior ou menor → `speak size <tamanho>`; para trocar a voz → `speak voice <nome>` (sem nome, lista);
- depois de rodar `speak size`, vale o tamanho novo dali em diante (como já vale para `speak off`);
- os comandos de barra são `/speak:on`, `/speak:off`, `/speak:mode`, `/speak:size`, `/speak:voice`, `/speak:status`, `/speak:stop`, `/speak:install`.

## Tamanho do resumo **(Ricardo pediu; descrições minhas)**

`speak size small|medium|large [all]`, no mesmo padrão de `speak mode`: na sessão (campo `size` do arquivo da sessão) ou, com `all` ou fora de sessão, no arquivo geral `~/.config/claude-speak/size` e em todas as sessões. Padrão `medium` (hoje sai sucinto demais). Variável `CLAUDE_SPEAK_SIZE` ganha de tudo. Descrição injetada na regra:
- small: uma frase curta;
- medium: duas a três frases: o que foi feito, o resultado e o que o humano decide;
- large: um parágrafo falado de quatro a seis frases: o que foi feito, o que se encontrou, o resultado e o que o humano decide.

Limite de caracteres lidos no modo resumo por tamanho: 300, 600, 1200 (o modo completo fica em 6000).

## Voz **(Ricardo pediu; nomes curtos meus)**

Vozes em português do motor: `pf_dora` (feminina, padrão de hoje), `pm_alex` e `pm_santa` (masculinas). `speak voice` sem argumento lista as três, com o nome curto (dora, alex, santa), o tipo e a atual marcada. `speak voice <nome>` aceita o curto ou o completo e grava em `~/.config/claude-speak/voice` (geral; uma voz por sessão é outra etapa). Nome desconhecido: recusa, código 2. Ordem: `CLAUDE_SPEAK_VOICE`, depois o arquivo, depois `pf_dora`. `speak status` mostra voz, velocidade e tamanho.

## Gerador de instalação sem plugin **(minha decisão)**

`prompts/` e `tests/test_speak_prompt.py` saem: com o plugin, a instalação é uma só, e manter o texto gerado em dia dobra o trabalho a cada mudança. Fica no histórico do git.

## Instalação para quem usa (README)

Requisitos: Linux, python3, uv, um tocador (pw-play, paplay ou aplay). Passos: `/plugin marketplace add ricksouzaa/cc-speaker`, `/plugin install speak@cc-speaker`, abrir sessão nova, aceitar a instalação do motor que o Claude oferece. Comandos, variáveis e pastas.

## Verificação

- `python3 -m unittest discover -s tests` passa, com testes novos: tamanho (sessão, geral, variável, recusa, limite), voz (lista, nome curto e completo, recusa, ordem), `speak rule` (marcador trocado por tamanho), gancho de começo (regra impressa, aviso sem motor, mudo com voz antiga instalada, forçado pela variável), gancho de mensagem nova em Python (mesmo comportamento do de shell), gancho de fim mudo com voz antiga, `hooks.json` e manifestos válidos e apontando para arquivos que existem, cada comando de barra só para o humano.
- `claude plugin validate .` sem erros.
- Instalado do catálogo local com escopo de usuário; `claude plugin list` mostra `speak@cc-speaker` ligado.
- Fala de verdade: só depois da troca, com o Ricardo (ele pediu silêncio no computador enquanto está fora).
