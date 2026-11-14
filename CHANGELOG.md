# Registro de mudanças

Todas as mudanças que importam para quem usa o plugin `speak` ficam aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/). Cada versão tem a sua marca `vX.Y.Z` e a sua página em
[Releases](https://github.com/ricksouzaa/cc-speaker/releases), com as notas copiadas daqui.

## [Não lançado]

## [0.27.0] - 2026-11-14

### Quebra
- **As vozes Estelle e Fantine saíram do plugin.** Quem tinha escolhido uma delas passa a ouvir a Jane, sem fazer nada; `/speak voice estelle` e `/speak voice fantine` não são mais aceitos. Ao atualizar, o plugin apaga do disco os arquivos das duas (cerca de 55 MB no modelo maior) e baixa de novo só o programa do motor (cerca de 10 MB); a voz fica calada por alguns segundos, até terminar.

### Alterado
- **A voz padrão agora é a Jane** (era a Lola). Quem nunca escolheu uma voz passa a ouvi-la; para voltar à Lola, `/speak voice lola`.
- As vozes femininas agora são cinco, nesta ordem no painel e na ajuda: Jane, Eve, Mary, Vera e Lola. As masculinas continuam Rafael, Charles e George.
- Com duas vozes a menos, o motor ficou um pouco menor: cerca de 880 MB para baixar no modelo maior e 280 MB no normal.

### Corrigido
- **O fim da frase não é mais engolido.** De vez em quando o motor parava antes da última sílaba: "validação" saía "valida". Agora o plugin pede a ele mais certeza de que a frase acabou antes de parar. Medido sem tocar som, com a voz Jane no modelo maior: antes, a palavra saiu cortada em 4 de 52 falas; depois, em nenhuma de 52. No modelo normal a fala fica uns 4% mais longa, por uma pausa um pouco maior no fim de cada frase.
- **"Pull request" ganhou outra escrita para o motor**, porque na voz Jane "pull" saía com som de "puro" e "request" com a entonação errada. Das seis escritas medidas no modelo maior, a nova foi a que saiu certa mais vezes.
- O aviso de instalação diz quanto falta baixar, e não o tamanho do motor inteiro: numa atualização como esta, cerca de 10 MB em vez de 900 MB.

## [0.26.0] - 2026-11-14

### Adicionado
- **Quatro vozes femininas novas: Eve, Jane, Mary e Vera.** Escolha com `/speak voice eve` (ou `jane`, `mary`, `vera`), na linha "Voz de leitura" do painel ou pedindo ao Claude. Agora são sete femininas e três masculinas; a padrão continua Lola.

### Alterado
- **O modelo maior passou a ser o padrão.** De ouvido, ele pronuncia melhor: no modelo normal, "cinquenta" saía errado dentro de um número (50, 250, 1.250), e no maior sai certo. Quem nunca escolheu um modelo passa a usar o maior: ao atualizar, o plugin baixa o motor de novo em segundo plano (cerca de 950 MB) e a voz fica calada até terminar. Ele pesa mais: cerca de 2 GB de memória durante a fala e 5 a 6 segundos até o primeiro som, contra 1 GB e 2 a 3 segundos do normal.
- Quem já tinha escolhido um modelo com `/speak model` continua nele; a atualização baixa só o que falta (as quatro vozes novas e o programa do motor: cerca de 50 MB no normal, 130 MB no maior). Para usar o normal, o comando é `/speak model normal` (cerca de 310 MB).
- O painel e o `/speak model` mostram o maior primeiro, marcado como padrão.
- O README avisa de um limite do motor: ele não repete uma fala igual, e de vez em quando engole o fim de uma palavra. Numa frase longa, "validação" saiu "valida" em uma ou duas de cada dez vezes, no modelo maior. Não há ajuste do motor para isso, e reescrever a palavra piorou; ouvir de novo costuma sair certo.

## [0.25.0] - 2026-11-14

### Adicionado
- **Escolha do modelo da voz.** O motor tem dois modelos de português, e agora dá para trocar: `/speak model large` usa o maior e `/speak model normal` volta ao padrão. No painel é a linha "Modelo da voz". O maior lê melhor siglas e palavras em inglês e custa mais: cerca de 850 MB para baixar, 2 GB de memória durante a fala e o dobro da espera até o primeiro som. Só um modelo fica no disco: ao trocar, o outro é baixado em segundo plano e a voz fica calada até terminar.
- O `/speak status` mostra o modelo em uso.

### Corrigido
- **Os números voltaram a ser falados.** O motor novo não lê algarismos: na 0.24.0, um valor, uma hora ou uma porcentagem saíam como ruído e estragavam a frase em volta. Agora o plugin escreve tudo por extenso antes de falar: números inteiros e com vírgula, valores em reais ("R$ 1.250,00" vira "mil duzentos e cinquenta reais"), porcentagens, horas ("23h30"), datas ("14/11/2026"), ordinais ("1º"), unidades ("280 MB") e versões.
- **As siglas voltaram a ser entendidas.** O motor novo erra palavras escritas em maiúsculas. A sigla soletrada agora vai com os nomes das letras numa palavra só ("IBGE" vira "ibegeé"), e a que se lê como palavra (SUS, ONU, NASA) vai só com a primeira letra maiúscula. SAC entrou na lista das que se leem como palavra. Vale também para a sigla no plural ("APIs") e para a colada a um número ("UTF-8", "MP3").
- Número romano (capítulo XIV) é lido como número, e uma palavra toda em maiúsculas ("ATENÇÃO") deixa de sair como ruído.
- Um valor com ponto de milhar ("1.250") não é mais lido como número de versão ("um ponto duzentos e cinquenta"), e uma data escrita com barras não some mais da fala.
- "Pull request" ganhou outra escrita para o motor, porque "request" saía com o som errado.
- A frase passada ao `speak test` e ao `speak say` recebe o mesmo preparo de números e siglas que uma resposta.
- **"Publico" não sai mais como "público".** Um verbo escrito igual a um nome com acento (publico, inicio, termino, calculo, pratica, critica e outros) saía com a sílaba forte do nome. A palavra "teste" também ganhou outra escrita para o motor, porque saía parecida com "texto".
- Um intervalo de horas ("14h-16h"), um valor por período ("R$ 30/ano") e uma velocidade ("120 km/h") não somem mais da fala.
- O tamanho do resumo é medido no texto como foi escrito: os números por extenso não fazem mais a fala ser cortada antes do fim.

### Alterado
- Mais termos em inglês são reescritos para o motor: release, commit, downtime e Slack.
- O aviso de instalação diz o tamanho do modelo escolhido.
- Escolher um modelo enquanto outra instalação roda não pede mais nada depois: o modelo escolhido é baixado em seguida, sozinho. E escolher um modelo tenta de novo uma instalação que tinha falhado.

## [0.24.0] - 2026-11-14

### Alterado
- **Motor de voz novo: o Pocket TTS, da Kyutai, entra no lugar do Kokoro.** A fala sai mais fluida e natural. Continua tudo na sua máquina: sem conta, sem custo e sem rede na hora de falar.
- **Seis vozes novas.** Femininas: Lola (a padrão), Estelle e Fantine. Masculinas: Rafael, Charles e George. Só o Rafael foi gravado em português; as outras são vozes de outras línguas falando português com o modelo de português. Troque pelo painel, por `/speak voice rafael` ou em palavras ("troca para a voz do Rafael").
- **A fala fica pronta mais depressa:** nos testes, a mesma resposta foi gerada em cerca de metade do tempo do motor antigo.
- **A velocidade mudou de jeito.** O motor novo fala numa velocidade só, que é o 1x. As outras velocidades são a mesma fala esticada ou encurtada no tempo, no mesmo tom: a voz não fica mais grossa nem mais fina. O 2x agora é o dobro de verdade. Perto do 1x quase não se nota; nos extremos o som pode perder naturalidade.
- **A instalação baixa menos:** cerca de 280 MB (antes 350), e cada arquivo baixado é conferido antes de ser usado.
- No `/speak status`, a linha da voz mostra a voz, se é feminina ou masculina, e a `velocidade aplicada`.

### Removido
- Sai o motor Kokoro, com as vozes **Dora, Alex e Santa**.
- Sai a **pronúncia do inglês por sons** que chegou na 0.23.0, junto com o arquivo `config/english`. O motor novo só recebe texto escrito e não aceita os sons prontos. No lugar, o plugin escreve do jeito que se fala alguns termos comuns (plugin, GitHub, pull request, bug, backend); os outros termos em inglês saem como o motor os lê, com as regras do português.

### Quebra
- **O motor é baixado de novo.** Depois de atualizar o plugin, o motor novo se instala sozinho na próxima sessão (cerca de 280 MB, alguns minutos), com o progresso embaixo do campo de texto, e os arquivos do Kokoro são apagados da pasta de dados. Até a instalação terminar, a voz fica calada. Sem internet nessa hora, rode `/speak install` quando tiver.
- **No Linux, o motor novo pede Ubuntu 22.04, Debian 12 ou mais novo** (glibc 2.34), em x86_64 ou ARM de 64 bits. Num sistema mais antigo a instalação para e diz que o programa do motor não roda ali; a 0.23.0 é a última versão que funciona nesses sistemas.
- `/speak voice dora`, `alex` e `santa` deixam de existir. Quem tinha escolhido a Dora passa a ouvir a Lola; quem tinha o Alex ou o Santa passa a ouvir o Rafael. Não é preciso fazer nada.
- O arquivo `config/english` não tem mais efeito.
- `CLAUDE_SPEAK_SPEED` agora é a velocidade da fala como você a ouve, em que 1 é o normal. Antes era o número entregue ao motor antigo, em que o normal era 1.1.

## [0.23.0] - 2026-11-13

### Adicionado
- **Termos técnicos em inglês voltam a ser falados com a pronúncia do inglês,** na mesma voz: plugin, commit, push, deploy, build, pull request, GitHub, backend, token, cache e outros. Antes saíam aportuguesados ("plu-jín", "jítch-úb"). Desta vez a frase inteira é gerada de uma vez, com os sons do inglês no lugar dos termos, sem a emenda de áudios que deixou a 0.16.0 estranha.
- Para incluir outros termos, escreva-os no arquivo `config/english` da pasta de dados, um por linha ou vários na mesma linha, separados por espaço (as linhas que começam com `#` são comentários).

## [0.22.1] - 2026-11-13

### Alterado
- **A velocidade da fala agora aparece com ponto,** como os tocadores de vídeo e de áudio mostram: `0.9x`, `1.25x`. Vale para o painel, o `/speak status` e as respostas do `/speak speed`. Para escrever nada muda: `/speak speed 0.9` e `/speak speed 0,9` continuam valendo igual.
- Quando uma resposta cita a velocidade desse jeito, a voz lê o número inteiro ("um ponto vinte e cinco xis"), sem engolir o ponto.
- **No terminal, o aviso de quem está falando perdeu o `speak:` da frente** e aparece só do ícone em diante: "🔊 Dora falando agora". O Claude Code escreve o nome do plugin antes de toda linha de status e não deixa tirar; por isso o aviso mudou de lugar e agora fica no canto direito do rodapé, na linha do modo (num terminal estreito, na linha de baixo). No VS Code e nos aplicativos ele continua na linha de status, com o `speak:`. Os avisos da instalação do motor seguem na linha de status em todo lugar.

## [0.22.0] - 2026-11-13

### Adicionado
- **Velocidade da fala.** Agora você escolhe se a voz fala mais devagar ou mais rápido, de 0,5x a 2x. O 1x é a velocidade normal da voz escolhida, a mesma de antes: quem não mexer não nota diferença. Escolha pelo painel (linha "Velocidade da fala"), por `/speak speed 0,9` (qualquer número de 0,5 a 2, com vírgula ou ponto; com `all` no fim, vale para todas as sessões) ou em palavras, como "fala mais devagar".
- A velocidade nova vale a partir da próxima fala. Para ouvir a diferença na hora, use "Ouvir de novo": a mesma resposta é lida outra vez, já na velocidade escolhida.
- `/speak status` mostra a escolha na linha `velocidade da fala`.
- **O aviso de quem está falando agora diz a voz.** Na linha embaixo do campo de texto aparece "🔊 Alex falando agora" na sessão que fala e "🔊 Dora falando em <pasta do projeto>" nas outras sessões.

### Alterado
- No `/speak status`, a linha da voz passa a dizer `velocidade no motor`, para não se confundir com a escolha: é o número que o motor recebe, a velocidade normal da voz vezes a escolha. O motor aceita de 0,5 a 2 nesse número, e por isso o 2x fica hoje um pouco abaixo do dobro.
- `CLAUDE_SPEAK_SPEED` continua valendo mais que a escolha, como antes. Quando ela está definida, a escolha fica guardada mas não vale, e o plugin avisa: no `/speak status`, no painel e na resposta do `/speak speed`.

### Removido
- Sai a **voz Alice**. Ela era a Dora misturada com uma voz americana e, de ouvido, não ficou muito diferente da Dora. Ficam a Dora, o Alex e o Santa.

### Quebra
- `/speak voice alice` deixa de existir, e a Alice sai do painel. Quem a tinha escolhido passa a ouvir a Dora, sem erro e sem precisar fazer nada; para outra voz, use o painel ou `/speak voice alex`.

## [0.21.2] - 2026-11-10

### Corrigido
- Numa conversa reaberta num processo novo (o **Orca** faz isso ao reabrir as sessões, e também `claude --resume`), a primeira resposta depois de ligar a voz ou o "só o resumo escrito" vinha sem a linha 🔊, e o resumo só voltava na mensagem seguinte. O plugin achava que a conversa era nova e não avisava o modelo, que seguia os avisos antigos de "não escreva a linha". Agora, nessa primeira mensagem, o modelo é avisado uma vez de que a linha voltou a ser pedida.

## [0.21.1] - 2026-11-06

### Corrigido
- No chat do **Orca** (e em outros programas que abrem o Claude Code sem a tela dele), o aviso "🔊 falando agora" ficava na conversa depois que a fala acabava, e cada aviso virava uma linha a mais. Agora, sem uma tela do Claude Code que desenhe a linha de estado, o plugin não manda esses avisos. A voz, os comandos `/speak` e os pedidos em palavras funcionam igual. O painel do `/speak` e os botões embaixo da resposta continuam só no terminal e no VS Code, porque o Orca desenha a conversa com a própria tela.

## [0.21.0] - 2026-11-05

### Removido
- Sai o **resumo em mensagem própria** (`/speak split`, a linha do painel e o pedido em palavras). No app do celular, onde ele serviria, a resposta e o resumo chegam juntos numa resposta só, e o botão de ler em voz alta lê tudo. No computador a voz do plugin já lê só o resumo. A escolha guardada e as respostas que esperavam a linha 🔊 são apagadas sozinhas.

### Quebra
- `/speak split` e `speak split` deixam de existir. O resumo volta a vir sempre no fim da resposta.

## [0.20.1] - 2026-11-05

### Alterado
- O resumo em mensagem própria volta a vir **desligado**, como na 0.19.0, para não gastar uma chamada a mais do modelo em toda resposta. Ligue quando for ouvir pelo celular: `/speak split on` (ou `/speak split on all`), o painel ou peça em palavras. Quem ligou de propósito continua com ele ligado.

## [0.20.0] - 2026-11-05

### Alterado
- O resumo em mensagem própria passa a vir **ligado**: o Claude responde sem a linha 🔊 e manda a linha sozinha logo depois, pronta para o botão de ler em voz alta do app do celular. Quem já escolheu desligado continua assim. Para voltar ao resumo no fim da resposta, use `/speak split off all`, o painel ou peça em palavras.
- Com isso, cada resposta custa uma chamada a mais do modelo enquanto a escolha estiver ligada.

## [0.19.0] - 2026-11-05

### Adicionado
- Nova escolha: **resumo em mensagem própria**. Ligada, o Claude responde sem a linha 🔊 e, logo depois, manda a linha sozinha numa segunda mensagem. Assim, o botão de ler em voz alta do app do celular toca só o resumo. Escolha pelo painel (linha "Resumo em mensagem própria"), por `/speak split on` e `/speak split off` (com `all` no fim, para todas as sessões) ou em palavras, como "manda o resumo numa mensagem separada".
- A voz do plugin lê o resumo uma vez só, e "Ouvir de novo" guarda a resposta inteira com o resumo no fim, como antes.
- Custa uma chamada a mais do modelo por resposta, só enquanto a escolha está ligada. Vale com a voz ligada ou só com o resumo escrito, e não muda nada na leitura inteira ou com a voz desligada.
- `/speak status` mostra a escolha na linha `resumo em mensagem própria`.

## [0.18.0] - 2026-11-05

### Adicionado
- Novo estado da voz: **só o resumo escrito**. A voz fica calada, mas o Claude continua escrevendo a linha 🔊 com o resumo no fim de cada resposta, para você ler sem ouvir (numa reunião, por exemplo). Escolha pelo painel (linha "Voz"), por `/speak quiet` (ou `/speak quiet all`) ou em palavras, como "cala a voz mas deixa o resumo". A linha de estado mostra `voz: só o resumo escrito`, e o painel avisa que a voz está calada nesta sessão e o resumo continua escrito.
- O resumo escrito continua saindo mesmo sem o motor de voz instalado. Na leitura inteira, esse estado vale como voz desligada.
- "Ouvir de novo" (e `/speak again`) continua tocando a resposta em qualquer estado, inclusive com a voz calada.

## [0.17.2] - 2026-11-05

### Corrigido
- Depois de desligar e religar a voz, as sessões que já estavam trabalhando continuavam sem escrever a linha 🔊: o aviso de que a voz tinha voltado era dado uma vez só e o Claude podia ignorá-lo, no meio de vários avisos antigos de "voz desligada". Agora, com a voz ligada e no modo resumo, o aviso se repete a cada mensagem nova enquanto a última resposta da sessão estiver sem a linha 🔊, e para quando ela volta. O aviso também diz que os avisos antigos de "não escreva a linha" não valem mais.

## [0.17.1] - 2026-10-30

### Corrigido
- Ao pausar a fala no Linux, o som não fica mais chiando, como se repetisse o trecho em que você pausou. A pausa agora manda silêncio ao tocador em vez de congelá-lo, e a fala continua de onde parou. A pausa passa a levar até cerca de um quarto de segundo para ser ouvida.

## [0.17.0] - 2026-10-30

### Removido
- Os termos em inglês voltam a ser falados em português, como antes da 0.16.0: a pronúncia inglesa no meio da frase ficou estranha. Saem a lista de termos e o arquivo `config/english`.

### Quebra
- O arquivo `config/english`, se você criou um, deixa de ter efeito e pode ser apagado.

## [0.16.0] - 2026-10-30

### Adicionado
- Termos técnicos em inglês no meio do texto (reload, plugins, commit, push, deploy, build, GitHub e outros) passam a ser falados com a pronúncia do inglês, na mesma voz. Para incluir outros, escreva-os no arquivo `config/english` da pasta de dados.

### Corrigido
- A última letra de siglas soletradas terminadas em E (como o IBGE) saía curta demais; agora sai inteira.
- ENEM passa a ser falado "ê-nêi", sem o som final que o motor inventava.

## [0.15.2] - 2026-10-30

### Alterado
- A regra que o Claude lê para escrever a linha 🔊 agora deixa escrever número de versão e sigla do jeito normal, sem por extenso: o plugin já lê "0.15.1" como "0 ponto 15 ponto 1" e soletra as siglas. Assim o resumo e o texto completo mostram a mesma coisa.

## [0.15.1] - 2026-10-30

### Corrigido
- IPVA, IPCA, ONG, USP, CIPA e DNIT saíam da lista de siglas lidas como palavra: agora são soletradas, como a maioria das pessoas fala. Quem as lê como palavra pode pô-las no arquivo `config/words`.

## [0.15.0] - 2026-10-30

### Adicionado
- As siglas em maiúsculas agora são soletradas antes de falar: "IBGE" vira "i bê gê é" e "ANTT" vira "á êne tê tê". Antes o motor tentava ler como palavra e errava.
- As siglas que se leem como palavra (SUS, PIX, ENEM, ONU, NASA, Anvisa e várias outras) e os números romanos continuam como estavam. Para incluir outra, escreva-a numa linha do arquivo `config/words` da pasta de dados.

## [0.14.6] - 2026-10-30

### Corrigido
- Ao ligar a voz de novo (`/speak on` ou `/speak on all`), as sessões que tinham sido avisadas de que a voz estava desligada voltam a escrever a linha 🔊 já na mensagem seguinte. Antes o aviso de volta só existia para a leitura que passava de inteira para resumo, e essas sessões ficavam sem resumo e sem voz por algumas respostas.

## [0.14.5] - 2026-10-29

### Alterado
- O README mostra só os selos que se atualizam sozinhos (versão, testes e licença). Saíram os de sistemas, de Python e de voz local, que repetiam o texto e podiam ficar desatualizados.

## [0.14.4] - 2026-10-29

### Adicionado
- O README mostra selos de versão, de estado dos testes automáticos, de licença, de sistemas aceitos, de Python e de voz local.

## [0.14.3] - 2026-10-29

### Corrigido
- Os testes automáticos do macOS no GitHub voltam a poder passar: cinco testes que só valem no Linux (tocador em tempo real e espera do microfone na retomada da fala) agora são pulados no Mac. O programa não mudou.

## [0.14.2] - 2026-10-29

### Adicionado
- `speak check` mostra também a linha `microfone:` (livre, em uso ou não deu para saber), para ajudar a achar por que a voz espera, principalmente no Mac.
- Arquivos `CONTRIBUTING.md` e `SECURITY.md` no repositório.

### Alterado
- O README explica o que fazer no Mac quando o microfone embutido parece sempre em uso: `/speak mic play`.

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

[Não lançado]: https://github.com/ricksouzaa/cc-speaker/compare/v0.27.0...HEAD
[0.27.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.25.0...v0.26.0
[0.25.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.22.1...v0.23.0
[0.22.1]: https://github.com/ricksouzaa/cc-speaker/compare/v0.22.0...v0.22.1
[0.22.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.21.2...v0.22.0
[0.21.2]: https://github.com/ricksouzaa/cc-speaker/compare/v0.21.1...v0.21.2
[0.21.1]: https://github.com/ricksouzaa/cc-speaker/compare/v0.21.0...v0.21.1
[0.21.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.20.1...v0.21.0
[0.20.1]: https://github.com/ricksouzaa/cc-speaker/compare/v0.20.0...v0.20.1
[0.20.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.18.0...v0.19.0
[0.18.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.17.2...v0.18.0
[0.17.2]: https://github.com/ricksouzaa/cc-speaker/compare/v0.17.1...v0.17.2
[0.17.1]: https://github.com/ricksouzaa/cc-speaker/compare/v0.17.0...v0.17.1
[0.17.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.15.2...v0.16.0
[0.15.2]: https://github.com/ricksouzaa/cc-speaker/compare/v0.15.1...v0.15.2
[0.15.1]: https://github.com/ricksouzaa/cc-speaker/compare/v0.15.0...v0.15.1
[0.15.0]: https://github.com/ricksouzaa/cc-speaker/compare/v0.14.6...v0.15.0
[0.14.6]: https://github.com/ricksouzaa/cc-speaker/compare/v0.14.5...v0.14.6
[0.14.5]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.5
[0.14.4]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.4
[0.14.3]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.3
[0.14.2]: https://github.com/ricksouzaa/cc-speaker/releases/tag/v0.14.2
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
