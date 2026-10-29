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
4. Se o motor de voz ainda não estiver instalado, a primeira sessão o instala sozinha, em segundo plano (veja abaixo). Não precisa de sudo.

## O motor, instalado sozinho

O Claude Code não tem passo de instalação para plugins. Por isso, ao abrir uma sessão sem o motor, o plugin dispara a instalação em segundo plano (cerca de 350 MB, sem perguntar), e o Claude avisa você em uma frase. A voz começa sozinha quando termina. Detalhes:

- Só uma instalação roda por vez: outra sessão que abra nesse meio tempo não começa outra.
- O andamento fica em `~/.local/state/claude-speak/install.log`.
- Se faltar o `uv`, nada é instalado; o Claude diz como instalá-lo (https://docs.astral.sh/uv/).
- Se a instalação falhar, ela não tenta de novo sozinha: o Claude aponta o registro e você roda `/speak install` para tentar outra vez, em primeiro plano.
- `CLAUDE_SPEAK_AUTOINSTALL=0` desliga a instalação automática.

## O comando /speak

Um comando só, para você digitar. Sem nada depois, abre um painel com uma lista para cada ajuste, no estilo do `/model` (setas movem, Enter escolhe, Esc fecha): voz ligada ou desligada, leitura, tamanho do resumo, voz de leitura e para quais sessões vale. Cada escolha vale na hora e a lista mostra o valor novo. Ele responde na hora, sem gastar uma resposta do Claude, e funciona mesmo durante uma resposta (assim `/speak stop` corta a fala já).

Também dá para escrever a ação inteira e pular o painel. Com `all` no fim, vale para todas as sessões; sem ele, só para a sessão atual:

- `/speak on` e `/speak off`: ligam e desligam a voz.
- `/speak mode [full|summary]`: lê a resposta inteira (sem código, caminhos e links) ou só o resumo da linha 🔊. Sem a escolha, abre o painel só com essa lista.
- `/speak size [small|medium|large]`: tamanho do resumo falado: uma frase curta, duas a três frases (padrão) ou um parágrafo.
- `/speak voice [dora|alex|santa]`: sem nome, abre a lista com as vozes em português; com nome, escolhe (dora é feminina; alex e santa são masculinas). Vale para todas as sessões.
- `/speak status`: mostra o estado atual (voz, modo, tamanho, motor).
- `/speak stop`: corta a fala que está tocando e esvazia a fila.
- `/speak install`: instala o motor (ou tenta de novo), em primeiro plano; pode levar minutos.

Se o painel não puder abrir (por exemplo, numa execução sem tela), o comando responde com a forma escrita. Também dá para pedir em palavras ("fala só o resumo", "resumo maior", "troca para a voz do Alex"); o Claude roda o comando por você.

## Variáveis de ambiente

- `CLAUDE_SPEAK=0`: começa a sessão muda.
- `CLAUDE_SPEAK_MODE`, `CLAUDE_SPEAK_SIZE`, `CLAUDE_SPEAK_VOICE`: mandam mais que as escolhas gravadas.
- `CLAUDE_SPEAK_SPEED`: velocidade da fala (padrão 1.1).

## Pastas

O motor fica em `~/.local/share/claude-speak`, as escolhas em `~/.config/claude-speak` e o estado em `~/.local/state/claude-speak`. Desinstalar o plugin não apaga o motor.

## Testes

`python3 -m unittest discover -s tests` (motor e script) e `claude plugin test .` (o comando `/speak`).

Decisões e próximos passos: `docs/proximos-passos.md`.

## Licença

MIT (veja `LICENSE`). O motor de voz não vem neste repositório: o modelo Kokoro (Apache 2.0) e as bibliotecas são baixados na sua máquina por `speak install`, cada um com a sua licença.
