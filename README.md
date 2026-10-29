# cc-speaker

Respostas do Claude Code lidas em voz alta, em português do Brasil, com um motor de voz que roda na sua máquina (Kokoro), sem rede e sem custo. É um plugin do Claude Code chamado `speak`; este repositório é também o catálogo de onde ele se instala. Por enquanto, só Linux.

## Requisitos

- Linux com `python3`.
- `uv` (https://docs.astral.sh/uv/), que instala o motor.
- Um tocador de áudio: `pw-play`, `paplay` ou `aplay`.
- Cerca de 350 MB livres para o motor e o modelo de voz.

## Instalação

1. No Claude Code: `/plugin marketplace add ricksouzaa/cc-speaker`
2. Depois: `/plugin install speak@cc-speaker`
3. Abra uma sessão nova.
4. O Claude vai oferecer a instalação do motor; responda que sim (ou rode `/speak:install`). Não precisa de sudo.

Se você ainda tem a voz antiga do ai-harness instalada, o plugin fica mudo até ela sair, para não falar em dobro.

## Comandos

Todos são só para você digitar. Com `all` no fim, valem para todas as sessões; sem ele, só para a sessão atual.

- `/speak:on [all]` e `/speak:off [all]`: ligam e desligam a voz.
- `/speak:mode full|summary [all]`: lê a resposta inteira (sem código, caminhos e links) ou só o resumo da linha 🔊.
- `/speak:size small|medium|large [all]`: tamanho do resumo falado: uma frase curta, duas a três frases (padrão) ou um parágrafo.
- `/speak:voice [dora|alex|santa]`: sem nome, lista as vozes em português; com nome, escolhe (dora é feminina; alex e santa são masculinas).
- `/speak:status`: mostra o estado atual (voz, modo, tamanho, motor).
- `/speak:stop`: corta a fala que está tocando e esvazia a fila.
- `/speak:install`: instala o motor.

Também dá para pedir em palavras ("fala só o resumo", "resumo maior", "troca para a voz do Alex"); o Claude roda o comando por você.

## Variáveis de ambiente

- `CLAUDE_SPEAK=0`: começa a sessão muda.
- `CLAUDE_SPEAK_MODE`, `CLAUDE_SPEAK_SIZE`, `CLAUDE_SPEAK_VOICE`: mandam mais que as escolhas gravadas.
- `CLAUDE_SPEAK_SPEED`: velocidade da fala (padrão 1.1).

## Pastas

O motor fica em `~/.local/share/claude-speak`, as escolhas em `~/.config/claude-speak` e o estado em `~/.local/state/claude-speak`. Desinstalar o plugin não apaga o motor.

## Testes

`python3 -m unittest discover -s tests`

O estado da mudança do ai-harness para este repositório está em `PASSAGEM.md`.

## Licença

MIT (veja `LICENSE`). O motor de voz não vem neste repositório: o modelo Kokoro (Apache 2.0) e as bibliotecas são baixados na sua máquina por `speak install`, cada um com a sua licença.
