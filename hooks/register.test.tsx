import { expect, mock, test } from 'claude-code/testing'

// Nada aqui toca o motor, o áudio nem as pastas reais: `process.run` é respondido pelo teste, que guarda o estado
// do speak numa variável. O menu é montado no painel `speak` da superfície `terminal` e operado pela escolha nas listas.

type Opts = { fail?: boolean; statusFails?: boolean; scope?: Record<string, string>; placed?: boolean; surface?: string; init?: Record<string, unknown> }

async function setup($: any, on: any, opts: Opts = {}) {
  const ran: string[][] = []
  const opened: any[] = []
  const lines: (string | undefined)[] = []
  const toasts: string[] = []
  const clock = mock.clock(on)
  on('ui.status', (_: unknown, e: any) => { lines.push(e.text); return { value: undefined } })
  on('ui.toast', (_: unknown, e: any) => { toasts.push(e.text); return { value: undefined } })
  const st: any = {
    on: true, mode: 'full', size: 'medium', engine: true, voice: 'dora',
    scope: { on: 'all', mode: 'all', size: 'all', ...(opts.scope ?? {}) },
    ...(opts.init ?? {}),
  }
  on('command.register', () => ({ value: { command: 'speak' } }))
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  on('session.surfaces', () => ({ value: [opts.surface ?? 'terminal'] }))
  on('ui.open', (_: unknown, e: any) => {
    opened.push(e)
    return { value: opts.placed === false ? { isPlaced: false, reason: 'sem lugar' } : { isPlaced: true } }
  })
  on('process.run', (_: unknown, e: any) => {
    const args = e.argv.slice(3) as string[]
    ran.push(args)
    const done = (exitCode: number, stdout: string, stderr = '') =>
      ({ value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } })
    if (args[0] === 'status' && args[1] === '--json') return opts.statusFails || st.__fail ? done(1, '', 'sem estado') : done(0, JSON.stringify(st))
    if (opts.fail) return done(1, '', 'voz: deu errado\n')
    if (args[0] === 'mode') st.mode = args[1]!
    if (args[0] === 'size') st.size = args[1]!
    if (args[0] === 'voice') st.voice = args[1]!
    if (args[0] === 'on' || args[0] === 'off') st.on = args[0] === 'on'
    return done(0, 'ok\n')
  })
  await $.session.start({ cwd: '/', surface: opts.surface ?? 'terminal', isInteractive: true })
  return { ran, opened, st, lines, toasts, clock }
}

const PANE = {
  plugin: 'speak',
  component: 'Pane',
  requestId: 'speak',
  surface: 'terminal',
  props: { title: 'Voz', isFocused: true, bodyColumns: 60, placement: 'inline', scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const

// Os comandos do speak que rodaram, sem as consultas de estado.
const changes = (ran: string[][]) => ran.filter(a => !(a[0] === 'status' && a[1] === '--json')).map(a => a.join(' '))

const HELP = 'Tab troca de linha · Enter escolhe o valor · Esc fecha'

async function openMenu($: any, args = '') {
  const r = await $.command.run({ command: 'speak', args })
  const ui = await $.ui.mount(PANE)
  return { r, ui }
}

const texts = async (ui: any, type: string): Promise<any[]> => ui.findAll({ type })
const footer = async (ui: any): Promise<string> => ((await texts(ui, 'Text')).at(-1) as any).text
const selects = async (ui: any): Promise<Record<string, any>> =>
  Object.fromEntries((await texts(ui, 'Select')).map((x: any) => [x.props.key, x.props]))

test('o comando /speak é registrado, imediato', async ($, on) => {
  let spec: any
  on('command.register', (_: unknown, e: any) => { spec = e; return { value: { command: 'speak' } } })
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(spec.name).toBe('speak')
  expect(spec.immediate).toBe(true)
})

test('escolha completa roda o speak certo, sem menu', async ($, on) => {
  const { ran } = await setup($, on)
  const args = ['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop']
  for (const a of args) await $.command.run({ command: 'speak', args: a })
  expect(changes(ran)).toEqual(['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop'])
})

test('status mostra o estado do speak e install roda direto', async ($, on) => {
  const { ran } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'status' })).text).toBe('ok')
  await $.command.run({ command: 'speak', args: 'install' })
  expect(changes(ran)).toEqual(['status', 'install'])
})

test('escrita completa não abre o menu', async ($, on) => {
  const { opened } = await setup($, on)
  await $.command.run({ command: 'speak', args: 'voice alex' })
  await $.command.run({ command: 'speak', args: 'status' })
  expect(opened).toEqual([])
})

