#!/usr/bin/env bash
# Roda DENTRO do contêiner (chamado por instalacao-limpa.sh). Não use fora dele.
set -u
MODO="${1:-auto}"
[ -f /.dockerenv ] || { echo "FALHOU: este roteiro só roda dentro do contêiner" >&2; exit 1; }
PRAZO=1200  # segundos para a instalação inteira (20 min)

echo "-- Instalando o plugin a partir de /plugin"
if claude plugin marketplace add /plugin && claude plugin install speak@cc-speaker; then
    METODO="claude plugin marketplace add + claude plugin install (sem login)"
    RAIZ="$(ls -d "$HOME"/.claude/plugins/cache/cc-speaker/speak/*/ 2> /dev/null | head -1)"
    RAIZ="${RAIZ%/}"
    DADOS="$HOME/.claude/plugins/data/speak-cc-speaker"
else
    echo "-- A instalação pelo Claude Code não funcionou sem login; copiando o plugin para o lugar"
    METODO="cópia do plugin para ~/.claude/plugins/cache (a instalação pelo claude não funcionou)"
    RAIZ="$HOME/.claude/plugins/cache/cc-speaker/speak/copia"
    DADOS="$HOME/.claude/plugins/data/speak-cc-speaker"
    mkdir -p "$RAIZ" && cp -r /plugin/bin /plugin/lib /plugin/hooks /plugin/.claude-plugin "$RAIZ"/
fi
[ -n "$RAIZ" ] && [ -f "$RAIZ/hooks/speak-start.py" ] || { echo "FALHOU: plugin não encontrado em '$RAIZ'" >&2; exit 1; }
echo "-- Método: $METODO"
echo "-- Raiz do plugin: $RAIZ"

if [ "$MODO" = visual ]; then
    echo "-- Plugin instalado. Rode: claude"
    exec bash
fi

export CLAUDE_PLUGIN_ROOT="$RAIZ" CLAUDE_PLUGIN_DATA="$DADOS"
ESTADO="$DADOS/state"
FALHAS=()
falhou() { FALHAS+=("$1"); echo "   FALHA: $1"; }

echo "-- Motor antes: $(python3 -I "$RAIZ/bin/speak" status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("engine =", d["engine"])')"

echo "-- Rodando o gancho de começo como o Claude Code roda"
SAIDA="$(printf '%s' '{"hook_event_name":"SessionStart","source":"startup","session_id":"teste-limpo"}' \
    | python3 -I "$RAIZ/hooks/speak-start.py")"
echo "$SAIDA"
if printf '%s' "$SAIDA" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert "instalando a voz" in d["systemMessage"], d["systemMessage"]
'; then
    echo "   ok: a saída é JSON com systemMessage de instalação"
else
    falhou "a saída do gancho não é JSON com systemMessage de instalação"
fi

echo "-- Acompanhando a instalação (status --json a cada 2 s, prazo ${PRAZO}s)"
INICIO=$SECONDS
VISTAS=0; SUBIU=0; ULT=-1; PCT_VISTO=0; LOG_CRESCEU=0; LOG_ANT=-1; PRIMEIRA_LINHA=""
while [ $((SECONDS - INICIO)) -lt "$PRAZO" ]; do
    JS="$(python3 -I "$RAIZ/bin/speak" status --json)"
    LEIT="$(printf '%s' "$JS" | python3 -c '
import json, sys
d = json.load(sys.stdin)
i = d.get("install") or {}
print(int(bool(d["engine"])), i.get("feito", -1), i.get("total", 0), i.get("fase", "-"))')"
    set -- $LEIT
    PRONTO=$1; FEITO=$2; TOTAL=$3; FASE=$4
    TAM=$(stat -c %s "$ESTADO/install.log" 2> /dev/null || echo 0)
    echo "   t=$((SECONDS - INICIO))s motor=$PRONTO fase=$FASE feito=$FEITO total=$TOTAL log=${TAM}B"
    if [ "$PRONTO" = 0 ] && [ "$FASE" = baixando ]; then
        VISTAS=$((VISTAS + 1))
        [ "$TOTAL" -gt 0 ] && PCT_VISTO=$((PCT_VISTO + 1))
        [ "$ULT" -ge 0 ] && [ "$FEITO" -gt "$ULT" ] && SUBIU=$((SUBIU + 1))
        ULT=$FEITO
    fi
    if [ "$PRONTO" = 0 ] && [ "$LOG_ANT" -ge 0 ] && [ "$TAM" -gt "$LOG_ANT" ]; then LOG_CRESCEU=$((LOG_CRESCEU + 1)); fi
    LOG_ANT=$TAM
    [ "$PRONTO" = 1 ] && break
    sleep 2
done

[ "$PRONTO" = 1 ] || falhou "o motor não ficou pronto em ${PRAZO}s"
[ "$SUBIU" -ge 2 ] || falhou "os bytes não subiram durante o download (subidas vistas: $SUBIU)"
[ "$PCT_VISTO" -ge 2 ] || falhou "a porcentagem não apareceu (leituras com total: $PCT_VISTO)"
[ "$LOG_CRESCEU" -ge 1 ] || falhou "o install.log não cresceu durante a instalação"
[ ! -e "$ESTADO/install.progress" ] || falhou "install.progress continua depois do fim"
FIM="$(python3 -I "$RAIZ/bin/speak" status 2>&1)"
echo "-- speak status no fim:"; echo "$FIM"
printf '%s' "$FIM" | grep -q 'motor: instalado em' || falhou "o status não diz instalado"
echo "-- install.log (últimas linhas):"; tail -n 15 "$ESTADO/install.log" 2> /dev/null

echo
echo "== Resumo: leituras com download=$VISTAS, bytes subiram $SUBIU vez(es), porcentagem vista $PCT_VISTO vez(es), log cresceu em $LOG_CRESCEU leitura(s), tempo $((SECONDS - INICIO))s, método: $METODO"
if [ "${#FALHAS[@]}" -gt 0 ]; then
    echo "== FALHOU:"; printf '   - %s\n' "${FALHAS[@]}"
    exit 1
fi
echo "== PASSOU: aviso na tela, progresso subindo, log linha a linha e motor pronto."
