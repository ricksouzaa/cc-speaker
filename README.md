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

## Comandos

Todos são só para você digitar. Com `all` no fim, valem para todas as sessões; sem ele, só para a sessão atual.

- `/speak:on [all]` e `/speak:off [all]`: ligam e desligam a voz.
- `/speak:mode [full|summary] [all]`: sem argumento, abre um menu de setas (leitura, alcance e, no resumo, o tamanho); lê a resposta inteira (sem código, caminhos e links) ou só o resumo da linha 🔊.
- `/speak:size [small|medium|large] [all]`: sem argumento, abre um menu de setas; tamanho do resumo falado: uma frase curta, duas a três frases (padrão) ou um parágrafo.
- `/speak:phone [on|off] [all]`: sem argumento, abre um menu de setas. Com o celular ligado, o computador não toca nada: cada resposta vira um arquivo mp3 (respeita o modo e o tamanho do resumo) que o Claude envia ao seu celular pelo controle remoto, para você dar o play. Custa uma volta curta extra do Claude por resposta, e a resposta inteira pode levar alguns minutos para virar áudio. Só funciona num controle remoto que aceite envio de arquivo; os mp3 ficam em `~/.local/state/claude-speak/phone` e somem depois de um dia.
- `/speak:voice [dora|alex|santa]`: sem nome, abre um menu de setas com as vozes em português; com nome, escolhe (dora é feminina; alex e santa são masculinas).
- `/speak:status`: mostra o estado atual (voz, modo, tamanho, saída, motor).
- `/speak:stop`: corta a fala que está tocando e esvazia a fila.
- `/speak:install`: instala o motor.

Também dá para pedir em palavras ("fala só o resumo", "resumo maior", "troca para a voz do Alex"); o Claude roda o comando por você.

## Variáveis de ambiente

- `CLAUDE_SPEAK=0`: começa a sessão muda.
- `CLAUDE_SPEAK_MODE`, `CLAUDE_SPEAK_SIZE`, `CLAUDE_SPEAK_VOICE`, `CLAUDE_SPEAK_OUTPUT` (`phone` ou `speaker`): mandam mais que as escolhas gravadas.
- `CLAUDE_SPEAK_SPEED`: velocidade da fala (padrão 1.1).

## Pastas

O motor fica em `~/.local/share/claude-speak`, as escolhas em `~/.config/claude-speak` e o estado em `~/.local/state/claude-speak`. Desinstalar o plugin não apaga o motor.

## Testes

`python3 -m unittest discover -s tests`

Decisões e próximos passos: `docs/proximos-passos.md`.

## Licença

MIT (veja `LICENSE`). O motor de voz não vem neste repositório: o modelo Kokoro (Apache 2.0) e as bibliotecas são baixados na sua máquina por `speak install`, cada um com a sua licença.
