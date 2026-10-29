# Próximos passos e decisões

O plugin `speak` nasceu em 28/10/2026 da voz que vivia no ai-harness (versão `ee7bd73` de lá); a troca terminou no mesmo dia. Desenhos: `docs/superpowers/specs/`.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub, com licença MIT; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português, com escolha entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.
- O repositório não usa o fluxo do harness (sem quadro).

## Decisões de 29/10/2026 que valem daqui em diante

- **Menu do `/speak`:** painel com uma lista nativa (`Select`) por linha e um botão Fechar, aberto com o foco (`$.ui.open({ focus: true, closeOnEscape: true })`). Recusados: o `Client` desenhado à mão (só recebe teclas depois de um clique, o Esc nunca chega e não abre no VS Code) e a caixa de pergunta `$.ui.ask` (vira um assistente de perguntas, sempre com a opção "Other"). Navegar com Tab é limite do Claude Code, aceito. O lugar do painel é do Claude Code: ao lado da conversa em tela cheia com 110 colunas ou mais, acima do campo nos outros casos.
- **Sessão do `speak`:** a chave vem do processo `claude` ancestral (`<pid>-<início>`), não do `session_id` do Claude Code; o gancho de fim de sessão a acha do mesmo jeito. `SessionEnd` sem filtro de motivo, então `/clear` e `resume` também cortam a fala da conversa que sai.
- **Instalação do motor:** a regra do início automático vive só em `speak autoinstall`, chamado pelo gancho de começo e pelo módulo (ao ativar o plugin no meio da sessão, o Claude Code roda o módulo, mas não o gancho `SessionStart` de comando). A trava `state/install.lock` fica dentro do `speak install`; o progresso só vale com ela presa. Uma falha não tenta de novo sozinha na mesma versão do plugin.
- **Pasta de dados no shell:** o gancho de começo exporta `CLAUDE_SPEAK_DATA`, nunca `CLAUDE_PLUGIN_DATA`, que outros plugins leriam como a pasta deles.
- **Microfone no Mac:** a conta ignora a saída padrão e a saída do sistema, para o próprio som não parecer gravação. Limite: ditar no microfone do mesmo aparelho em que a voz toca não corta a fala.
- **Opção do microfone:** `wait`, `play` e `auto`. O `auto` volta a `wait` quando o microfone passa de ocupado para livre, visto na espera pela vez, na vigia da fala e no gancho de mensagem nova (`speak _mictick`), sem processo novo em segundo plano. Limite: sem fala e sem mensagem nova, a volta espera a próxima. A vez vai para a fala mais antiga que pode tocar agora (0.8.1): a fala de uma sessão em `wait` com o microfone ocupado guarda o seu lugar, mas não segura as de trás (`play`, `auto`); quando o microfone fica livre ela toca antes das que chegaram depois. Bilhete sem sessão (versão antiga) conta como `wait`. O microfone é lido uma vez por volta. **Ditado (0.9.1):** em `play` e `auto` no Linux só o ditado do Claude Code (`application.name` terminando em `[<nome>]` ou `node.name` `alsa_capture.<nome>`, com `<nome>` o `comm` ou o nome do executável de um processo `claude` vivo da pessoa, lido do `/proc` só quando há uma gravação com esse jeito) segura e corta a fala; `wait` segue igual (qualquer gravação). Ditar sozinho não conta como reunião vista no `auto`. Mac: o CoreAudio não diz quem grava, então em `play`/`auto` nada segura (como antes).
- **Versão e envio:** todo ajuste sobe a versão e é enviado na hora (`.claude/rules/git-workflow.md`).
- **Versões publicadas (29/10/2026):** Versionamento Semântico completo, `CHANGELOG.md` no formato Keep a Changelog, marca anotada `vX.Y.Z` e página de versão no GitHub com as notas da seção; as 34 versões anteriores foram marcadas no commit de cada uma. Marca enviada não se move nem se apaga. A passagem para 1.0.0 é decisão do Ricardo.

## Feito

