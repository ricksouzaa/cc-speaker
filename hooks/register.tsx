// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, abre o menu (painel `speak`, que já abre com o
// foco): uma lista nativa (`Select`) por linha, a linha "Ouvir de novo" (dois botões que tocam na hora) e um botão Fechar; cada escolha roda o `bin/speak` na hora.
// A primeira linha, "Mudar em", só diz onde as próximas trocas são gravadas (todas as sessões ou só esta); abre sempre
// em "Todas as sessões" e trocá-la não roda nada. Responde sozinho, sem o modelo. Com a escolha escrita
// (/speak voice alex), roda direto, sem menu, e responde uma linha.
// Também mostra, na linha de status de todas as sessões, quem está falando (lido de state/speech.json, sem abrir processo),
// e troca o rótulo do botão que deu o play por Pausar/Continuar (/speak pause, /speak resume).
import type { EngineInterface, Register, Timer } from 'claude-code'

type Engine = EngineInterface
type Reply = { text?: string }
type State = {
  version?: string
  on: boolean; mode: string; size: string; mic?: string; voice: string; engine: boolean
  scope?: { on?: string; mode?: string; size?: string; mic?: string }
  installing?: boolean
  install?: { fase?: string; arquivo?: string; feito?: number; total?: number } | null
  session?: string | null; stateDir?: string
  speaking?: Speech | null; paused?: Speech[]
}
// Uma fala, como o speak a anota em state/speech.json: a sessão dona, a pasta dela e o modo (summary ou full).
type Speech = { pid: number; session: string; dir: string; how: string; waiting?: number }
type Heard = { playing: Speech | null; paused: Speech[] }

const MODES: Record<string, string> = { full: 'Resposta inteira', summary: 'Só o resumo' }
const SIZES: Record<string, string> = { small: 'Pequeno', medium: 'Médio', large: 'Grande' }
const MICS: Record<string, string> = { wait: 'Espera', play: 'Toca', auto: 'Toca nesta reunião' }
const VOICES: Record<string, string> = { dora: 'Dora (feminina)', alex: 'Alex (masculina)', santa: 'Santa (masculina)' }
const READERS: Record<string, string> = { dora: 'Dora', alex: 'Alex', santa: 'Santa' }
const POWER: Record<string, string> = { on: 'Ligada', off: 'Desligada' }
const USAGE =
  'Escreva a ação: /speak on, /speak off, /speak mode full|summary, /speak size small|medium|large, /speak mic wait|play|auto, ' +
  '/speak voice dora|alex|santa, /speak again [summary|full], /speak pause, /speak resume, /speak status, /speak stop, ' +
  '/speak install, /speak update ' +
  '(com "all" no fim, vale para todas as sessões).'
const where = (all: boolean) => (all ? 'em todas as sessões' : 'nesta sessão')
const speakArgv = ($: Engine, args: string[]) => ['python3', '-I', `${$.plugin.root}/bin/speak`, ...args]

async function run($: Engine, args: string[]) {
  const r = await $.process.run(speakArgv($, args), { timeoutMs: 600000 })
  return { ok: r.exitCode === 0, out: (r.exitCode === 0 ? r.stdout : r.stderr || r.stdout).trim() }
}

async function state($: Engine): Promise<State | undefined> {
  try {
    const r = await run($, ['status', '--json'])
    return r.ok ? (JSON.parse(r.out) as State) : undefined
  } catch {
    return undefined
  }
}

// O andamento da instalação do motor, em uma linha: `78% (253 de 326 MB)`, `dependências` ou vazio (instalando, sem dado).
function progress(s: State | undefined): string {
  const p = s?.install
  if (!p) return ''
  if (p.fase !== 'baixando' || !p.total) return p.fase === 'dependências' ? 'dependências' : ''
  const mb = (n: number) => Math.round(n / 1e6)
  return `${Math.min(100, Math.round((100 * (p.feito ?? 0)) / p.total))}% (${mb(p.feito ?? 0)} de ${mb(p.total)} MB)`
}
// Por que o motor não está se instalando, segundo `speak autoinstall` (a regra única do início automático).
type Why = 'ready' | 'installing' | 'no-uv' | 'failed' | 'off'
const WHYS: string[] = ['ready', 'installing', 'no-uv', 'failed', 'off']
// O aviso fixo da linha de status quando nada vai instalar o motor sozinho.
const missingLine = (why: Why) =>
  why === 'no-uv'
    ? '🔊 Voz não instalada: falta o uv; instale-o e rode /speak install'
    : '🔊 Voz não instalada: rode /speak install'
