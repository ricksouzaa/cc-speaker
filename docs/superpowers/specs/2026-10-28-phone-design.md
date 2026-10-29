# Modo celular: desenho

Data: 28/10/2026. Pedido do Ricardo: quando está no controle remoto (dirigindo, fora do computador), ligar um modo em que o computador não toca nada e cada resposta vira um mp3 que chega ao celular para ele dar o play. Respeita o modo (inteira ou resumo) e o tamanho do resumo, igual à fala local. Ele quer testar já; as decisões abaixo são minhas, para a revisão dele.

## Limite que molda o desenho

Só o modelo envia arquivo ao usuário (ferramenta SendUserFile); os ganchos não. Por isso o gancho de fim de resposta gera o mp3 e devolve ao Claude um pedido de continuar (`decision: block`), e o Claude envia o arquivo numa volta curta. Custa uma volta por resposta. A alternativa (o Claude gerar o mp3 do resumo antes de terminar) foi descartada: não serve para o modo inteiro e depende de o modelo lembrar.

## Comportamento

- `speak phone on|off [all]`: a saída da sessão (campo `output` do arquivo da sessão: `phone` ou `speaker`) ou, com `all` ou fora de sessão, o arquivo geral `~/.config/claude-speak/output` e todas as sessões, no mesmo padrão de `mode` e `size`. Padrão `speaker`. Variável `CLAUDE_SPEAK_OUTPUT` ganha de tudo. `speak status` mostra a saída ("alto-falante" ou "celular").
- O modo celular só age com a voz ligada na sessão (`speak on`), como a fala local.
- `speak say -` com saída `phone`: não toca nada; escolhe o texto como hoje (modo e tamanho), sintetiza em primeiro plano um mp3 (Kokoro, voz e velocidade em vigor, gravado com soundfile, que já grava MP3 com a libsndfile 1.2 do motor) em `~/.local/state/claude-speak/phone/<sessão>-<hora>.mp3`, apaga os mp3 com mais de um dia e imprime o caminho. Sem texto, sem motor ou com a voz desligada: não imprime nada.
- Com `CLAUDE_SPEAK_STOP_ACTIVE=1` (o gancho repassa o `stop_hook_active` da entrada) e saída `phone`, `speak say -` não faz nada: é a volta em que o Claude acabou de enviar o arquivo; assim não há laço nem mp3 da mensagem de envio. Com saída `speaker`, nada muda.
- `hooks/speak-stop.py`: quando `speak say -` imprime um caminho de mp3 que existe, o gancho imprime `{"decision": "block", "reason": "<pedido>"}` e sai 0. Pedido, em português: o áudio desta resposta está em <caminho>; envie esse arquivo ao humano com a ferramenta SendUserFile (carregue-a pelo ToolSearch se precisar), sem legenda longa, e termine sem escrever mais nada; se a ferramenta não existir nesta sessão, diga em uma frase que o modo celular só funciona no controle remoto e sugira `speak phone off`. O tempo de espera do gancho passa de 4 s para 300 s só nesse caminho (a síntese de uma resposta inteira leva minutos); no caminho do alto-falante segue igual.
- Regra (`rules/speak.md`): uma linha nova: quando o humano pedir para ouvir no celular, ou parar de mandar para o celular, rodar `speak phone on` ou `speak phone off` (com `all` como nos outros); depois de um pedido `speak:` do gancho de fim, enviar o arquivo e não escrever mais nada. A lista dos comandos de barra ganha `/speak:phone`.
- `/speak:phone [on|off] [all]`: com argumento, roda direto; sem argumento, menu de setas como `/speak:size` (saída: "Celular (mp3 pelo controle remoto)" e "Alto-falante do computador", com " (atual)"; alcance: esta sessão ou todas). Confirma em uma frase. `disable-model-invocation: true`.
- README: o comando e uma frase do que ele faz e custa.

## Verificação

Testes sem áudio e sem tocar as pastas reais: `phone on/off` por sessão e geral, variável, status; `say -` em modo celular não toca e imprime caminho (síntese falsa); com `CLAUDE_SPEAK_STOP_ACTIVE=1` não faz nada; limpeza dos mp3 antigos; gancho imprime o bloqueio só quando há caminho, e nada no modo alto-falante; comando de barra só para o humano. Versão 0.2.0. Fim a fim: com o Ricardo no controle remoto.
