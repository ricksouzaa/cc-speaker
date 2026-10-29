// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, abre um painel com listas (setas movem, Enter
// escolhe, Esc fecha), como o /model; cada escolha roda o `bin/speak` na hora e redesenha com o valor novo. Responde
// sozinho, sem o modelo. Com a escolha escrita (/speak voice alex), roda direto e responde uma linha.
import type { EngineInterface, Register } from 'claude-code'

type Engine = EngineInterface
type Reply = { text?: string }
type State = { on: boolean; mode: string; size: string; voice: string; engine: boolean }
type View = 'all' | 'power' | 'mode' | 'size' | 'voice'

const PANE = 'speak'
const MODES: Record<string, string> = { full: 'Resposta inteira', summary: 'Só o resumo' }
const SIZES: Record<string, string> = { small: 'Pequeno', medium: 'Médio', large: 'Grande' }
const VOICES: Record<string, string> = { dora: 'Dora (feminina)', alex: 'Alex (masculina)', santa: 'Santa (masculina)' }
const POWER: Record<string, string> = { on: 'Ligada', off: 'Desligada' }
const SCOPES: Record<string, string> = { session: 'Só esta sessão', all: 'Todas as sessões' }
const USAGE =
  'Escreva a ação: /speak on, /speak off, /speak mode full|summary, /speak size small|medium|large, ' +
  '/speak voice dora|alex|santa, /speak status, /speak stop, /speak install ' +
  '(com "all" no fim, vale para todas as sessões).'
const VIEWS: Record<string, View> = { on: 'power', off: 'power', mode: 'mode', size: 'size', voice: 'voice' }

const options = (table: Record<string, string>) => Object.keys(table).map(value => ({ value, label: table[value]! }))
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

// Escrita completa: roda direto, sem painel. Devolve undefined quando falta a escolha (então abre o painel).
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

// O que o painel tem para mostrar quando não abre: as opções, em texto.
const fallback = (view: View) =>
  `Não consegui abrir o painel aqui. ${USAGE}` + (view === 'all' ? '' : '')

export const register: Register = on => {
  // Estado do painel: vive enquanto o módulo está carregado.
  let view: View = 'all'
  let all = false
  let note = ''
  let now: State | undefined

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
      view = (body[0] && VIEWS[body[0]]) || 'all'
      all = wantsAll
      note = ''
      now = await state($)
      const opened = await $.ui.open({ id: PANE, title: 'Voz', focus: true, closeOnEscape: true })
      $.ui.invalidate('ui.render')
      return opened.isPlaced ? {} : { text: fallback(view) }
    } catch (error) {
      return { text: `O speak falhou: ${String((error as { message?: unknown })?.message ?? error)}` }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Text } = elements
    // Onde não há Select (telas sem lista), o painel só aponta a forma escrita.
    if (!('Select' in elements)) return <Text>{USAGE}</Text>
    const { Select } = elements
    const tail = () => (all ? ['all'] : [])
    // Cada escolha roda na hora, guarda a frase do rodapé e pede o redesenho.
    const apply = (args: string[]) => {
      void (async () => {
        const r = await change($, args)
        note = r.text
        now = await state($)
        $.ui.invalidate('ui.render')
      })()
    }
    const rows: { key: string; label: string; table: Record<string, string>; value: string | undefined; pick: (v: string) => void; view: View }[] = [
      { key: 'power', label: 'Voz', table: POWER, value: now ? (now.on ? 'on' : 'off') : undefined,
        pick: v => apply([v, ...tail()]), view: 'power' },
      { key: 'mode', label: 'Leitura', table: MODES, value: now?.mode, pick: v => apply(['mode', v, ...tail()]), view: 'mode' },
      { key: 'size', label: 'Tamanho do resumo', table: SIZES, value: now?.size, pick: v => apply(['size', v, ...tail()]), view: 'size' },
      { key: 'voice', label: 'Voz de leitura', table: VOICES, value: now?.voice, pick: v => apply(['voice', v]), view: 'voice' },
    ]
    const shown = rows.filter(r => view === 'all' || r.view === view)
    const needsScope = shown.some(r => r.key !== 'voice')
    return (
      <Box flexDirection="column">
        {shown.map(r => (
          <Select key={r.key} label={r.label} options={options(r.table)} value={r.value}
            onSelect={(v: string) => r.pick(v)} />
        ))}
        {needsScope && (
          <Select key="scope" label="Vale para" options={options(SCOPES)} value={all ? 'all' : 'session'}
            onSelect={(v: string) => { all = v === 'all'; note = `Daqui em diante vale ${where(all)}.`; $.ui.invalidate('ui.render') }} />
        )}
        <Text dimColor>{note || 'Setas movem, Enter escolhe, Esc fecha.'}</Text>
      </Box>
    )
  })
}
