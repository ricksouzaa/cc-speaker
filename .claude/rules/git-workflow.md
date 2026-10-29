# Fluxo do git (cc-speaker)

Projeto solo: só o Ricardo tem permissão de escrita no repositório.

- Os commits vão direto na `main`, sem pedido de mudança e sem linha de atribuição.
- Versões seguem o Versionamento Semântico (`MAIOR.MENOR.CORREÇÃO`):
  - correção ou texto sobe o último número (0.7.1 → 0.7.2);
  - funcionalidade nova sobe o do meio e zera o último (0.7.2 → 0.8.0);
  - mudança que quebra o uso de quem já tem o plugin (comando ou opção que some ou muda de sentido, escolhas ou pasta de dados que deixam de valer) sobe o primeiro e zera os outros; enquanto o primeiro número é 0, ela sobe o do meio e as notas avisam em "Quebra";
  - a passagem para 1.0.0 é decisão do Ricardo.
- Todo ajuste no projeto termina com a versão nova, publicada, sem esperar pedido:
  1. sobe a versão em `.claude-plugin/plugin.json` e no teste da versão em `tests/test_speak.py`;
  2. em `CHANGELOG.md`, o que estava em "Não lançado" vira a seção `## [X.Y.Z] - AAAA-MM-DD`, com as categorias Adicionado, Alterado, Corrigido, Removido e Quebra (só as que houver), escritas para quem usa o plugin; o link da versão vai ao pé do arquivo e o de "Não lançado" passa a comparar com a marca nova;
  3. roda as verificações: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests`, `claude plugin test .` e `claude plugin validate .`;
  4. faz o commit (`chore: versão X.Y.Z` quando é só a subida, ou o próprio commit do ajuste) e a marca anotada nele: `git tag -a vX.Y.Z -m "vX.Y.Z"`;
  5. envia o ramo e a marca: `git push origin main vX.Y.Z`;
  6. publica a versão no GitHub com as notas daquela seção do `CHANGELOG.md`: `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <seção> --verify-tag`;
  7. atualiza o plugin instalado na máquina: `claude plugin marketplace update cc-speaker` e `claude plugin update speak@cc-speaker`.
- Uma marca enviada nunca é movida nem apagada; um erro numa versão publicada se corrige com uma versão nova.
- Se uma verificação falhar, nada é enviado: corrige primeiro.
