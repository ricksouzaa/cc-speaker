import { expect, test } from 'claude-code/testing'

// Nada aqui toca o motor, o áudio nem as pastas reais: `process.run` é respondido pelo teste, que guarda o estado
// do speak numa variável. O menu é montado no painel `speak` da superfície `terminal` e operado pelas teclas.

type Opts = { fail?: boolean; scope?: Record<string, string>; placed?: boolean; surface?: string }

async function setup($: any, on: any, opts: Opts = {}) {
  const ran: string[][] = []
  const opened: any[] = []
  const st: any = {
    on: true, mode: 'full', size: 'medium', engine: true, voice: 'dora',
    scope: { on: 'all', mode: 'all', size: 'all', ...(opts.scope ?? {}) },
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
    if (args[0] === 'status' && args[1] === '--json') return done(0, JSON.stringify(st))
    if (opts.fail) return done(1, '', 'voz: deu errado\n')
    if (args[0] === 'mode') st.mode = args[1]!
    if (args[0] === 'size') st.size = args[1]!
    if (args[0] === 'voice') st.voice = args[1]!
    if (args[0] === 'on' || args[0] === 'off') st.on = args[0] === 'on'
    return done(0, 'ok\n')
  })
  await $.session.start({ cwd: '/', surface: opts.surface ?? 'terminal', isInteractive: true })
  return { ran, opened, st }
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

async function lines(ui: any): Promise<string[]> {
  return (await ui.findAll({ type: 'Text', in: 'menu' })).map((t: any) => t.text as string)
}
const HELP = '↑↓ ajuste · ←→ valor · Esc fecha'

async function openMenu($: any, args = '') {
  const r = await $.command.run({ command: 'speak', args })
  const ui = await $.ui.mount(PANE)
  return { r, ui }
}

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

test('/speak sozinho abre o painel que fica aberto, com o foco em "Mudar em" e Todas as sessões', async ($, on) => {
  const { ran, opened } = await setup($, on)
  const { ui } = await openMenu($)
  expect(opened.length).toBe(1)
  expect(opened[0].id).toBe('speak')
  expect(opened[0].focus).toBe(true)
  expect(opened[0].closeOnEscape).toBe(true)
  const t = await lines(ui)
  expect(t.length).toBe(6)
  expect(t[0]).toMatch(/^❯ Mudar em\s+‹ Todas as sessões ›$/)
  expect(t[1]).toMatch(/^ {2}Voz\s+‹ Ligada ›$/)
  expect(t[2]).toMatch(/^ {2}Leitura\s+‹ Resposta inteira ›$/)
  expect(t[3]).toMatch(/^ {2}Tamanho do resumo\s+‹ Médio ›$/)
  expect(t[4]).toMatch(/^ {2}Voz de leitura\s+‹ Dora ›$/)
  expect(t[5]).toBe(HELP)
  expect(changes(ran)).toEqual([])
  await ui.unmount()
})

test('/speak mode abre com o foco em Leitura', async ($, on) => {
  await setup($, on)
  const { ui } = await openMenu($, 'mode')
  const t = await lines(ui)
  expect(t[0]).toMatch(/^ {2}Mudar em/)
  expect(t[2]).toMatch(/^❯ Leitura/)
  await ui.unmount()
})

test('baixo e direita na Voz mudam com "all" e o rodapé diz o que passou a valer', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.key({ key: 'down' })
  await ui.key({ key: 'right' })
  expect(changes(ran)).toEqual(['off all'])
  const t = await lines(ui)
  expect(t[1]).toMatch(/^❯ Voz\s+‹ Desligada ›$/)
  expect(t[5]).toBe('A voz está desligada em todas as sessões.')
  await ui.unmount()
})

test('direita em "Mudar em" não roda nada; depois a troca vale só nesta sessão, sem "all"', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.key({ key: 'right' })
  expect(changes(ran)).toEqual([])
  expect((await lines(ui))[0]).toMatch(/‹ Só nesta sessão ›$/)
  await ui.key({ key: 'down' })
  await ui.key({ key: 'down' })
  await ui.key({ key: 'right' })
  expect(changes(ran)).toEqual(['mode summary'])
  expect((await lines(ui))[5]).toBe('A voz passa a ler só o resumo nesta sessão.')
  await ui.unmount()
})

test('a voz de leitura nunca leva "all"', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'voice')
  await ui.key({ key: 'right' })
  expect(changes(ran)).toEqual(['voice alex'])
  expect((await lines(ui))[4]).toMatch(/‹ Alex ›$/)
  await ui.unmount()
})

test('a linha com campo próprio da sessão leva a marca "só nesta sessão"', async ($, on) => {
  await setup($, on, { scope: { mode: 'session' } })
  const { ui } = await openMenu($)
  const t = await lines(ui)
  expect(t[2]).toMatch(/‹ Resposta inteira ›\s+· só nesta sessão$/)
  for (const i of [0, 1, 3, 4]) expect(t[i]).not.toContain('só nesta sessão')
  await ui.unmount()
})

test('esquerda no primeiro valor vai ao último, e direita no último volta ao primeiro', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'size')
  await ui.key({ key: 'left' })
  await ui.key({ key: 'left' })
  await ui.key({ key: 'right' })
  expect(changes(ran)).toEqual(['size small all', 'size large all', 'size small all'])
  await ui.unmount()
})

test('cima na primeira linha vai à última', async ($, on) => {
  await setup($, on)
  const { ui } = await openMenu($)
  await ui.key({ key: 'up' })
  expect((await lines(ui))[4]).toMatch(/^❯ Voz de leitura/)
  await ui.unmount()
})

test('Enter não faz nada', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'mode')
  await ui.key({ key: 'return' })
  expect(changes(ran)).toEqual([])
  expect((await lines(ui))[2]).toMatch(/^❯ Leitura\s+‹ Resposta inteira ›$/)
  await ui.unmount()
})

test('speak com código 1 mostra o erro no rodapé e o valor lido de volta do estado', async ($, on) => {
  await setup($, on, { fail: true })
  const { ui } = await openMenu($, 'mode')
  await ui.key({ key: 'right' })
  const t = await lines(ui)
  expect(t[2]).toMatch(/‹ Resposta inteira ›$/)
  expect(t[5]).toBe('voz: deu errado')
  await ui.unmount()
})

test('"Mudar em" abre sempre em Todas as sessões, mesmo depois de trocada', async ($, on) => {
  await setup($, on)
  const first = await openMenu($)
  await first.ui.key({ key: 'right' })
  await first.ui.unmount()
  const { ui } = await openMenu($)
  expect((await lines(ui))[0]).toMatch(/‹ Todas as sessões ›$/)
  await ui.unmount()
})

test('mensagem de valor desconhecido não roda nada', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.post({ key: 'mode', value: 'x; rm' })
  await ui.post({ key: 'nada', value: 'on' })
  expect(changes(ran)).toEqual([])
  await ui.unmount()
})

test('painel que não abre responde em texto com a forma escrita', async ($, on) => {
  const { ran } = await setup($, on, { placed: false })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('/speak voice')
  expect(changes(ran)).toEqual([])
})

test('superfície sem Client responde em texto com a forma escrita', async ($, on) => {
  const { opened } = await setup($, on, { surface: 'vscode' })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('/speak voice')
  expect(opened).toEqual([])
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
