// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, abre o menu de setas (painel `speak`, desenhado
// por `menu.tsx`): cima e baixo mudam de linha, esquerda e direita o valor, e cada troca roda o `bin/speak` na hora.
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
async function change($: Engine, args: string[]): Promise<{ ok: boolean; text: string }> {
  const r = await run($, args)
  if (!r.ok) return { ok: false, text: r.out || 'O speak falhou.' }
  return { ok: true, text: said(args, await state($)) }
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
const ENTER_ALL = 'Todas as sessões'
const WHERES: Record<string, string> = { all: ENTER_ALL, session: 'Só nesta sessão' }

type Key = 'where' | 'power' | 'mode' | 'size' | 'voice'
const ROWS: { key: Key; label: string; table: Record<string, string>; current: (s: State) => string; own: (s: State) => boolean }[] = [
  { key: 'where', label: 'Mudar em', table: WHERES, current: () => '', own: () => false },
  { key: 'power', label: 'Voz', table: POWER, current: s => (s.on ? 'on' : 'off'), own: s => s.scope?.on === 'session' },
  { key: 'mode', label: 'Leitura', table: MODES, current: s => s.mode, own: s => s.scope?.mode === 'session' },
  { key: 'size', label: 'Tamanho do resumo', table: SIZES, current: s => s.size, own: s => s.scope?.size === 'session' },
  { key: 'voice', label: 'Voz de leitura', table: READERS, current: s => s.voice, own: () => false },
]

// As props do Client: as linhas com o valor em vigor lido do speak, o foco e a nota do rodapé.
async function menuProps($: Engine): Promise<unknown> {
  const now = await state($)
  const where = (await $.state.get(STATE)).value ?? 'all'
  const note = (await $.state.get(NOTE)).value ?? ''
  const focus = (await $.state.get(FOCUS)).value ?? 'where'
  return {
    focus,
    note,
    rows: ROWS.map(r => ({
      key: r.key,
      label: r.label,
      values: Object.keys(r.table).map(value => ({ value, label: r.table[value]! })),
      value: r.key === 'where' ? where : now ? r.current(now) : '',
      own: now ? r.own(now) : false,
    })),
  }
}

// Uma troca vinda do menu: "Mudar em" só guarda o alcance; o resto roda o speak (com `all` quando o alcance é todas
// as sessões, menos a voz de leitura, que é sempre geral) e guarda a frase, ou o erro, para o rodapé.
async function menuChange($: Engine, data: unknown): Promise<void> {
  const { key, value } = (data ?? {}) as { key?: unknown; value?: unknown }
  const row = ROWS.find(r => r.key === key)
  if (!row || typeof value !== 'string' || !(value in row.table)) return
  if (row.key === 'where') {
    await $.state.set(STATE, value as 'all' | 'session')
    await $.state.set(NOTE, '')
    return
  }
  const all = ((await $.state.get(STATE)).value ?? 'all') === 'all'
  const tail = all && row.key !== 'voice' ? ['all'] : []
  const args = row.key === 'power' ? [value, ...tail] : [row.key, value, ...tail]
  await $.state.set(NOTE, (await change($, args)).text)
}

// Abre o menu com o foco na linha pedida; devolve falso quando ele não abre (então a resposta é em texto).
async function openMenu($: Engine, focus: Key): Promise<boolean> {
  if (!(await $.session.surfaces()).includes('terminal')) return false
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

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Client } = $.ui.resolve(e) as any
    return <Client key="menu" module="./menu.tsx" props={await menuProps($)} />
  })

  on('ui.message', async ($, e) => {
    if (e.requestId !== PANE) return {}
    await menuChange($, e.data)
    return { props: await menuProps($) }
  })
}