const isInstalling = (s: State | undefined) => !!s && !s.engine && (!!s.install || !!s.installing)
const installLine = (s: State | undefined) => `🔊 Instalando a voz${progress(s) ? ': ' + progress(s) : '...'}`

// A linha de status sob o campo de texto enquanto o motor se instala. O relógio só roda enquanto houver instalação
// (ou nos primeiros segundos da sessão, à espera do gancho que a inicia) e é cancelado ao fim.
const WATCH_MS = 2000
const WATCH_FAILS = 5 // leituras falhas seguidas antes de desistir
const WATCH_GRACE = 5 // consultas sem instalação à vista antes de desistir, se nunca se viu uma
const WARN_EVERY = 5 // com o aviso fixo na tela, lê o estado a cada 5 toques (10 s)
let watch: Timer | undefined
let watching = false
let hurry = false // um /speak install com o relógio já rodando: a próxima leitura não espera
let live: State | undefined // a última leitura do relógio, só para o progresso do rodapé
let footLine = '' // a linha de progresso já desenhada no rodapé
let installShowing = false // a linha de status está com a instalação do motor: ela vence a do aviso de fala

function stopWatch($: Engine) {
  watch?.cancel()
  watch = undefined
  watching = false
  live = undefined
  installShowing = false
  shownSpeech = undefined // a linha foi limpa: o aviso de fala, se houver, volta a ser desenhado
  $.ui.status(undefined)
  paintSpeech($)
}

// `why` vem do `speak autoinstall`: com `no-uv`, `failed` ou `off` e o motor faltando, o relógio não desiste em
// silêncio; deixa o aviso fixo na linha de status até o motor ficar pronto ou a sessão acabar.
function startWatch($: Engine, why?: Why) {
  if (watching) {
    hurry = true
    return
  }
  watching = true
  const warn = why === 'no-uv' || why === 'failed' || why === 'off' ? missingLine(why) : ''
  let seen = false
  let idle = 0
  let fails = 0
  let busy = false
  let laps = 0
  let shown = '' // o aviso fixo já desenhado
  const tick = async () => {
    if (busy || !watching) return
    if (warn && !seen && !hurry && laps++ % WARN_EVERY !== 0) return
    hurry = false
    busy = true
    try {
      const now = await state($)
      if (!watching) return
      if (!now) { // leitura falha: tenta de novo; depois de várias seguidas desiste em silêncio
        if (++fails >= WATCH_FAILS) stopWatch($)
        return
      }
      fails = 0
      if (isInstalling(now)) {
        seen = true
        shown = ''
        const line = installLine(now)
        installShowing = true
        $.ui.status(line)
        // O menu aberto só troca o progresso do rodapé, e só quando o texto muda; as linhas não são tocadas.
        if (view && line !== footLine) {
          footLine = line
          $.ui.invalidate('ui.render')
        }
        live = now
        return
      }
      if (warn && !now.engine) { // nada instala o motor: o aviso fica
        if (seen) { // uma instalação que começou depois (/speak install) e terminou sem motor
          seen = false
          $.ui.toast('A instalação da voz não terminou; rode /speak install', { timeoutMs: 8000 })
        }
        if (shown !== warn) {
          shown = warn
          installShowing = true
          $.ui.status(warn)
        }
        return
      }
      if (!seen && !now.engine && ++idle <= WATCH_GRACE) return
      stopWatch($)
      if (seen || warn) {
        $.ui.toast(
          now.engine ? 'Voz pronta' : 'A instalação da voz não terminou; rode /speak install',
          { timeoutMs: 8000 },
        )
      }
    } finally {
      busy = false
    }
  }
  watch = $.clock.every(WATCH_MS, () => void tick())
  void tick()
}

