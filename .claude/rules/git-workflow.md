# Fluxo do git (cc-speaker)

Projeto solo: só o Ricardo tem permissão de escrita no repositório.

- Os commits vão direto na `main`, sem pedido de mudança e sem linha de atribuição. Nada de tags.
- Todo ajuste no projeto termina com a versão nova e o envio, sem esperar pedido:
  1. sobe a versão em `.claude-plugin/plugin.json` e no teste da versão em `tests/test_speak.py`: correção ou texto, o último número (0.7.1 → 0.7.2); funcionalidade nova, o do meio (0.7.2 → 0.8.0);
  2. roda as verificações: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests`, `claude plugin test .` e `claude plugin validate .`;
  3. faz o commit e o `git push origin main`;
  4. atualiza o plugin instalado na máquina: `claude plugin marketplace update cc-speaker` e `claude plugin update speak@cc-speaker`.
- Se uma verificação falhar, nada é enviado: corrige primeiro.