- Plugin `speak` no catálogo `cc-speaker`, com o comando `/speak`: um painel com listas nativas (ligar, leitura, tamanho, voz, alcance) que fica aberto até Esc, pedidos em palavras e o motor instalado sozinho na primeira sessão.
- Alcance guardado: "só esta sessão" e "todas as sessões" são coisas distintas; todas as sessões apaga as exceções em vez de copiar o valor.
- Pasta de dados na do plugin (`.../plugins/data/speak-cc-speaker`, ou a que o Claude Code der): motor, escolhas e estado juntos, e `claude plugin uninstall` apaga tudo (a menos que use `--keep-data`). As pastas antigas (`~/.local/share/claude-speak` e as outras) se mudam sozinhas, uma de cada vez.
- Mac: peça por sistema em `lib/speak_os.py`; som em fluxo pelo `sounddevice` (com prazo para abrir, escrever e parar) e `afplay` de reserva; microfone lido pelo CoreAudio. O fluxo do GitHub roda os testes no Ubuntu e no macOS (também no Python 3.9 do Mac). Falta o teste num Mac de verdade.
- A linha 🔊 do resumo só é pedida no modo resumo (o padrão); no modo leitura inteira o modelo é avisado de que não deve escrevê-la.
- Fim de sessão corta a fala daquela sessão (`speak stop here`), sem mexer nas outras.
- Instalação do motor visível: progresso na linha de status, no `/speak status` e no menu, com aviso ao fim ou na falha (issue #1).
- Teste de instalação limpa em contêiner (`tests/docker/`).
- Plugin ativado no meio da sessão instala o motor ali mesmo, com aviso na conversa e progresso (issue #2, testada pelo Ricardo numa máquina limpa).
- Opção do microfone (espera, toca, toca nesta reunião), no menu, por escrito e em palavras.
- README reorganizado em tabelas, com os padrões de cada opção.
- Tamanho do resumo (pequeno, médio, grande) e escolha da voz (dora, alex, santa).
- Filtro do que se narra: a voz não lê nomes de ramo, códigos de commit, HEAD nem código entre crases com hífen, sublinhado ou número (0.7.5).
- Ouvir de novo (0.8.0): `speak again [summary|full]` repete a última fala da sessão (guardada em `state/last/`, podada com as sessões mortas), mesmo com a voz desligada; no `/speak again` e numa linha do painel; sem 🔊, o resumo lê a resposta inteira e avisa.
- Versão no `status` (linha própria `versão:`, campo `version` no `--json` e no rodapé do painel) e `speak update` (0.9.0): roda `claude plugin marketplace update` e `claude plugin update`, 120 s cada, e diz de que versão para qual; a nova só vale depois do `/reload-plugins` (o módulo não consegue dispará-lo). `plugin_version` agora vive em `lib/speak_paths.py`.
- Testes que não tocam a pasta de dados real: um só ajudante de isolamento (`tests/isolation.py`) e um guarda-costas que compara a pasta real antes e depois da bateria.

## Recusado

- Um comando por ação (`/speak-on`, `/speak-off` e outros), pedido pela sessão do smart-platform: recusado pelo Ricardo em 29/10/2026; `/speak on` e os demais já bastam.

## Pendências

- **Mac de verdade**: confirmar som, microfone e achar a sessão (`speak check`). A classe `_CoreAudio` (`lib/speak_os.py`) não tem cobertura de teste e suas constantes foram escritas de memória. Em 29/10/2026 o testador deixou de ter o Mac: o teste fica aberto para quem aparecer pelas issues (https://github.com/ricksouzaa/cc-speaker/issues), e o README avisa que o macOS nunca foi testado num Mac de verdade.
- **Microfone embutido sempre ligado no Mac**: se a escuta da Siri (ou outro programa) deixar a entrada embutida em uso o tempo todo, a fila pode achar que alguém grava e a voz esperar para sempre. A ver no teste do Mac.
- **Módulo e ganchos com pastas diferentes**: com `--plugin-dir` (cópia de desenvolvimento) o módulo do painel e os ganchos ainda derivam pastas de dados diferentes (investigado em 29/10/2026). A ordem nova (`CLAUDE_SPEAK_DATA` antes de `CLAUDE_PLUGIN_DATA`, 0.11.1) só vale onde a variável existe, e o módulo não a recebe: ele chama o `speak` sem `CLAUDE_PLUGIN_DATA` e, como o script não está em `plugins/cache`, cai na pasta reserva `speak-cc-speaker`; os ganchos recebem `CLAUDE_PLUGIN_DATA` do Claude Code (para uma cópia de desenvolvimento, provavelmente `.../data/speak-inline`, ainda não visto). A leitura do `stateDir` pelo `speak status --json` (0.13.0) só faz o módulo ler a pasta do próprio `speak` dele, não a dos ganchos. Reproduzido: `speak status --json` dá `.../data/speak-cc-speaker/state` sem a variável e `<variável>/state` com ela. Proposta, ainda não aplicada (muda o desenho): em `speak_paths.root`, quando o script está em `plugins/cache` a pasta sai do caminho do script e `CLAUDE_PLUGIN_DATA` deixa de valer (numa instalação normal as duas coincidem); numa cópia de desenvolvimento, módulo e ganchos caem os dois na pasta reserva. Quem quiser outra pasta continua com `CLAUDE_SPEAK_DATA`. Falta o Ricardo decidir e confirmar o que o Claude Code exporta para o módulo.

## Pedidos para depois

- **Outros narradores** pesquisados em 28/10/2026, para escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- **Voz no estilo do Jarvis**, ideia do Ricardo. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator nem o nome como marca.

## Retirado

- Modo celular (mp3 enviado pelo controle remoto): retirado em 28/10/2026, porque o botão de ler em voz alta do próprio app (celular e web, no controle remoto) cobre o caso.