// O aviso de quem fala e os botões Pausar/Continuar. O relógio lê `state/speech.json` (o speak o mantém) com
// `$.fs.read`: nenhuma volta abre processo. O caminho da pasta e a chave desta sessão vêm de UMA leitura de
// `speak status --json` no começo da sessão. Só quando o arquivo muda é que o desenho é invalidado.
const SPEECH_MS = 500
const SPEECH_TRIES = 5 // leituras do estado que falham antes de desistir do aviso
const SPEECH_RETRY = 20 // voltas entre uma tentativa e outra (10 s)
const SPEECH_CHECK = 20 // voltas entre as conferências por `speak status --json` onde não há /proc (10 s)
let speechClock: Timer | undefined
let speechBusy = false
let speechFile = '' // state/speech.json, absoluto; vazio até a primeira leitura do estado
let me = '' // a chave desta sessão, como o speak a chama
let tries = 0
let wait = 0 // voltas até a próxima tentativa
let check = 0
let hasProc: boolean | undefined
let heard: Heard = { playing: null, paused: [] }
let heardKey = ''
let shownSpeech: string | undefined // a última linha de status do aviso de fala

const folderOf = (x: Speech) => (x.dir || '').replace(/\/+$/, '').split('/').pop() || ''
const mine = (x: Speech | null | undefined) => !!x && !!me && x.session === me

function speechLine(h: Heard): string | undefined {
  const ownPaused = h.paused.some(mine)
  if (h.playing) {
    if (mine(h.playing)) return '🔊 falando agora'
    const other = folderOf(h.playing) ? `🔊 falando: ${folderOf(h.playing)}` : '🔊 outra sessão está falando'
    return ownPaused ? `${other} · ⏸ sua fala pausada` : other
  }
  return ownPaused ? '⏸ fala pausada' : undefined
}

// Desenha a linha de aviso na linha de status, a menos que a instalação do motor a esteja usando.
function paintSpeech($: Engine) {
  if (installShowing) return
  const line = speechLine(heard)
  if (line === shownSpeech) return
  shownSpeech = line
  $.ui.status(line)
}

// O que o botão de cada modo faz agora: pausar a fala desta sessão que toca nesse modo, continuar a que está pausada
// nesse modo, ou tocar de novo a última resposta.
type Role = 'play' | 'pause' | 'continue'
function role(which: string): Role {
  if (mine(heard.playing) && heard.playing!.how === which) return 'pause'
  if (heard.paused.some(x => mine(x) && x.how === which)) return 'continue'
  return 'play'
}
const labelOf = (which: string, plain: string) => {
  const r = role(which)
  return r === 'pause' ? '⏸ Pausar' : r === 'continue' ? '▶ Continuar' : plain
}

function parseHeard(raw: string): Heard {
  const empty: Heard = { playing: null, paused: [] }
  try {
    const data = JSON.parse(raw)
    const ok = (x: any): x is Speech => !!x && typeof x === 'object' && Number.isInteger(x.pid)
    return {
      playing: ok(data?.playing) ? data.playing : null,
      paused: Array.isArray(data?.paused) ? data.paused.filter(ok) : [],
    }
  } catch {
    return empty
  }
}

// O que está de pé de verdade: no Linux, o processo da fala existe em /proc; sem /proc (Mac), vale o arquivo e, de tempos
// em tempos, uma conferência pelo `speak status --json`, que também limpa o arquivo.
async function speechTick($: Engine): Promise<void> {
  if (speechBusy) return
  speechBusy = true
  try {
    if (!speechFile) {
      if (tries >= SPEECH_TRIES || wait-- > 0) return
      const s = await state($)
      if (!s?.stateDir) {
        wait = SPEECH_RETRY
        if (++tries >= SPEECH_TRIES) { speechClock?.cancel(); speechClock = undefined }
        return
      }
      speechFile = `${s.stateDir}/speech.json`
      me = s.session ?? ''
    }
    let raw = ''
    try { raw = String(await $.fs.read(speechFile)) } catch { raw = '' }
    let now = parseHeard(raw)
    if (now.playing || now.paused.length > 0) {
      if (hasProc === undefined) hasProc = await $.fs.exists('/proc/self').catch(() => false)
      if (hasProc) {
        const live = async (x: Speech) => await $.fs.exists(`/proc/${x.pid}`).catch(() => true)
        const playing = now.playing && (await live(now.playing)) ? now.playing : null
        const paused: Speech[] = []
        for (const x of now.paused) if (await live(x)) paused.push(x)
        now = { playing, paused }
      } else if (check++ % SPEECH_CHECK === 0) {
        const s = await state($)
        if (s) now = { playing: s.speaking ?? null, paused: s.paused ?? [] }
      }
    }
    const key = JSON.stringify([me, now.playing, now.paused])
    if (key === heardKey) return
    heardKey = key
    heard = now
    paintSpeech($)
    $.ui.invalidate('ui.render')
  } finally {
    speechBusy = false
  }
}

