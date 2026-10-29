# Registro de mudanças

Todas as mudanças que importam para quem usa o plugin `speak` ficam aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/). Cada versão tem a sua marca `vX.Y.Z` e a sua página em
[Releases](https://github.com/ricksouzaa/cc-speaker/releases), com as notas copiadas daqui.

## [Não lançado]

## [0.14.1] - 2026-10-29

### Alterado
- Quem apontava a pasta de dados com `CLAUDE_PLUGIN_DATA` deve usar `CLAUDE_SPEAK_DATA`.

### Corrigido
- O painel do `/speak` e os ganchos sempre usam a mesma pasta de dados. Numa cópia de desenvolvimento (`--plugin-dir`) eles podiam usar pastas diferentes, porque só os ganchos recebiam a variável `CLAUDE_PLUGIN_DATA` do Claude Code. Ela deixou de ser lida: a pasta vem de `CLAUDE_SPEAK_DATA`, se existir, ou de onde o plugin está instalado. Numa instalação normal nada muda.

## [0.14.0] - 2026-10-29

### Adicionado
- Voz Alice: a Dora mais suave, feita misturando a Dora com uma voz americana do próprio arquivo de vozes (nada novo para baixar), com leitura em português e velocidade padrão 1,05. Escolha no painel ou com `/speak voice alice`; quem já tinha Dora, Alex ou Santa guardada continua como estava.

## [0.13.1] - 2026-10-29

### Corrigido
- O aviso de que a voz está sendo instalada sai uma vez só: quando o módulo do painel e o início da sessão tentavam instalar ao mesmo tempo (máquina carregada), os dois podiam avisar. Agora avisa quem de fato começou a instalação; a sessão que abre com a instalação já em andamento não repete o aviso na tela (o progresso segue na linha de status).
- Duas sessões abertas juntas na primeira vez depois de atualizar não rodam mais ao mesmo tempo a limpeza única dos arquivos de sessão do modelo antigo.
- Mudança de pastas antigas para a nova entre discos que falha por um erro inesperado já não deixa para trás a cópia pela metade (`<pasta>.part-<número>`).
- Um arquivo de ambiente da sessão (`CLAUDE_ENV_FILE`) com bytes que não são texto não faz o gancho de começo repetir a linha `export CLAUDE_SPEAK_DATA=...` a cada sessão.

## [0.13.0] - 2026-10-29

### Adicionado
- `/speak pause` congela a fala que está tocando, de qualquer sessão, no ponto exato; enquanto ela fica pausada, a próxima fala da fila toca. `/speak resume` (ou, em palavras, "continua", "continuar de onde parou") a retoma: na hora, se nada toca, ou na frente da fila, assim que a que toca terminar. `/speak stop`, sair da sessão e o fim de uma sessão encerram as falas pausadas.
- O botão que deu o play (Resumo ou Resposta inteira, sob a última resposta e na linha "Ouvir de novo" do painel) vira "⏸ Pausar" enquanto a fala desta sessão toca e "▶ Continuar" quando ela está pausada.
- A linha de status sob o campo de texto avisa, em todas as sessões, quem está falando: "🔊 falando agora" na sessão dona da fala, "🔊 falando: <pasta do projeto>" nas outras e "⏸ fala pausada" na dona quando pausada. A linha da instalação da voz continua vencendo.
- `/speak status` mostra o que toca agora e o que está pausado.

## [0.12.0] - 2026-10-29

### Adicionado
- Com a máquina carregada, a voz junta fala pronta suficiente antes de começar, para tocar até o fim sem parar entre as frases; com a máquina livre, começa na hora, como antes.
- No Linux, o tocador de áudio pede prioridade de tempo real ao sistema (sem senha), para o som não picotar no meio da palavra quando o processador está cheio. Se o sistema recusar, toca como antes.

## [0.11.1] - 2026-10-29

### Corrigido
- Falas esperando a vez leem o microfone uma vez por segundo em vez de sete, e de novo logo antes de tocar: vinte falas presas na fila gastavam mais de um núcleo inteiro do processador.
- A pasta de dados do `speak` vence a de outro plugin que esteja exportada no mesmo terminal.

## [0.11.0] - 2026-10-29

### Adicionado
- Botões Resumo e Resposta inteira abaixo da última resposta, para ouvir de novo sem abrir o painel.

## [0.10.0] - 2026-10-29

### Alterado
- Só a subida de versão: a novidade da 0.9.1 (o painel mostra o tamanho do resumo apenas no modo resumo) pedia o número do meio.

## [0.9.1] - 2026-10-29

### Alterado
- O painel só mostra o tamanho do resumo no modo resumo.

### Corrigido
- Em "toca" e "toca nesta reunião", o ditado do Claude Code continua cortando a fala.
- A voz lê comandos de barra (por exemplo, "barra speak stop").
- A linha 🔊 não vai na recapitulação nem em textos que o próprio Claude Code gera.

## [0.9.0] - 2026-10-29

### Adicionado
- A versão aparece no `speak status` e no rodapé do painel.
- `speak update` atualiza o catálogo e o plugin de uma vez.

## [0.8.1] - 2026-10-29

### Corrigido
- Uma fala que espera o microfone não trava mais a fila das sessões que tocam durante a reunião.

## [0.8.0] - 2026-10-29

### Adicionado
- Ouvir de novo a última fala da sessão, como tocou, só o resumo ou a resposta inteira (`speak again`), mesmo com a
  voz desligada.

## [0.7.5] - 2026-10-29

### Alterado
- Interno: testes mais estáveis (guarda da pasta real e microfone simulado no Mac).

## [0.7.4] - 2026-10-29

### Corrigido
- A voz não lê nomes de ramo, códigos de commit, HEAD nem código entre crases com hífen, sublinhado ou número.

## [0.7.3] - 2026-10-29

### Alterado
- Documentação: decisões do menu, da instalação visível e do Mac nos próximos passos.

## [0.7.2] - 2026-10-29

### Alterado
- Documentação: regra do fluxo do git do projeto.

## [0.7.1] - 2026-10-29

### Alterado
- README reorganizado em tabelas, com o padrão de cada opção e uma seção de problemas.

## [0.7.0] - 2026-10-29

### Adicionado
- Opção do microfone: espera, toca ou toca nesta reunião.

## [0.6.2] - 2026-10-29

### Corrigido
- Plugin ativado no meio da sessão instala o motor ali mesmo e avisa na conversa (#2).

## [0.6.1] - 2026-10-29

### Corrigido
- O gancho de início de sessão não falha quando falta a pasta `lib/`.
- No Mac, o fluxo de áudio abre com prazo e o corte pelo microfone não fica esperando.
- O gancho de início de sessão também roda ao bifurcar uma conversa.

### Alterado
- Interno: testes isolados da pasta de dados real e rodando também no Python 3.9 do Mac.

## [0.6.0] - 2026-10-29

### Alterado
- Documentação do menu do `/speak`, da pasta de dados e do Mac.

## [0.5.11] - 2026-10-29

### Corrigido
- A vigia do microfone para quando a fala termina.
- O corte da fala ao fim da sessão acontece sob a trava da fila.

## [0.5.10] - 2026-10-29

### Adicionado
- O fim de uma sessão corta a fala daquela sessão, sem mexer nas outras.

### Corrigido
- O progresso da instalação tolera uma leitura falha e não rouba o foco do menu.

## [0.5.9] - 2026-10-29

### Adicionado
- A instalação do motor mostra o progresso e avisa na tela quando acaba ou falha (#1).

## [0.5.8] - 2026-10-29

### Corrigido
- O menu do `/speak` usa listas nativas, que recebem o foco e abrem também no VS Code.
- O gancho avisa quando a leitura volta ao resumo no meio da sessão.

## [0.5.7] - 2026-10-29

### Alterado
- A linha 🔊 só é pedida no modo resumo, que passa a ser o padrão.

## [0.5.6] - 2026-10-29

### Adicionado
- O `/speak` abre um menu que fica aberto até o Esc.
- No Mac, o som toca pelo `sounddevice` e cai para o `afplay` em qualquer falha.

### Corrigido
- O microfone do Mac ignora a saída padrão e pula o dispositivo com erro.

## [0.5.5] - 2026-10-28

### Adicionado
- Som e microfone no Mac.

## [0.5.4] - 2026-10-28

### Corrigido
- "Só esta sessão" e "todas as sessões" são guardadas como escolhas distintas.
- A marca de falha da instalação guarda a versão do plugin.

## [0.5.3] - 2026-10-28

### Corrigido
- Uma instalação espera a que já está rodando, e o status diz que está instalando.

## [0.5.2] - 2026-10-28

### Alterado
- Motor, escolhas e estado passam para a pasta de dados do plugin; as pastas antigas se mudam sozinhas.
- O que depende do sistema fica numa peça própria (Linux e Mac).

## [0.5.1] - 2026-10-28

### Corrigido
- Com um `pw-play` antigo, sem `--raw`, a voz toca pelo `paplay` ou pelo `aplay`.

## [0.5.0] - 2026-10-28

### Alterado
- O `/speak` pergunta em caixas de escolha no lugar do painel.

## [0.4.0] - 2026-10-28

### Removido
- Modo celular: o botão de ler em voz alta do próprio app cobre o caso.

## [0.3.0] - 2026-10-28

### Alterado
- O `/speak` abre uma lista em vez de perguntar.

## [0.2.1] - 2026-10-28

### Adicionado
- Todo comando também por palavras, com menu quando falta a escolha.

## [0.2.0] - 2026-10-28

### Adicionado
- Modo celular (mp3 pelo controle remoto).

## [0.1.2] - 2026-10-28

### Removido
- A guarda da voz antiga.

## [0.1.1] - 2026-10-28

### Adicionado
- Menus de setas em `/speak:mode`, `/speak:size` e `/speak:voice`.
- Licença MIT.

## [0.1.0] - 2026-10-28

### Adicionado
- Primeira versão do plugin `speak`: ganchos em Python, comandos de barra, tamanho do resumo e escolha da voz.

[Não lançado]: https://github.com/ricksouzaa/cc-speaker/compare/v0.14.1...HEAD
[0.14.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.1
[0.14.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.0
[0.13.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.13.1
[0.13.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.13.0
[0.12.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.12.0
[0.11.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.11.1
[0.11.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.11.0
[0.10.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.10.0
[0.9.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.9.1
[0.9.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.9.0
[0.8.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.8.1
[0.8.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.8.0
[0.7.5]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.5
[0.7.4]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.4
[0.7.3]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.3
[0.7.2]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.2
[0.7.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.1
[0.7.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.7.0
[0.6.2]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.6.2
[0.6.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.6.1
[0.6.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.6.0
[0.5.11]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.11
[0.5.10]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.10
[0.5.9]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.9
[0.5.8]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.8
[0.5.7]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.7
[0.5.6]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.6
[0.5.5]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.5
[0.5.4]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.4
[0.5.3]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.3
[0.5.2]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.2
[0.5.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.1
[0.5.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.5.0
[0.4.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.4.0
[0.3.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.3.0
[0.2.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.2.1
[0.2.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.2.0
[0.1.2]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.1.2
[0.1.1]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.1.1
[0.1.0]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.1.0
