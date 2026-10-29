// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, abre o menu (painel `speak`, que já abre com o
// foco): uma lista nativa (`Select`) por linha, a linha "Ouvir de novo" (dois botões que tocam na hora) e um botão Fechar; cada escolha roda o `bin/speak` na hora.
// A primeira linha, "Mudar em", só diz onde as próximas trocas são gravadas (todas as sessões ou só esta); abre sempre
// em "Todas as sessões" e trocá-la não roda nada. Responde sozinho, sem o modelo. Com a escolha escrita
// (/speak voice alex), roda direto, sem menu, e responde uma linha.
import type { EngineInterface, Register, Timer } from 'claude-code'

type Engine = EngineInterface
type Reply = { text?: string }
type State = {
  version?: string
  on: boolean; mode: string; size: string; mic?: string; voice: string; engine: boolean
  scope?: { on?: string; mode?: string; size?: string; mic?: string }
  installing?: boolean
  install?: { fase?: string; arquivo?: string; feito?: number; total?: number } | null
}

const MODES: Record<string, string> = { full: 'Resposta inteira', summary: 'Só o resumo' }
const SIZES: Record<string, string> = { small: 'Pequeno', medium: 'Médio', large: 'Grande' }
const MICS: Record<string, string> = { wait: 'Espera', play: 'Toca', auto: 'Toca nesta reunião' }
const VOICES: Record<string, string> = { dora: 'Dora (feminina)', alex: 'Alex (masculina)', santa: 'Santa (masculina)' }
const READERS: Record<string, string> = { dora: 'Dora', alex: 'Alex', santa: 'Santa' }
const POWER: Record<string, string> = { on: 'Ligada', off: 'Desligada' }
const USAGE =
  'Escreva a ação: /speak on, /speak off, /speak mode full|summary, /speak size small|medium|large, /speak mic wait|play|auto, ' +
  '/speak voice dora|alex|santa, /speak again [summary|full], /speak status, /speak stop, /speak install, /speak update ' +
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

function stopWatch($: Engine) {
  watch?.cancel()
  watch = undefined
  watching = false
  live = undefined
  $.ui.status(undefined)
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
    case 'status':
    case 'stop':
    case 'install': {
      if (action === 'install') startWatch($)
      const r = await run($, body)
      if (!r.ok) return { text: r.out || 'O speak falhou.' }
      if (action === 'status') return { text: r.out }
      return { text: action === 'stop' ? 'A fala foi cortada e a fila esvaziada.' : r.out || 'Motor instalado.' }
    }
    default:
      return { text: `Não conheço "${action}". ${USAGE}` }
  }
}

// Ouvir de novo a última fala desta sessão (o speak diz a frase do que vai tocar, ou por que não tocou).
async function again($: Engine, which?: string): Promise<string> {
  const r = await run($, which ? ['again', which] : ['again'])
  return r.out.split('\n').map(l => l.trim()).filter(Boolean).join(' ') || (r.ok ? 'Pronto.' : 'O speak falhou.')
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

// "Ouvir de novo": toca na hora e guarda a frase (ou o erro) para o rodapé; a linha não guarda valor.
async function menuAgain($: Engine, which: string): Promise<void> {
  if (!(which in AGAINS)) return
  await $.state.set(NOTE, await again($, which))
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
      {ROWS.map(r => {
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
            <Button key={'again-' + v} label={AGAINS[v]!} onPress={() => m.again(v)} />
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
    first: (ROWS.some(r => r.key === focus) ? focus : 'where') as Key,
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

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'speak',
      description: 'Ajusta a voz que lê as respostas: ligar, modo, tamanho, microfone, voz; ouve de novo a última fala',
      argumentHint: '[on|off|mode|size|mic|voice|again|status|stop|install|update] [all]',
      immediate: true,
    })
    void kick($) // em segundo plano: não atrasa o registro da sessão
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