function startSpeech($: Engine) {
  speechClock?.cancel()
  speechFile = ''
  me = ''
  tries = 0
  wait = 0
  check = 0
  heard = { playing: null, paused: [] }
  heardKey = ''
  shownSpeech = undefined
  speechClock = $.clock.every(SPEECH_MS, () => void speechTick($))
  void speechTick($)
}

// Começa a instalação do motor (a mesma regra do gancho de começo da sessão; ver `speak autoinstall`) e liga o
// relógio. Ao ativar o plugin no meio de uma sessão, o Claude Code roda este módulo, mas não o gancho de comando
// SessionStart; sem isto nada iniciaria a instalação. Se a sessão começou normalmente, o gancho já iniciou e a
// resposta é `installing`: o `autoinstall` olha a trava install.lock (e uma segunda trava só dele, que serializa os
// dois), então nunca saem dois `speak install`; e o `install` espera a trava mesmo que saíssem.
async function kick($: Engine) {
  let why: Why | undefined
  try {
    const r = await $.process.run(speakArgv($, ['autoinstall']), { timeoutMs: 30000 })
    const [word = '', extra] = r.exitCode === 0 ? r.stdout.trim().split(/\s+/) : []
    if (WHYS.includes(word)) why = word as Why
    // Só quem iniciou a instalação avisa (`installing started`): se o gancho de começo da sessão já a iniciou, o
    // aviso dele (systemMessage) já está na tela. O `ui.log` é uma linha na conversa, que não some como o toast.
    if (word === 'installing' && extra === 'started') $.ui.log(INSTALLING_NOTE)
  } catch {
    why = undefined
  }
  startWatch($, why)
}

const INSTALLING_NOTE = 'Instalando a voz (cerca de 350 MB, alguns minutos). Acompanhe com /speak status.'

const cap = (word: string) => word.charAt(0).toUpperCase() + word.slice(1)

// Uma frase em português do que passou a valer, a partir do comando que rodou.
function said(args: string[], after: State | undefined): string {
  const all = args[args.length - 1] === 'all'
  const [cmd, value] = args
  switch (cmd) {
    case 'on': return `A voz está ligada ${where(all)}.`
    case 'off': return `A voz está desligada ${where(all)}.`
    case 'mode':
      return value === 'full'
        ? `A voz passa a ler a resposta inteira ${where(all)}.`
        : `A voz passa a ler só o resumo ${where(all)}.`
    case 'size': return `O resumo falado passa a ser ${(SIZES[value ?? ''] ?? '').toLowerCase()}, ${where(all)}.`
    case 'mic':
      return value === 'wait'
        ? `A voz passa a esperar o microfone ficar livre ${where(all)}.`
        : value === 'play'
          ? `A voz passa a tocar mesmo com o microfone em uso ${where(all)}, até você mudar.`
          : `A voz passa a tocar mesmo com o microfone em uso ${where(all)}, e volta a esperar quando o microfone ficar livre.`
    case 'voice': return `A voz agora é a ${cap(after?.voice ?? value ?? '')}, em todas as sessões.`
    default: return 'Pronto.'
  }
}

// Roda uma mudança (on, off, mode, size, voice) e devolve a frase, ou a mensagem de erro do speak.
// Lê o estado uma vez, depois da mudança, e o devolve para quem quiser redesenhar.
async function change($: Engine, args: string[]): Promise<{ ok: boolean; text: string; after: State | undefined }> {
  const r = await run($, args)
  const after = await state($)
  if (!r.ok) return { ok: false, text: r.out || 'O speak falhou.', after }
  return { ok: true, text: said(args, after), after }
}