test('/speak sozinho abre o painel com o foco, uma lista por linha e o botão Fechar', async ($, on) => {
  const { ran, opened } = await setup($, on)
  const { ui } = await openMenu($)
  expect(opened.length).toBe(1)
  expect(opened[0].id).toBe('speak')
  expect(opened[0].focus).toBe(true)
  expect(opened[0].closeOnEscape).toBe(true)
  const s = await selects(ui)
  expect(Object.keys(s)).toEqual(['where', 'power', 'mode', 'size', 'voice'])
  expect(s.where.value).toBe('all')
  expect(s.power.value).toBe('on')
  expect(s.mode.value).toBe('full')
  expect(s.size.value).toBe('medium')
  expect(s.voice.value).toBe('dora')
  expect(s.where.label).toMatch(/^Mudar em\s*$/)
  expect(s.where.options.map((o: any) => o.label)).toEqual(['Todas as sessões', 'Só nesta sessão'])
  expect(s.where.autoFocus).toBe(true)
  for (const k of ['power', 'mode', 'size', 'voice']) expect(s[k].autoFocus).toBeUndefined()
  expect((await texts(ui, 'Button')).length).toBe(1)
  expect(await footer(ui)).toBe(HELP)
  expect(changes(ran)).toEqual([])
  await ui.unmount()
})

test('/speak mode abre com o foco em Leitura', async ($, on) => {
  await setup($, on)
  const { ui } = await openMenu($, 'mode')
  const s = await selects(ui)
  expect(s.mode.autoFocus).toBe(true)
  expect(s.where.autoFocus).toBeUndefined()
  await ui.unmount()
})

test('abre também sem a superfície terminal', async ($, on) => {
  const { opened } = await setup($, on, { surface: 'vscode' })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r).toEqual({})
  expect(opened.length).toBe(1)
})

test('escolher na Voz roda com "all" e o rodapé diz o que passou a valer', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.select({ key: 'power', value: 'off' })
  expect(changes(ran)).toEqual(['off all'])
  expect((await selects(ui)).power.value).toBe('off')
  expect(await footer(ui)).toBe('A voz está desligada em todas as sessões.')
  await ui.unmount()
})

test('uma troca lê o estado uma vez só', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  const before = ran.length
  await ui.select({ key: 'mode', value: 'summary' })
  expect(ran.slice(before).map(a => a.join(' '))).toEqual(['mode summary all', 'status --json'])
  await ui.unmount()
})

test('"Mudar em" não roda nada; depois a troca vale só nesta sessão, sem "all"', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.select({ key: 'where', value: 'session' })
  expect(changes(ran)).toEqual([])
  expect((await selects(ui)).where.value).toBe('session')
  await ui.select({ key: 'mode', value: 'summary' })
  expect(changes(ran)).toEqual(['mode summary'])
  expect(await footer(ui)).toBe('A voz passa a ler só o resumo nesta sessão.')
  await ui.unmount()
})

test('a voz de leitura nunca leva "all"', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'voice')
  await ui.select({ key: 'voice', value: 'alex' })
  expect(changes(ran)).toEqual(['voice alex'])
  expect((await selects(ui)).voice.value).toBe('alex')
  await ui.unmount()
})

test('a linha com campo próprio da sessão leva a marca "só nesta sessão"', async ($, on) => {
  await setup($, on, { scope: { mode: 'session' } })
  const { ui } = await openMenu($)
  const s = await selects(ui)
  expect(s.mode.label).toContain('só nesta sessão')
  for (const k of ['where', 'power', 'size', 'voice']) expect(s[k].label).not.toContain('só nesta sessão')
  await ui.unmount()
})

test('duas escolhas seguidas rodam o speak uma depois da outra', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await Promise.all([ui.select({ key: 'mode', value: 'summary' }), ui.select({ key: 'size', value: 'large' })])
  expect(changes(ran)).toEqual(['mode summary all', 'size large all'])
  const order = ran.map(a => a[0])
  expect(order.slice(-4)).toEqual(['mode', 'status', 'size', 'status'])
  await ui.unmount()
})

test('speak com código 1 mostra o erro no rodapé e o valor lido de volta do estado', async ($, on) => {
  await setup($, on, { fail: true })
  const { ui } = await openMenu($, 'mode')
  await ui.select({ key: 'mode', value: 'summary' })
  expect((await selects(ui)).mode.value).toBe('full')
  expect(await footer(ui)).toBe('voz: deu errado')
  await ui.unmount()
})

test('"Mudar em" abre sempre em Todas as sessões, mesmo depois de trocada', async ($, on) => {
  await setup($, on)
  const first = await openMenu($)
  await first.ui.select({ key: 'where', value: 'session' })
  await first.ui.unmount()
  const { ui } = await openMenu($)
  expect((await selects(ui)).where.value).toBe('all')
  await ui.unmount()
})

test('valor desconhecido não roda nada', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.select({ key: 'mode', value: 'x; rm' })
  expect(changes(ran)).toEqual([])
  await ui.unmount()
})

test('quando o estado não pode ser lido, as linhas ficam vazias e o rodapé avisa', async ($, on) => {
  await setup($, on, { statusFails: true })
  const { ui } = await openMenu($)
  const s = await selects(ui)
  for (const k of ['power', 'mode', 'size', 'voice']) expect(s[k].value).toBeUndefined()
  expect(await footer(ui)).toBe('Não deu para ler o estado da voz.')
  await ui.unmount()
})

