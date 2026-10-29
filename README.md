# cc-speaker

Um plugin do Claude Code, chamado `speak`, que lê as respostas em voz alta em português do Brasil. A voz é gerada na sua máquina pelo Kokoro: sem rede, sem conta e sem custo. Este repositório é também o catálogo de onde o plugin se instala.

- **Lê só o resumo, ou a resposta inteira.** Por padrão, o Claude termina cada resposta com uma linha 🔊, um resumo feito para ser ouvido, e só ela é lida. No modo da resposta inteira, a voz lê o texto e pula código, caminhos e links.
- **Uma fala de cada vez.** Com várias sessões abertas, as falas entram numa fila e uma mensagem nova não corta a que está tocando.
- **Respeita o microfone.** Enquanto você dita ou está numa reunião, a voz espera; se começar uma gravação no meio da fala, ela para. Dá para mudar isso quando você quer que a reunião ouça.
- **Se ajusta sem gastar resposta.** O comando `/speak` abre um painel com as opções, ou você pede em palavras ("fala só o resumo", "troca para a voz do Alex").

Funciona no Linux e no macOS, mas o macOS **nunca foi testado num Mac de verdade**: tem suporte no código e passa nos testes automáticos do GitHub, e só. Se você usar no Mac e tiver problema, [abra uma issue](https://github.com/ricksouzaa/cc-speaker/issues). O Windows fica de fora por enquanto.

## Requisitos

| | Linux | macOS |
|---|---|---|
| Python | `python3` | `python3` (o do sistema serve) |
| Instalador do motor | [`uv`](https://docs.astral.sh/uv/) | [`uv`](https://docs.astral.sh/uv/) |
| Tocador de áudio | `pw-play` (PipeWire 1.1 ou mais novo), `paplay` ou `aplay` | já vem no sistema |
| Espaço | cerca de 350 MB | cerca de 350 MB |
| Situação | testado no Linux | só nos testes automáticos do GitHub; nunca num Mac de verdade |

No Ubuntu 24.04 o `pw-play` é mais velho, e o speak usa o `paplay` ou o `aplay` no lugar. O código do Mac tem suporte e passa nos testes automáticos do GitHub, mas nunca foi testado num Mac de verdade. Quem usar no Mac e tiver problema pode abrir uma issue em https://github.com/ricksouzaa/cc-speaker/issues.

## Instalação

No Claude Code:

```
/plugin marketplace add ricksouzaa/cc-speaker
/plugin install speak@cc-speaker
```

Pronto. A voz se instala sozinha, em segundo plano e sem sudo: ali mesmo, logo depois do `/plugin install`, ou na próxima sessão que você abrir. São cerca de 350 MB, entre o modelo de voz e as bibliotecas, e leva alguns minutos. Enquanto isso:

- aparece uma linha na conversa dizendo que a voz está sendo instalada;
- embaixo do campo de texto, o progresso: `🔊 Instalando a voz: 78% (253 de 326 MB)`;
- no fim, o aviso "Voz pronta", e a voz começa a falar.

O `/speak status` e o rodapé do menu também mostram o andamento. Só uma instalação roda por vez, mesmo com várias sessões abertas.

## Uso

### O painel

Digite `/speak` sozinho. Abre um painel com uma lista por linha, já com o teclado nele, no terminal e no VS Code. Tab muda de linha, Enter escolhe o valor, e Esc ou o botão Fechar fecham. Cada escolha vale na hora.

| Linha | O que escolhe |
|---|---|
| Mudar em | onde as próximas trocas valem: todas as sessões (padrão ao abrir) ou só nesta |
| Voz | ligada (padrão) ou desligada |
| Leitura | só o resumo (padrão) ou a resposta inteira |
| Tamanho do resumo | pequeno (uma frase), médio (padrão, duas ou três frases) ou grande (um parágrafo); a linha só aparece com a leitura em "só o resumo" (o `/speak size` escrito vale em qualquer modo) |
| Voz de leitura | Dora (padrão, feminina), Alice (feminina, a Dora mais suave), Alex ou Santa (masculinas); vale sempre para todas as sessões |
| Com o microfone em uso | Espera (padrão), Toca ou Toca nesta reunião (veja [Microfone](#microfone)) |
| Ouvir de novo | dois botões, Resumo e Resposta inteira: tocam na hora a última fala desta sessão; a linha não guarda valor |

Abaixo da última resposta (só depois que o turno termina) aparecem os mesmos dois botões, `[ ▶ Resumo ]` e `[ ▶ Resposta inteira ]`; sem a linha 🔊 só o segundo. Somem quando começa o turno seguinte. Clicar só funciona no terminal em tela cheia.

Enquanto a fala desta sessão toca, o botão do modo dela (Resumo ou Resposta inteira, tanto sob a resposta quanto na linha do painel) vira `[ ⏸ Pausar ]`; pausada, vira `[ ▶ Continuar ]`; ao acabar, volta ao normal. A linha de status sob o campo de texto, em todas as sessões, diz quem fala: "🔊 falando agora" na sessão dona da fala, "🔊 falando: <pasta do projeto>" nas outras, e "⏸ fala pausada" na dona, quando pausada. Enquanto a instalação do motor usa essa linha, ela vence o aviso.

A pausa congela o tocador e a síntese (o sinal SIGSTOP no grupo de processos da fala) e continua com SIGCONT. Foi testada no Linux com o `pw-play`; com `paplay`, `aplay` e no Mac (`afplay`) o código é o mesmo, mas não foi testado num Mac de verdade.

Uma linha que só vale nesta sessão leva a marca "· só nesta sessão". O painel responde sem gastar uma resposta do Claude e funciona até no meio de uma resposta.

### Comandos escritos

Para pular o painel, escreva a ação. Com `all` no fim, vale para todas as sessões; sem ele, só para esta.

| Comando | O que faz |
|---|---|
| `/speak on` · `/speak off` | liga ou desliga a voz (padrão: `on`) |
| `/speak mode summary` · `full` | lê só o resumo ou a resposta inteira (padrão: `summary`) |
| `/speak size small` · `medium` · `large` | tamanho do resumo (padrão: `medium`) |
| `/speak voice dora` · `alice` · `alex` · `santa` | troca a voz, sempre em todas as sessões (padrão: `dora`) |
| `/speak mic wait` · `play` · `auto` | o que fazer com o microfone em uso (padrão: `wait`) |
| `/speak again` · `again summary` · `again full` | ouve de novo a última fala desta sessão, mesmo com a voz desligada: do jeito em que tocou, só o resumo ou a resposta inteira |
| `/speak pause` | congela a fala que está tocando, de qualquer sessão, no ponto exato; a vez passa para a próxima da fila, e a pausada espera você pedir |
| `/speak resume` | continua a fala pausada desta sessão (ou a pausada mais recente); se outra fala toca, a pausada vai para a frente da fila e continua quando essa acabar |
| `/speak status` | mostra a versão do plugin e como está tudo: voz, leitura, tamanho, microfone e motor |
| `/speak stop` | corta a fala que está tocando, esvazia a fila e encerra as falas pausadas |
| `/speak install` | instala o motor de novo, em primeiro plano |
| `/speak update` | atualiza o plugin para a versão mais nova do catálogo; vale depois de `/reload-plugins` ou numa sessão nova |

Sem o valor (`/speak mode`, `/speak voice`…), o painel abre já na linha certa. Sair de uma sessão corta as falas dela (tocando, na fila ou pausadas), e as de outras sessões continuam.

### Em palavras

Também dá para pedir ao Claude, escrevendo ou ditando: "fala só o resumo", "resumo maior", "troca para a voz do Alex", "para de falar", "silêncio em todas as sessões". Para pausar: "pausa"; para seguir: "continua" ou "continuar de onde parou". Para ouvir de novo: "repete", "não entendi, repete", "lê a resposta inteira", "lê só o resumo de novo". Ele roda o comando e confirma o que passou a valer.

## Microfone

O microfone é detectado pelo `pw-dump` no Linux e pelo CoreAudio no Mac. Há três jeitos de lidar com ele:

| Escolha | O que acontece com o microfone gravando |
|---|---|
| `wait`, Espera (padrão) | a fala espera na fila até o microfone ficar livre; se uma gravação começa durante a fala, ela é cortada |
| `play`, Toca | a fala toca mesmo com a reunião gravando, até você mudar; no Linux, o ditado do Claude Code (segurar a barra de espaço) continua segurando e cortando a fala |
| `auto`, Toca nesta reunião | como `play` (o ditado do Claude Code continua cortando, no Linux), e quando a reunião acaba (o microfone fica livre) volta sozinho para `wait`; ditar sozinho não conta como reunião |

O `play` e o `auto` servem para quando você quer que as pessoas da reunião ouçam: sem fone de ouvido, o microfone capta a voz. O `auto` percebe o fim da reunião na próxima fala ou na próxima mensagem; se for escolhido com o microfone livre, vale para a próxima reunião.

No Linux, o `pw-dump` mostra o nome do programa que grava, e o ditado do Claude Code aparece como `PipeWire ALSA [<nome do processo>]`, com o nome de um processo `claude` seu: é assim que ele é reconhecido e separado da reunião. No Mac, o CoreAudio não diz quem grava: em `play` e `auto` nada segura nem corta a fala, nem o ditado.

No Mac, se a voz nunca tocar porque o `speak` acha que o microfone está sempre em uso (a escuta da Siri, por exemplo, pode manter a entrada embutida ligada), rode `speak check`: a linha `microfone:` mostra o que ele enxerga. Se disser "em uso" sem ninguém gravando, use `/speak mic play`, que fala mesmo assim.

## Quando a voz não instala

- **Falta o `uv`:** nada é instalado, e o Claude diz como instalá-lo. Embaixo do campo fica o aviso "Voz não instalada". Depois de instalar o `uv`, rode `/speak install`.
- **A instalação falhou:** ela não tenta de novo sozinha, para não baixar tudo em toda sessão. O aviso fica embaixo do campo; rode `/speak install` para tentar de novo, vendo cada etapa.
- **O registro** de cada instalação fica em `state/install.log`, na [pasta de dados](#pastas). Cada etapa aparece ali na hora em que começa.

Enquanto o motor falta, o Claude não escreve a linha 🔊. A instalação automática se desliga com `CLAUDE_SPEAK_AUTOINSTALL=0`.

Quando o plugin é ativado com uma sessão já aberta, a instalação começa ali mesmo, mas as regras da voz só chegam ao Claude na próxima sessão.

## Ajustes avançados

### Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `CLAUDE_SPEAK=0` | a sessão começa muda |
| `CLAUDE_SPEAK_MODE`, `CLAUDE_SPEAK_SIZE`, `CLAUDE_SPEAK_MIC`, `CLAUDE_SPEAK_VOICE` | valem mais que as escolhas gravadas |
| `CLAUDE_SPEAK_SPEED` | velocidade da fala (padrão: 1.1) |
| `CLAUDE_SPEAK_AUTOINSTALL=0` | desliga a instalação automática do motor |

### Pastas

Tudo fica na pasta de dados do plugin, `~/.claude/plugins/data/speak-cc-speaker` (ou onde `CLAUDE_SPEAK_DATA` mandar): o motor em `engine/`, as escolhas em `config/` e o estado em `state/`.

Desinstalar o plugin apaga essa pasta inteira, a menos que você use `--keep-data`. Quem usava uma versão antiga, com as pastas `~/.local/share/claude-speak`, `~/.config/claude-speak` e `~/.local/state/claude-speak`, as vê movidas para lá na primeira vez, sem baixar o motor de novo.

## Desenvolvimento

- Testes do motor e do script: `python3 -m unittest discover -s tests`
- Testes do comando `/speak`: `claude plugin test .`
- Instalação numa máquina nova, num contêiner Ubuntu: `bash tests/docker/instalacao-limpa.sh auto`, ou `visual` para ver a tela (veja [`tests/docker/README.md`](tests/docker/README.md))
- Os testes rodam no GitHub no Ubuntu e no macOS a cada envio.

Decisões e próximos passos: [`docs/proximos-passos.md`](docs/proximos-passos.md).

## Licença

MIT (veja [`LICENSE`](LICENSE)). O motor de voz não vem neste repositório: o modelo Kokoro (Apache 2.0) e as bibliotecas são baixados na sua máquina pelo `speak install`, cada um com a sua licença.