// Escrita completa: roda direto, sem menu. Devolve undefined quando falta a escolha (então abre o menu).
async function direct($: Engine, body: string[], all: boolean): Promise<Reply | undefined> {
  const [action, value, ...extra] = body
  if (extra.length > 0) return { text: USAGE }
  const tail = all ? ['all'] : []
  switch (action) {
    case 'on':
    case 'off':
      return value ? { text: USAGE } : { text: (await change($, [action, ...tail])).text }
    case 'mode':
      return value ? runChoice($, 'mode', value, MODES, tail) : undefined
    case 'size':
      return value ? runChoice($, 'size', value, SIZES, tail) : undefined
    case 'mic':
      return value ? runChoice($, 'mic', value, MICS, tail) : undefined
    case 'voice':
      if (all) return { text: USAGE }
      return value ? runChoice($, 'voice', value, VOICES, []) : undefined
    case 'again':
      if (all || extra.length > 0 || (value && value !== 'summary' && value !== 'full')) return { text: USAGE }
      return { text: await again($, value) }
    case 'update': {
      // Atualiza o plugin (até dois comandos do claude, com prazo de 120 s cada); a nova versão só vale depois do
      // /reload-plugins, que o módulo não consegue disparar.
      const r = await run($, body)
      return { text: r.out || (r.ok ? 'Pronto.' : 'O speak falhou.') }
    }
    case 'pause':
    case 'resume': {
      if (all || value) return { text: USAGE }
      const text = await speechCommand($, action)
      void speechTick($)
      return { text }
    }
    case 'status':
    case 'stop':
    case 'install': {
      if (action === 'install') startWatch($)
      const r = await run($, body)
      if (!r.ok) return { text: r.out || 'O speak falhou.' }
      if (action === 'status') return { text: r.out }
      if (action === 'stop') void speechTick($)
      return { text: action === 'stop' ? 'A fala foi cortada, a fila esvaziada e as pausadas encerradas.' : r.out || 'Motor instalado.' }
    }
    default:
      return { text: `Não conheço "${action}". ${USAGE}` }
  }
}

// Ouvir de novo a última fala desta sessão (o speak diz a frase do que vai tocar, ou por que não tocou).
async function again($: Engine, which?: string): Promise<string> {
  return oneLine(await run($, which ? ['again', which] : ['again']))
}
const oneLine = (r: { ok: boolean; out: string }) =>
  r.out.split('\n').map(l => l.trim()).filter(Boolean).join(' ') || (r.ok ? 'Pronto.' : 'O speak falhou.')

// Pausar ou continuar a fala (o speak diz a frase, ou por que não deu).
async function speechCommand($: Engine, cmd: string): Promise<string> {
  return oneLine(await run($, [cmd]))
}

async function runChoice($: Engine, cmd: string, value: string, valid: Record<string, string>, tail: string[]) {
  // O speak valida e explica o erro; só a lista de valores conhecidos evita mandar lixo.
  if (!(value in valid) && cmd !== 'voice') return { text: USAGE }
  return { text: (await change($, [cmd, value, ...tail])).text }
}

const STATE = { plugin: 'speak', key: 'where' } as const
const NOTE = { plugin: 'speak', key: 'note' } as const
const FOCUS = { plugin: 'speak', key: 'focus' } as const
const PANE = 'speak'
const ALL_LABEL = 'Todas as sessões'
const WHERES: Record<string, string> = { all: ALL_LABEL, session: 'Só nesta sessão' }
const OWN = '· só nesta sessão'
const HELP = 'Tab troca de linha · Enter escolhe o valor · Esc fecha'
const UNREAD = 'Não deu para ler o estado da voz.'

const AGAIN_LABEL = 'Ouvir de novo'
const AGAINS: Record<string, string> = { summary: 'Resumo', full: 'Resposta inteira' }

type Key = 'where' | 'power' | 'mode' | 'size' | 'voice' | 'mic'
const ROWS: { key: Key; label: string; table: Record<string, string>; current: (s: State) => string; own: (s: State) => boolean }[] = [
  { key: 'where', label: 'Mudar em', table: WHERES, current: () => '', own: () => false },
  { key: 'power', label: 'Voz', table: POWER, current: s => (s.on ? 'on' : 'off'), own: s => s.scope?.on === 'session' },
  { key: 'mode', label: 'Leitura', table: MODES, current: s => s.mode, own: s => s.scope?.mode === 'session' },
  { key: 'size', label: 'Tamanho do resumo', table: SIZES, current: s => s.size, own: s => s.scope?.size === 'session' },
  { key: 'voice', label: 'Voz de leitura', table: READERS, current: s => s.voice, own: () => false },
  { key: 'mic', label: 'Com o microfone em uso', table: MICS, current: s => s.mic ?? 'wait', own: s => s.scope?.mic === 'session' },
]
// A linha do tamanho só aparece com a leitura em "só o resumo": na resposta inteira o tamanho não é usado. Vale o
// valor que a linha Leitura mostra (o do alcance de "Mudar em"); sem estado lido, todas as linhas aparecem.
const shown = (key: Key, now: State | undefined): boolean => !(key === 'size' && now?.mode === 'full')
const MIC_WARNING = 'Com o microfone em uso, a voz toca: ele pode captar a voz e quem está na reunião ouve.'

