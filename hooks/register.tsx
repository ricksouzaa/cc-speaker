// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, abre o menu (painel `speak`, que já abre com o
// foco): uma lista nativa (`Select`) por linha e um botão Fechar; cada escolha roda o `bin/speak` na hora.
// A primeira linha, "Mudar em", só diz onde as próximas trocas são gravadas (todas as sessões ou só esta); abre sempre
// em "Todas as sessões" e trocá-la não roda nada. Responde sozinho, sem o modelo. Com a escolha escrita
// (/speak voice alex), roda direto, sem menu, e responde uma linha.
import type { EngineInterface, Register } from 'claude-code'

type Engine = EngineInterface
type Reply = { text?: string }
type State = {
  on: boolean; mode: string; size: string; voice: string; engine: boolean
  scope?: { on?: string; mode?: string; size?: string }
}

const MODES: Record<string, string> = { full: 'Resposta inteira', summary: 'Só o resumo' }
const SIZES: Record<string, string> = { small: 'Pequeno', medium: 'Médio', large: 'Grande' }
const VOICES: Record<string, string> = { dora: 'Dora (feminina)', alex: 'Alex (masculina)', santa: 'Santa (masculina)' }
const READERS: Record<string, string> = { dora: 'Dora', alex: 'Alex', santa: 'Santa' }
const POWER: Record<string, string> = { on: 'Ligada', off: 'Desligada' }
const USAGE =
  'Escreva a ação: /speak on, /speak off, /speak mode full|summary, /speak size small|medium|large, ' +
  '/speak voice dora|alex|santa, /speak status, /speak stop, /speak install ' +
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
    case 'voice':
      if (all) return { text: USAGE }
      return value ? runChoice($, 'voice', value, VOICES, []) : undefined
    case 'status':
    case 'stop':
    case 'install': {
      const r = await run($, body)
      if (!r.ok) return { text: r.out || 'O speak falhou.' }
      if (action === 'status') return { text: r.out }
      return { text: action === 'stop' ? 'A fala foi cortada e a fila esvaziada.' : r.out || 'Motor instalado.' }
    }
    default:
      return { text: `Não conheço "${action}". ${USAGE}` }
  }
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

type Key = 'where' | 'power' | 'mode' | 'size' | 'voice'
const ROWS: { key: Key; label: string; table: Record<string, string>; current: (s: State) => string; own: (s: State) => boolean }[] = [
  { key: 'where', label: 'Mudar em', table: WHERES, current: () => '', own: () => false },
  { key: 'power', label: 'Voz', table: POWER, current: s => (s.on ? 'on' : 'off'), own: s => s.scope?.on === 'session' },
  { key: 'mode', label: 'Leitura', table: MODES, current: s => s.mode, own: s => s.scope?.mode === 'session' },
  { key: 'size', label: 'Tamanho do resumo', table: SIZES, current: s => s.size, own: s => s.scope?.size === 'session' },
  { key: 'voice', label: 'Voz de leitura', table: READERS, current: s => s.voice, own: () => false },
]

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

// Tudo o que o desenho precisa, já lido: quem desenha não fala com o speak nem com o estado.
type Menu = {
  now: State | undefined; where: string; note: string; first: Key
  choose: (key: Key, value: string) => unknown; close: () => unknown
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
      <Button key="fechar" label="Fechar" onPress={m.close} />
      <Text dimColor>{m.note || (m.now ? HELP : UNREAD)}</Text>
    </Box>
  )
}

async function menuTree($: Engine, e: any): Promise<unknown> {
  if (!view) view = { now: await state($) }
  const focus = (await $.state.get(FOCUS)).value ?? 'where'
  return drawMenu($.ui.resolve(e), {
    now: view.now,
    where: (await $.state.get(STATE)).value ?? 'all',
    note: (await $.state.get(NOTE)).value ?? '',
    first: (ROWS.some(r => r.key === focus) ? focus : 'where') as Key,
    choose: (key, value) => enqueue(() => menuChange($, key, value)),
    close: () => $.ui.close({ id: PANE }),
  })
}

// Abre o menu com o foco na linha pedida; devolve falso quando ele não abre (então a resposta é em texto).
async function openMenu($: Engine, focus: Key): Promise<boolean> {
  view = undefined
  await $.state.set(STATE, 'all')
  await $.state.set(NOTE, '')
  await $.state.set(FOCUS, focus)
  return (await $.ui.open({ id: PANE, title: 'Voz', focus: true, closeOnEscape: true })).isPlaced
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'speak',
      description: 'Ajusta a voz que lê as respostas: ligar, modo, tamanho, voz',
      argumentHint: '[on|off|mode|size|voice|status|stop|install] [all]',
      immediate: true,
    })
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