test('painel que não abre responde em texto com a forma escrita', async ($, on) => {
  const { ran } = await setup($, on, { placed: false })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('/speak voice')
  expect(changes(ran)).toEqual([])
})

test('erro do speak volta como texto', async ($, on) => {
  await setup($, on, { fail: true })
  const r = await $.command.run({ command: 'speak', args: 'voice zeca' })
  expect(r.text).toBe('voz: deu errado')
})

test('ação desconhecida explica as formas escritas', async ($, on) => {
  const { ran } = await setup($, on)
  const r = await $.command.run({ command: 'speak', args: 'dance' })
  expect(r.text).toContain('/speak voice')
  expect(changes(ran)).toEqual([])
})

test('sem instalação à vista, o relógio desiste depois de alguns toques e não mostra nada', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on)
  st.engine = false
  await clock.advance(30000)
  expect(lines.filter(l => l !== undefined)).toEqual([])
  expect(toasts).toEqual([])
})

test('instalando: linha de status com o progresso; ao fim, limpa e avisa Voz pronta', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, {
    init: { engine: false, installing: true, install: { fase: 'dependências' } },
  })
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz: dependências')
  st.install = { fase: 'baixando', arquivo: 'kokoro-v1.0.onnx', feito: 252698624, total: 325532232 }
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz: 78% (253 de 326 MB)')
  st.engine = true
  st.installing = false
  st.install = null
  await clock.advance(2000)
  expect(lines.at(-1)).toBeUndefined()
  expect(toasts).toEqual(['Voz pronta'])
  const count = lines.length
  await clock.advance(20000)
  expect(lines.length).toBe(count) // o relógio foi cancelado
})

test('instalação que termina sem motor avisa a falha e o /speak install', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { init: { engine: false, installing: true } })
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz...')
  st.installing = false
  await clock.advance(2000)
  expect(lines.at(-1)).toBeUndefined()
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toMatch(/\/speak install/)
})

test('o relógio começa também ao rodar /speak install', async ($, on) => {
  const { lines, clock, st } = await setup($, on)
  await clock.advance(30000) // o relógio do começo já desistiu: motor pronto
  st.engine = false
  st.installing = true
  await $.command.run({ command: 'speak', args: 'install' })
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz...')
})

test('o rodapé do menu mostra o progresso enquanto instala', async ($, on) => {
  const { st } = await setup($, on)
  st.engine = false
  st.installing = true
  st.install = { fase: 'baixando', arquivo: 'kokoro-v1.0.onnx', feito: 1000000, total: 4000000 }
  const { ui } = await openMenu($)
  expect(await footer(ui)).toBe('🔊 Instalando a voz: 25% (1 de 4 MB)')
  await ui.unmount()
})

test('leitura falha no meio da instalação tenta de novo, sem aviso de falha', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { init: { engine: false, installing: true } })
  await clock.advance(2000)
  st.__fail = true
  await clock.advance(4000) // três leituras falhas seguidas
  expect(lines.at(-1)).toBe('🔊 Instalando a voz...')
  expect(toasts).toEqual([])
  st.__fail = false
  st.engine = true
  st.installing = false
  await clock.advance(2000)
  expect(toasts).toEqual(['Voz pronta'])
})

test('leituras falhas seguidas: desiste em silêncio e limpa a linha', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { init: { engine: false, installing: true } })
  await clock.advance(2000)
  st.__fail = true
  await clock.advance(30000)
  expect(lines.at(-1)).toBeUndefined()
  expect(toasts).toEqual([])
})

test('com o menu aberto o relógio só mexe no rodapé, e só quando o progresso muda; o foco não volta', async ($, on) => {
  const { ran, clock, st } = await setup($, on, {
    init: { engine: false, installing: true, install: { fase: 'baixando', arquivo: 'kokoro-v1.0.onnx', feito: 1000000, total: 4000000 } },
  })
  const { ui } = await openMenu($, 'mode')
  expect((await selects(ui)).mode.autoFocus).toBe(true)
  const reads = () => ran.filter(a => a[0] === 'status').length
  await clock.advance(2000)
  expect(await footer(ui)).toBe('🔊 Instalando a voz: 25% (1 de 4 MB)')
  st.install = { fase: 'baixando', arquivo: 'kokoro-v1.0.onnx', feito: 2000000, total: 4000000 }
  st.mode = 'summary' // um valor que o relógio não deve trazer para as linhas
  await clock.advance(2000)
  expect(await footer(ui)).toBe('🔊 Instalando a voz: 50% (2 de 4 MB)')
  const s = await selects(ui)
  expect(s.mode.value).toBe('full')
  for (const k of Object.keys(s)) expect(s[k].autoFocus).toBeUndefined()
  expect(reads()).toBeGreaterThan(1)
  await ui.unmount()
})
