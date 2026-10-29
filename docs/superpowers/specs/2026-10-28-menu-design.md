> Trocado em 29/10/2026: o menu de hoje não é de setas nem usa `$.ui.ask`: é o painel lateral com listas nativas (Tab troca de linha, Enter escolhe, Esc ou o botão Fechar fecham; funciona no terminal e no VS Code). Veja as decisões de 29/10/2026 em `docs/proximos-passos.md`.

> Retirado em 28/10/2026: o modo celular e as seções dele neste desenho foram retirados (o botão de ler em voz alta do próprio app cobre o caso).

> Trocado em 28/10/2026, a pedido do Ricardo depois de comparar um protótipo: o painel de listas (`$.ui.open` + `ui.render`) deu lugar à caixa nativa `$.ui.ask`, que abre abaixo do campo de digitação. Fluxo novo: `/speak` sozinho pergunta "O que quer ajustar?", depois o valor daquele ajuste (com " (atual)" no valor em vigor) e, exceto para a voz de leitura, "Vale para quais sessões?"; só então o `bin/speak` roda, uma vez. `/speak mode|size|voice` pula a primeira caixa; `all` no fim pula a do alcance; Esc não muda nada. Isso também corrige o campo "Vale para" do painel, que voltava a "Só esta sessão" a cada abertura. O resto deste desenho continua valendo.

# Comando /speak com menus nativos: desenho

Data: 28/10/2026. Pedido do Ricardo: ao digitar o comando, escolher as opções com as setas, como no `/model`, para toda escolha (modo, tamanho, voz, saída...). Os comandos de barra feitos como habilidades não fazem isso: o menu vinha do modelo, depois de rodar um comando, numa resposta inteira. Decisões minhas, para a revisão dele.

## O que muda

- O plugin ganha um módulo de ganchos (`hooks/register.ts`, nomeado em `hooks/hooks.json` sob `modules`, ao lado dos `hooks` de comando de hoje; conferido com `claude plugin validate` numa cópia). Ele registra, no `session.start`, um comando só: `/speak` (sem prefixo; nome livre para módulos), com `immediate: true` (roda mesmo durante uma resposta, para `/speak stop` cortar a fala na hora).
- O `command.run` do `/speak` responde sozinho, sem o modelo e sem gastar resposta: abre o diálogo nativo de escolha (`$.ui.ask`, o mesmo do AskUserQuestion, escolhido com as setas) e roda o `speak` do plugin (`$.process.run` com `python3 -I <root>/bin/speak ...`, `root` de `$.plugin.root`); o processo é filho da sessão, então `speak` acha a sessão como hoje.
- As habilidades `skills/*` saem: uma forma só de comando. A regra (`rules/speak.md`) passa a citar `/speak` e os pedidos em palavras continuam como estão.

## Comportamento

- `/speak` sem argumento: "O que você quer ajustar?" (header "Voz"): "Ligar ou desligar", "Leitura e tamanho do resumo", "Voz", "Celular ou computador". O "Outro" do diálogo aceita uma ação escrita (`status`, `stop`, `install`, ou qualquer linha que `/speak` aceite).
- `/speak <ação>` sem escolha abre o menu daquela ação; com a escolha completa roda direto (`/speak voice alex`, `/speak mode summary all`, `/speak on`).
  - `on`/`off`: menu "Ligar" / "Desligar" (com "(atual)"), depois alcance.
  - `mode`: "Resposta inteira" / "Só o resumo" (com "(atual)"); se resumo, "Pequeno" / "Médio" / "Grande" (com "(atual)"); depois alcance.
  - `size`: os três tamanhos, depois alcance.
  - `voice`: uma opção por voz que `speak voice` lista ("Dora (feminina)" etc., "(atual)" na em uso); vale para todas as sessões, sem pergunta de alcance.
  - `phone`: "Celular (mp3 pelo controle remoto)" / "Alto-falante do computador", depois alcance.
  - Alcance: "Só esta sessão" / "Todas as sessões" (vira `all`).
  - `status`, `stop`, `install`: rodam direto, sem menu. `install` pode levar minutos.
