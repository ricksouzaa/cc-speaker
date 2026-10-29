import { expect, test } from 'claude-code/testing'

// Nada aqui toca o motor, o áudio nem as pastas reais: `process.run` e a abertura do painel são respondidos pelo teste.
const PANE = {
  plugin: 'speak',
  component: 'Pane',
  requestId: 'speak',
  props: { title: 'Voz', isFocused: true, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

async function setup($: any, on: any, opts: { fail?: boolean; placed?: boolean } = {}) {
  const ran: string[][] = []
  const opened: any[] = []
  const st = { on: true, mode: 'full', size: 'medium', engine: true, voice: 'dora' }
  on('command.register', () => ({ value: { command: 'speak' } }))
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  on('ui.open', (_: unknown, e: any) => {
    opened.push(e)
    return opts.placed === false ? { value: { isPlaced: false, reason: 'sem superfície' } } : { value: { isPlaced: true } }
  })
  on('process.run', (_: unknown, e: any) => {
    const args = e.argv.slice(3) as string[]
    ran.push(args)
    const done = (exitCode: number, stdout: string, stderr = '') =>
      ({ value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } })
    if (args[0] === 'status' && args[1] === '--json') return done(0, JSON.stringify(st))
    if (opts.fail) return done(2, '', 'voz: deu errado\n')
    if (args[0] === 'mode') st.mode = args[1]!
    if (args[0] === 'size') st.size = args[1]!
    if (args[0] === 'voice') st.voice = args[1]!
    if (args[0] === 'on' || args[0] === 'off') st.on = args[0] === 'on'
    return done(0, 'ok\n')
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  return { ran, opened }
}

// Os comandos do speak que rodaram, sem as consultas de estado.
const changes = (ran: string[][]) => ran.filter(a => !(a[0] === 'status' && a[1] === '--json')).map(a => a.join(' '))

test('o comando /speak é registrado, imediato', async ($, on) => {
  let spec: any
  on('command.register', (_: unknown, e: any) => { spec = e; return { value: { command: 'speak' } } })
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(spec.name).toBe('speak')
  expect(spec.immediate).toBe(true)
})

test('escolha completa roda o speak certo, sem painel', async ($, on) => {
  const { ran, opened } = await setup($, on)
  const args = ['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop']
  for (const a of args) await $.command.run({ command: 'speak', args: a })
  expect(changes(ran)).toEqual(['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop'])
  expect(opened).toEqual([])
})

test('status mostra o estado do speak e install roda direto', async ($, on) => {
  const { ran } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'status' })).text).toBe('ok')
  await $.command.run({ command: 'speak', args: 'install' })
  expect(changes(ran)).toEqual(['status', 'install'])
})

test('/speak sozinho abre o painel com uma lista por ajuste, cada uma com o valor atual', async ($, on) => {
  const { opened } = await setup($, on)
  await $.command.run({ command: 'speak', args: '' })
  expect(opened[0]).toMatchObject({ id: 'speak', focus: true, closeOnEscape: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  for (const key of ['power', 'mode', 'size', 'voice', 'scope']) {
    expect(await ui.find({ key })).toBeDefined()
  }
  await ui.unmount()
})

test('escolher no painel roda o speak e redesenha; o alcance vira all', async ($, on) => {
  const { ran } = await setup($, on)
  await $.command.run({ command: 'speak', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.select({ key: 'mode', value: 'summary' })
  await ui.select({ key: 'scope', value: 'all' })
  await ui.select({ key: 'size', value: 'large' })
  await ui.select({ key: 'voice', value: 'santa' })
  await ui.select({ key: 'power', value: 'off' })
  expect(changes(ran)).toEqual(['mode summary', 'size large all', 'voice santa', 'off all'])
  expect((await ui.find({ type: 'Text', text: /desligada/ }))).toBeDefined()
  await ui.unmount()
})

test('/speak mode abre só a lista da leitura', async ($, on) => {
  await setup($, on)
  await $.command.run({ command: 'speak', args: 'voice' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ key: 'voice' })).toBeDefined()
  expect(await ui.find({ key: 'mode' })).toBeUndefined()
  expect(await ui.find({ key: 'scope' })).toBeUndefined()
  await ui.unmount()
})

test('painel que não abre devolve as opções em texto', async ($, on) => {
  await setup($, on, { placed: false })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('/speak voice')
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
