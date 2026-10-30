# Plano: internacionalização (inglês)

Estado: **só plano**, sem prazo. Decidido pelo Ricardo em 30/10/2026: não fazer agora; o português do Brasil continua o padrão e quem quiser pode fazer um fork e traduzir.

## Objetivo

Quem mora fora do Brasil instala o mesmo plugin e usa a voz e os textos em inglês. Quem usa hoje não percebe mudança nenhuma.

## Desenho

- **Um motor só.** O Kokoro já traz vozes nativas em inglês (`af_`, `am_`, `bf_`, `bm_`) no mesmo arquivo de vozes; não há outro motor para baixar.
- **Idioma escolhido, não adivinhado.** Na instalação, se o idioma do sistema (`LANG`) não for português e nada foi escolhido, o gancho de início manda o Claude perguntar na primeira resposta: "Seu sistema está em inglês. Instalar a voz em inglês ou em português?". Sistema em português: instala sozinho, em português, como hoje. Depois, `speak lang <idioma>` troca para todas as sessões.
- **Tabelas por idioma**, uma por arquivo, com: as mensagens do terminal e do painel; as palavras que o código fala ou reconhece (o "ponto" da versão, "ramo/branch/worktree", o `MIC_TEXT`); e as vozes (lista, voz padrão e o `lang` do Kokoro, hoje fixo em `pt-br` na chamada do `create`).
- **O que o Claude já resolve**: a linha 🔊 e as respostas saem no idioma da conversa; basta o gancho dizer em que idioma escrever a linha. Os pedidos em palavras já viram comandos `speak` pela regra, em qualquer idioma.

## Onde mexer (medido em 30/10/2026)

- `bin/speak`: cerca de 50 pontos de mensagem e 22 padrões de texto na `clean`, quase todos neutros em relação ao idioma.
- `hooks/register.tsx`: cerca de 95 linhas de texto do painel.
- Ganchos Python e `lib/speak_update.py`: cerca de 15 textos.
- `rules/speak.md`: a instrução do idioma da linha 🔊.
- `tests/test_speak.py`: muitos testes conferem frases em português; fixar o idioma de teste em português ou ler as frases da tabela.
- `README.md` e `CHANGELOG.md` em inglês.

## Riscos

- A limpeza do texto antes da fala (números, siglas, versões) precisa de ajuste e teste de ouvido por idioma, não só tradução.
- A qualidade da voz inglesa do Kokoro ainda não foi ouvida pelo Ricardo.
- Primeira experiência de quem está fora do Brasil: sem a pergunta de idioma, a instalação sai em português.
- Mais coisas para testar; o Mac nunca foi testado.

## Alternativas descartadas por ora

- Adivinhar o idioma só pelo `LANG` sem perguntar: troca o idioma sem avisar.
- Voz que segue o idioma de cada resposta (detecção no texto): mais complexa e pode errar em respostas curtas.
- Segundo motor (Piper ou outro): só valeria para um idioma que o Kokoro não cobre.
- Primeira versão menor: traduzir só a pergunta de idioma, o aviso de instalação, `speak status` e `speak voice`, deixando o painel para depois.
