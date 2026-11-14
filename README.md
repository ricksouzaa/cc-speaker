# cc-speaker

[![Versão](https://img.shields.io/github/v/release/ricksouzaa/cc-speaker?label=vers%C3%A3o)](https://github.com/ricksouzaa/cc-speaker/releases)
[![Testes](https://img.shields.io/github/actions/workflow/status/ricksouzaa/cc-speaker/tests.yml?branch=main&label=testes)](https://github.com/ricksouzaa/cc-speaker/actions/workflows/tests.yml)
[![Licença: MIT](https://img.shields.io/github/license/ricksouzaa/cc-speaker?label=licen%C3%A7a)](LICENSE)

Um plugin do Claude Code, chamado `speak`, que lê as respostas em voz alta em português do Brasil. A voz é gerada na sua máquina pelo [Pocket TTS](https://github.com/kyutai-labs/pocket-tts), da Kyutai: sem rede, sem conta e sem custo. Este repositório é também o catálogo de onde o plugin se instala.

- **Lê só o resumo, ou a resposta inteira.** Por padrão, o Claude termina cada resposta com uma linha 🔊, um resumo feito para ser ouvido, e só ela é lida. No modo da resposta inteira, a voz lê o texto e pula código, caminhos e links.
- **Uma fala de cada vez.** Com várias sessões abertas, as falas entram numa fila e uma mensagem nova não corta a que está tocando.
- **Respeita o microfone.** Enquanto você dita ou está numa reunião, a voz espera; se começar uma gravação no meio da fala, ela para. Dá para mudar isso quando você quer que a reunião ouça.
- **Se ajusta sem gastar resposta.** O comando `/speak` abre um painel com as opções, ou você pede em palavras ("fala só o resumo", "troca para a voz do Rafael").

Funciona no Linux e no macOS, mas o macOS **nunca foi testado num Mac de verdade**: tem suporte no código e passa nos testes automáticos do GitHub, e só. Se você usar no Mac e tiver problema, [abra uma issue](https://github.com/ricksouzaa/cc-speaker/issues). O Windows fica de fora por enquanto.

## Requisitos

| | Linux | macOS |
|---|---|---|
| Sistema | Ubuntu 22.04, Debian 12 ou mais novo (glibc 2.34), em x86_64 ou ARM de 64 bits | Intel ou Apple Silicon |
| Python | `python3` | `python3` (o do sistema serve) |
| Instalador do motor | [`uv`](https://docs.astral.sh/uv/) | [`uv`](https://docs.astral.sh/uv/) |
| Tocador de áudio | `pw-play` (PipeWire 1.1 ou mais novo), `paplay` ou `aplay` | já vem no sistema |
| Espaço | cerca de 330 MB | cerca de 330 MB |
| Situação | testado no Linux | só nos testes automáticos do GitHub; nunca num Mac de verdade |

No Ubuntu 24.04 o `pw-play` é mais velho, e o speak usa o `paplay` ou o `aplay` no lugar. O código do Mac tem suporte e passa nos testes automáticos do GitHub, mas nunca foi testado num Mac de verdade. Quem usar no Mac e tiver problema pode abrir uma issue em https://github.com/ricksouzaa/cc-speaker/issues.

## Instalação

No Claude Code:

```
/plugin marketplace add ricksouzaa/cc-speaker
/plugin install speak@cc-speaker
```

Pronto. A voz se instala sozinha, em segundo plano e sem sudo: ali mesmo, logo depois do `/plugin install`, ou na próxima sessão que você abrir. São cerca de 280 MB para baixar (uns 330 MB no disco), entre o motor, o modelo de voz e as vozes, e leva alguns minutos. Enquanto isso:

- aparece uma linha na conversa dizendo que a voz está sendo instalada;
- embaixo do campo de texto, o progresso: `🔊 Instalando a voz: 78% (171 de 219 MB)`;
- no fim, o aviso "Voz pronta", e a voz começa a falar.

O `/speak status` e o rodapé do menu também mostram o andamento. Só uma instalação roda por vez, mesmo com várias sessões abertas.

## Uso

### O painel

Digite `/speak` sozinho. Abre um painel com uma lista por linha, já com o teclado nele, no terminal e no VS Code. Tab muda de linha, Enter escolhe o valor, e Esc ou o botão Fechar fecham. Cada escolha vale na hora.

| Linha | O que escolhe |
|---|---|
| Mudar em | onde as próximas trocas valem: todas as sessões (padrão ao abrir) ou só nesta |
| Voz | ligada (padrão), só o resumo escrito (a voz cala e a linha 🔊 continua saindo, mesmo sem o motor; na leitura inteira vale como desligada) ou desligada |
| Leitura | só o resumo (padrão) ou a resposta inteira |
| Tamanho do resumo | pequeno (uma frase), médio (padrão, duas ou três frases) ou grande (um parágrafo); a linha só aparece com a leitura em "só o resumo" (o `/speak size` escrito vale em qualquer modo) |
| Voz de leitura | Lola (padrão), Estelle ou Fantine (femininas); Rafael, Charles ou George (masculinas); vale sempre para todas as sessões |
| Velocidade da fala | de 0.5x a 2x; o 1x (padrão) é a velocidade normal da voz escolhida. Vale a partir da próxima fala (veja [Velocidade](#velocidade)) |
| Com o microfone em uso | Espera (padrão), Toca ou Toca nesta reunião (veja [Microfone](#microfone)) |
| Ouvir de novo | dois botões, Resumo e Resposta inteira: tocam na hora a última fala desta sessão; a linha não guarda valor |

Abaixo da última resposta (só depois que o turno termina) aparecem os mesmos dois botões, `[ ▶ Resumo ]` e `[ ▶ Resposta inteira ]`; sem a linha 🔊 só o segundo. Somem quando começa o turno seguinte. Clicar só funciona no terminal em tela cheia.

Enquanto a fala desta sessão toca, o botão do modo dela (Resumo ou Resposta inteira, tanto sob a resposta quanto na linha do painel) vira `[ ⏸ Pausar ]`; pausada, vira `[ ▶ Continuar ]`; ao acabar, volta ao normal. Embaixo do campo de texto, em todas as sessões, um aviso diz quem fala e com que voz: "🔊 Lola falando agora" na sessão dona da fala, "🔊 Lola falando em <pasta do projeto>" nas outras, e "⏸ fala pausada" na dona, quando pausada. No terminal o aviso fica no canto direito do rodapé, na linha do modo, só do ícone em diante (num terminal estreito, na linha de baixo). No VS Code e nos aplicativos ele sai na linha de status, que o Claude Code sempre começa com o nome do plugin (`speak: 🔊 Lola falando agora`); ali, enquanto a instalação do motor usa a linha, ela vence o aviso.

A pausa congela o tocador e a síntese (o sinal SIGSTOP no grupo de processos da fala) e continua com SIGCONT. Foi testada no Linux com o `pw-play`; com `paplay`, `aplay` e no Mac (`afplay`) o código é o mesmo, mas não foi testado num Mac de verdade.

Uma linha que só vale nesta sessão leva a marca "· só nesta sessão". O painel responde sem gastar uma resposta do Claude e funciona até no meio de uma resposta.

### Comandos escritos

Para pular o painel, escreva a ação. Com `all` no fim, vale para todas as sessões; sem ele, só para esta.

| Comando | O que faz |
|---|---|
| `/speak on` · `/speak quiet` · `/speak off` | liga a voz, cala a voz mas mantém o resumo escrito, ou desliga tudo (padrão: `on`) |
| `/speak mode summary` · `full` | lê só o resumo ou a resposta inteira (padrão: `summary`) |
| `/speak size small` · `medium` · `large` | tamanho do resumo (padrão: `medium`) |
| `/speak voice lola` · `estelle` · `fantine` · `rafael` · `charles` · `george` | troca a voz, sempre em todas as sessões (padrão: `lola`) |
| `/speak speed 0.9` · `1` · `1.25` | velocidade da fala: um número de 0.5 a 2, em que 1 é a velocidade normal da voz (padrão: `1`) |
| `/speak mic wait` · `play` · `auto` | o que fazer com o microfone em uso (padrão: `wait`) |
| `/speak again` · `again summary` · `again full` | ouve de novo a última fala desta sessão, mesmo com a voz desligada: do jeito em que tocou, só o resumo ou a resposta inteira |
| `/speak pause` | congela a fala que está tocando, de qualquer sessão, no ponto exato; a vez passa para a próxima da fila, e a pausada espera você pedir |
| `/speak resume` | continua a fala pausada desta sessão (ou a pausada mais recente); se outra fala toca, a pausada vai para a frente da fila e continua quando essa acabar |
| `/speak status` | mostra a versão do plugin e como está tudo: voz, leitura, tamanho, microfone, velocidade e motor |
| `/speak stop` | corta a fala que está tocando, esvazia a fila e encerra as falas pausadas |
| `/speak install` | instala o motor de novo, em primeiro plano |
| `/speak update` | atualiza o plugin para a versão mais nova do catálogo; vale depois de `/reload-plugins` ou numa sessão nova |

Sem o valor (`/speak mode`, `/speak voice`…), o painel abre já na linha certa. Sair de uma sessão corta as falas dela (tocando, na fila ou pausadas), e as de outras sessões continuam.

### Em palavras

Também dá para pedir ao Claude, escrevendo ou ditando: "fala só o resumo", "resumo maior", "troca para a voz do Rafael", "fala mais devagar", "para de falar", "cala a voz mas deixa o resumo", "silêncio em todas as sessões". Para pausar: "pausa"; para seguir: "continua" ou "continuar de onde parou". Para ouvir de novo: "repete", "não entendi, repete", "lê a resposta inteira", "lê só o resumo de novo". Ele roda o comando e confirma o que passou a valer.

## Velocidade

A velocidade é um número que multiplica a velocidade normal da voz escolhida: `1` é o normal, `0.9` um pouco mais devagar, `1.25` mais rápido. O painel oferece 0.5x, 0.75x, 0.9x, 1x, 1.1x, 1.25x, 1.5x, 1.75x e 2x; escrita, vale qualquer número de 0.5 a 2 (`/speak speed 0.95`). O plugin mostra a velocidade com ponto; ao escrever, a vírgula vale igual (`/speak speed 0,95`).

- **Vale a partir da próxima fala.** A fala que está tocando termina na velocidade em que começou.
- **Para comparar de ouvido,** troque a velocidade e use "Ouvir de novo": a mesma resposta é lida outra vez, já na velocidade nova.
- **O motor fala numa velocidade só,** que é o 1x. As outras são a mesma fala esticada ou encurtada no tempo, no mesmo tom: a voz não fica mais grossa nem mais fina. Perto do 1x quase não se nota; nos extremos (0.5x e 2x) o som pode perder naturalidade.
- **Com a variável `CLAUDE_SPEAK_SPEED` definida,** a escolha fica guardada, mas não vale: a voz segue no número da variável. O painel, o `/speak status` e a resposta do `/speak speed` avisam; para a escolha valer, tire a variável.

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
- **O motor não roda nesta máquina:** num Linux mais antigo que o da tabela de [requisitos](#requisitos), ou com a pasta de dados num disco que não deixa rodar programas, a instalação para e diz "o programa do motor não roda nesta máquina". Não há conserto pelo plugin; a versão 0.23.0, com o motor antigo, roda nesses sistemas.
- **A instalação falhou:** ela não tenta de novo sozinha, para não baixar tudo em toda sessão. O aviso fica embaixo do campo; rode `/speak install` para tentar de novo, vendo cada etapa.
- **O registro** de cada instalação fica em `state/install.log`, na [pasta de dados](#pastas). Cada etapa aparece ali na hora em que começa.

Enquanto o motor falta, o Claude não escreve a linha 🔊, a não ser que a voz esteja em só o resumo escrito. A instalação automática se desliga com `CLAUDE_SPEAK_AUTOINSTALL=0`.

Quando o plugin é ativado com uma sessão já aberta, a instalação começa ali mesmo, mas as regras da voz só chegam ao Claude na próxima sessão.

## Ajustes avançados

### Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `CLAUDE_SPEAK=0` | a sessão começa muda |
| `CLAUDE_SPEAK_MODE`, `CLAUDE_SPEAK_SIZE`, `CLAUDE_SPEAK_MIC`, `CLAUDE_SPEAK_VOICE` | valem mais que as escolhas gravadas |
| `CLAUDE_SPEAK_SPEED` | a velocidade da fala, de 0.5 a 2 (1 é o normal), no lugar da escolha do `/speak speed` |
| `CLAUDE_SPEAK_AUTOINSTALL=0` | desliga a instalação automática do motor |

### Siglas

O motor de voz erra a leitura de siglas escritas em maiúsculas (IBGE sai como uma palavra). Por isso o plugin soletra, antes de falar, toda sigla de duas a seis letras ("IBGE" vira "i bê gê é"), menos as que se leem como palavra (SUS, PIX, ENEM, ONU, NASA e outras) e os números romanos. Para acrescentar uma sigla que deve ser lida como palavra, ponha-a numa linha do arquivo `config/words` da pasta de dados; as linhas que começam com `#` são comentários.

### Palavras em inglês

O motor só recebe texto escrito e lê o que está em inglês com as regras do português. Para alguns termos comuns (plugin, GitHub, pull request, bug, backend), o plugin escreve a palavra do jeito que se fala antes de entregá-la ao motor ("plâguin", "bâg"); os outros saem como o motor os lê. O arquivo `config/english`, que a versão 0.23.0 usava, não tem mais efeito.

### Pastas

Tudo fica na pasta de dados do plugin, `~/.claude/plugins/data/speak-cc-speaker` (ou onde `CLAUDE_SPEAK_DATA` mandar): o motor em `engine/`, as escolhas em `config/` e o estado em `state/`.

Desinstalar o plugin apaga essa pasta inteira, a menos que você use `--keep-data`. Quem usava uma versão antiga, com as pastas `~/.local/share/claude-speak`, `~/.config/claude-speak` e `~/.local/state/claude-speak`, as vê movidas para lá na primeira vez.

## Desenvolvimento

- Testes do motor e do script: `python3 -m unittest discover -s tests`
- Testes do comando `/speak`: `claude plugin test .`
- Instalação numa máquina nova, num contêiner Ubuntu: `bash tests/docker/instalacao-limpa.sh auto`, ou `visual` para ver a tela (veja [`tests/docker/README.md`](tests/docker/README.md))
- Os testes rodam no GitHub no Ubuntu e no macOS a cada envio.

Decisões e próximos passos: [`docs/proximos-passos.md`](docs/proximos-passos.md).

## Licença

MIT (veja [`LICENSE`](LICENSE)).

O motor de voz não vem neste repositório: o `speak install` o baixa na sua máquina, e cada parte tem a sua licença.

| Parte | De onde vem | Licença |
|---|---|---|
| Programa | [Pocket TTS](https://github.com/kyutai-labs/pocket-tts), da Kyutai | MIT |
| Modelo de português | [`kyutai/pocket-tts-without-voice-cloning`](https://huggingface.co/kyutai/pocket-tts-without-voice-cloning), da Kyutai | CC BY 4.0 |
| Vozes Fantine, Charles e George | gravações do [VCTK](https://datashare.ed.ac.uk/handle/10283/3443), da Universidade de Edimburgo, no [catálogo de vozes da Kyutai](https://huggingface.co/kyutai/tts-voices) | CC BY 4.0 |
| Voz Estelle | gravação da própria Kyutai, no mesmo catálogo | CC0 |
| Voz Lola | um trecho do Common Voice, da Mozilla | CC0 |
| Voz Rafael | um trecho de áudio que a Kyutai publica junto do modelo, sem dizer a origem | a do modelo (CC BY 4.0); a do áudio original não foi confirmada |

O plugin usa só as vozes prontas desse catálogo. Ele não clona voz de ninguém, e o modelo que baixa é a edição sem essa função.