- O "atual" vem de `speak status` (ou de um subcomando de consulta, se o implementador preferir algo estável de ler, como um `speak status --json`).
- Resposta: `{ text }` com uma linha clara em português do que vale agora (ou a saída do `speak` quando for `status`), e, quando a voz ou a saída mudou, `context` com uma nota curta ao modelo (por exemplo: a voz foi ligada nesta sessão; volte a terminar as respostas com a linha 🔊), para ele não depender só do gancho da próxima mensagem.
- Diálogo cancelado: `{ text: 'Nada mudou.' }`. Diálogo indisponível (rejeita, por exemplo numa superfície sem diálogo ou em `-p`): texto com as opções e a forma escrita (`/speak voice alex`).
- Erro do `speak`: a mensagem dele como texto.

## Verificação

`claude plugin validate .` sem erros; `claude plugin test .` com um `hooks/*.test.ts` que cobre: cada ação com escolha completa roda o `speak` certo; sem escolha abre o diálogo e roda o escolhido; cancelado não roda nada; alcance vira `all`. `python3 -m unittest discover -s tests` continua passando (testes das habilidades saem ou viram testes do módulo). Versão 0.3.0. Na sessão do Ricardo: `/speak` abre o menu.

## Motor instalado sozinho (pedido do Ricardo no mesmo dia)

O Claude Code não tem passo de pós-instalação para plugins. Então, no começo de uma sessão sem motor, `hooks/speak-start.py` dispara `speak install` em segundo plano, desligado da sessão (novo processo, saída em `~/.local/state/claude-speak/install.log`), sem perguntar, e só uma instalação por vez (trava de arquivo; outra sessão que abra durante a instalação não dispara outra). O aviso ao modelo passa a dizer que o motor está sendo instalado em segundo plano (cerca de 350 MB) e que a voz começa sozinha quando terminar; se faltar o uv, o aviso diz como instalá-lo (https://docs.astral.sh/uv/) e não dispara nada; se a última tentativa falhou, o aviso diz isso e aponta o log e `/speak install` para tentar de novo. `/speak install` continua, para tentar de novo em primeiro plano. README atualizado.

## Correção do Ricardo: lista, não pergunta

O diálogo de perguntas (`$.ui.ask`, o do AskUserQuestion) não é o que ele quer: quer uma lista como a do `/model`. Então o `/speak` abre um painel (`$.ui.open({ id: 'speak', title: 'Voz', focus: true, closeOnEscape: true, rows })`) desenhado por `ui.render` em `{ component: 'Pane', requestId: 'speak' }`, com elementos `Select` (setas movem, Enter escolhe, Esc fecha; `onSelect` roda o `speak` sem turno do modelo):

- `/speak` sozinho: o painel de ajustes, uma linha `Select` por ajuste, cada uma mostrando o valor atual: Voz (Ligada / Desligada), Leitura (Resposta inteira / Só o resumo), Tamanho do resumo (Pequeno / Médio / Grande), Voz (Dora, Alex, Santa, com o tipo), Saída (Computador / Celular), Alcance (Só esta sessão / Todas as sessões: vale para as escolhas seguintes de ligar, leitura, tamanho e saída). Cada escolha aplica na hora e redesenha com o novo valor; uma linha de rodapé diz o que acabou de mudar.
- `/speak <ação>` sem escolha: o mesmo painel só com a lista daquela ação (e o alcance, quando couber).
- Escolha completa (`/speak voice alex`), `status`, `stop`, `install`: como antes, sem painel.
- Painel que não abre (`isPlaced` false, sem superfície): texto com as opções e a forma escrita.
- `$.ui.ask` não é usado.

## Celular sem a linha 🔊 no chat

Pedido do Ricardo (o mp3 já chega e toca no celular): com a saída `phone` e o modo `summary`, a linha 🔊 não aparece no chat.

- `speak-cut.py` (nova mensagem): nessa combinação avisa "speak: modo celular com resumo: não termine esta resposta com a linha 🔊; o gancho de fim vai pedir o resumo." (a nota de "voz desligada" continua quando está mudo).
- `speak-stop.py`: nessa combinação não lê linha 🔊; bloqueia uma vez pedindo ao Claude que rode `speak mobile say "<resumo>"` (resumo da resposta recém-dada, no tamanho em vigor, sem código nem caminhos) e envie o mp3 impresso com SendUserFile, sem escrever mais nada. Celular com modo completo: como antes (o gancho sintetiza a prosa). No segundo Stop (`stop_hook_active`) não faz nada.
- `speak mobile say <texto>`: sintetiza o texto em mp3 (mesma função, mesma pasta e limpeza) e imprime o caminho; sem texto, sai com código 2. `speak mobile-summary` diz se a sessão está nessa combinação (código 0 e imprime a descrição do tamanho).