// O estado da voz lido para o desenho: vazio ao abrir (o desenho lê), e trocado a cada mudança pela leitura que a
// própria mudança já fez, para não ler duas vezes. `now` indefinido é "não deu para ler".
let view: { now: State | undefined } | undefined

// As trocas rodam em fila: duas escolhas seguidas rodam o speak uma depois da outra, nunca juntas.
let queue: Promise<unknown> = Promise.resolve()
const enqueue = (job: () => Promise<void>): Promise<unknown> => (queue = queue.then(job).catch(() => undefined))

// Uma troca vinda do menu: "Mudar em" só guarda o alcance; o resto roda o speak (com `all` quando o alcance é todas
// as sessões, menos a voz de leitura, que é sempre geral) e guarda a frase, ou o erro, para o rodapé.
async function menuChange($: Engine, key: Key, value: string): Promise<void> {
  const row = ROWS.find(r => r.key === key)
  if (!row || !(value in row.table)) return
  if (row.key === 'where') {
    await $.state.set(STATE, value as 'all' | 'session')
    await $.state.set(NOTE, '')
  } else {
    const all = ((await $.state.get(STATE)).value ?? 'all') === 'all'
    const tail = all && row.key !== 'voice' ? ['all'] : []
    const args = row.key === 'power' ? [value, ...tail] : [row.key, value, ...tail]
    const done = await change($, args)
    view = { now: done.after }
    await $.state.set(NOTE, done.text)
  }
  $.ui.invalidate('ui.render')
}

// "Ouvir de novo": toca na hora e guarda a frase (ou o erro) para o rodapé; a linha não guarda valor. Enquanto a fala
// desta sessão toca nesse modo, o mesmo botão pausa; pausada, continua (ver `role`).
async function menuAgain($: Engine, which: string): Promise<void> {
  if (!(which in AGAINS)) return
  const r = role(which)
  await $.state.set(NOTE, r === 'play' ? await again($, which) : await speechCommand($, r === 'pause' ? 'pause' : 'resume'))
  await speechTick($) // o botão troca de rótulo na hora, sem esperar o relógio
  $.ui.invalidate('ui.render')
}

// Tudo o que o desenho precisa, já lido: quem desenha não fala com o speak nem com o estado.
type Menu = {
  now: State | undefined; install: State | undefined; where: string; note: string; first: Key
  choose: (key: Key, value: string) => unknown; again: (which: string) => unknown; close: () => unknown
}

// O desenho do painel, isolado: trocar o formato do menu é trocar só esta função.
function drawMenu(el: any, m: Menu) {
  const { Box, Text, Select, Button } = el
  const width = Math.max(...ROWS.map(r => r.label.length)) + 2
  return (
    <Box flexDirection="column">
      {ROWS.filter(r => shown(r.key, m.now)).map(r => {
        const value = r.key === 'where' ? m.where : m.now ? r.current(m.now) : ''
        const own = m.now ? r.own(m.now) : false
        return (
          <Select
            key={r.key}
            label={r.label.padEnd(width) + (own ? OWN + ' ' : '')}
            options={Object.keys(r.table).map(v => ({ value: v, label: r.table[v]! }))}
            value={value || undefined}
            autoFocus={r.key === m.first ? true : undefined}
            onSelect={(v: string) => m.choose(r.key, v)}
          />
        )
      })}
      <Box flexDirection="row">
        <Text>{AGAIN_LABEL.padEnd(width)}</Text>
        {Object.keys(AGAINS).map(v => (
          <Box key={v} marginRight={2}>
            <Button key={'again-' + v} label={labelOf(v, AGAINS[v]!)} onPress={() => m.again(v)} />
          </Box>
        ))}
      </Box>
      <Button key="fechar" label="Fechar" onPress={m.close} />
      {m.now && (m.now.mic === 'play' || m.now.mic === 'auto') ? <Text dimColor>{MIC_WARNING}</Text> : null}
      <Text dimColor>{m.note || (isInstalling(m.install) ? installLine(m.install) : m.now ? HELP + (m.now.version ? ` · versão ${m.now.version}` : '') : UNREAD)}</Text>
    </Box>
  )
}

