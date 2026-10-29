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