async function menuTree($: Engine, e: any): Promise<unknown> {
  if (!view) view = { now: await state($) }
  const focus = (await $.state.get(FOCUS)).value ?? 'where'
  const progressNow = live ?? view.now
  footLine = installLine(progressNow)
  return drawMenu($.ui.resolve(e), {
    now: view.now,
    install: progressNow,
    where: (await $.state.get(STATE)).value ?? 'all',
    note: (await $.state.get(NOTE)).value ?? '',
    // o foco pedido numa linha que não aparece (o tamanho, na resposta inteira) vai para a linha Leitura
    first: (ROWS.some(r => r.key === focus && shown(r.key, view!.now)) ? focus : focus === 'size' ? 'mode' : 'where') as Key,
    choose: (key, value) => enqueue(() => menuChange($, key, value)),
    again: which => enqueue(() => menuAgain($, which)),
    close: () => $.ui.close({ id: PANE }),
  })
}

// Abre o menu com o foco na linha pedida; devolve falso quando ele não abre (então a resposta é em texto).
async function openMenu($: Engine, focus: Key): Promise<boolean> {
  view = undefined
  live = undefined
  await $.state.set(STATE, 'all')
  await $.state.set(NOTE, '')
  await $.state.set(FOCUS, focus)
  return (await $.ui.open({ id: PANE, title: 'Voz', focus: true, closeOnEscape: true })).isPlaced
}

// Botões abaixo da última resposta. `lastAnswer` é o texto final do último turno que fechou (turn.complete); fica vazio
// enquanto um turno corre (turn.start) e no começo da sessão. O bloco é o último quando o texto dele é igual a esse
// texto: o motor não diz qual bloco é o último, e o texto final é o que sobrou de mais estável. Se uma resposta
// antiga tiver texto idêntico (ex.: "Pronto."), ela mostra os botões também; é o preço de não varrer a conversa.
let lastAnswer = ''
const hasSummaryLine = (text: string) =>
  text.split('\n').some(l => l.trim().replace(/^[>*_ ]+/, '').startsWith('🔊'))

function drawAgainButtons(el: any, withSummary: boolean, press: (which: string) => unknown) {
  const { Box, Button } = el
  return (
    <Box flexDirection="row">
      {Object.keys(AGAINS)
        .filter(v => v === 'full' || withSummary)
        .map(v => (
          <Box key={'box-' + v} marginRight={2}>
            <Button key={'msg-again-' + v} label={labelOf(v, `▶ ${AGAINS[v]}`)} onPress={() => press(v)} />
          </Box>
        ))}
    </Box>
  )
}

export const register: Register = on => {
  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined && lastAnswer) {
      lastAnswer = ''
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      lastAnswer = e.isAborted ? '' : (e.answer ?? '').trim()
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  // Todas as outras mensagens passam direto: só uma comparação de texto antes do `next`.
  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    if (!lastAnswer || e.props.isSummary || e.props.text.trim() !== lastAnswer) return next(e)
    const drawn = await next(e)
    const { Box } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        {drawn}
        {drawAgainButtons($.ui.resolve(e), hasSummaryLine(lastAnswer), which => enqueue(() => menuAgain($, which)))}
      </Box>
    )
  })

  on('session.start', async ($, e, next) => {
    lastAnswer = ''
    await $.command.register({
      name: 'speak',
      description: 'Ajusta a voz que lê as respostas: ligar, modo, tamanho, microfone, voz; ouve de novo, pausa e continua a fala',
      argumentHint: '[on|off|mode|size|mic|voice|again|pause|resume|status|stop|install|update] [all]',
      immediate: true,
    })
    void kick($) // em segundo plano: não atrasa o registro da sessão
    startSpeech($)
    return next(e)
  })

  on('command.run', { command: 'speak' }, async ($, e) => {
    try {
      const words = e.args.trim().split(/\s+/).filter(Boolean)
      const wantsAll = words[words.length - 1] === 'all'
      const body = wantsAll ? words.slice(0, -1) : words
      if (body.length > 0) {
        const done = await direct($, body, wantsAll)
        if (done) return done
      }
      const focus = (body[0] ?? 'where') as Key
      return (await openMenu($, focus)) ? {} : { text: USAGE }
    } catch (error) {
      return { text: `O speak falhou: ${String((error as { message?: unknown })?.message ?? error)}` }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => menuTree($, e))
}
