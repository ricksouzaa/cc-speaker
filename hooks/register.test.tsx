import { expect, mock, test } from 'claude-code/testing'

// Nada aqui toca o motor, o áudio nem as pastas reais: `process.run` é respondido pelo teste, que guarda o estado
// do speak numa variável. O menu é montado no painel `speak` da superfície `terminal` e operado pela escolha nas listas.

type Opts = { autoinstall?: string; fail?: boolean; statusFails?: boolean; scope?: Record<string, string>; placed?: boolean; again?: string; surface?: string; init?: Record<string, unknown> }

async function setup($: any, on: any, opts: Opts = {}) {
  const ran: string[][] = []
  const opened: any[] = []
  const lines: (string | undefined)[] = []
  const toasts: string[] = []
  const logs: string[] = []
  const clock = mock.clock(on)
  on('ui.status', (_: unknown, e: any) => { lines.push(e.text); return { value: undefined } })
  on('ui.log', (_: unknown, e: any) => { logs.push(e.text); return { value: undefined } })
  on('ui.toast', (_: unknown, e: any) => { toasts.push(e.text); return { value: undefined } })
  const st: any = {
    on: true, mode: 'summary', size: 'medium', mic: 'wait', engine: true, voice: 'dora',
    scope: { on: 'all', mode: 'all', size: 'all', mic: 'all', ...(opts.scope ?? {}) },
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
    if (args[0] === 'autoinstall') return done(0, (opts.autoinstall ?? 'ready') + '\n')
    if (args[0] === 'status' && args[1] === '--json') return opts.statusFails || st.__fail ? done(1, '', 'sem estado') : done(0, JSON.stringify(st))
    if (args[0] === 'again') {
      if (opts.again === 'none') return done(1, '', 'voz: ainda não há uma resposta desta sessão para ouvir de novo\n')
      return done(0, args[1] === 'full' ? 'Lendo de novo a última resposta inteira.\n'
        : (opts.again === 'noline' ? 'Essa resposta não tinha resumo; vou ler a resposta inteira.\n' : '') + 'Lendo de novo o resumo da última resposta.\n')
    }
    if (args[0] === 'update') return done(opts.fail ? 1 : 0, opts.fail ? '' : 'atualizado de 0.8.1 para 0.9.0; rode /reload-plugins ou abra uma sessão nova para valer\n', opts.fail ? 'voz: `claude plugin update speak@cc-speaker` falhou (código 3):\nsem rede\n' : '')
    if (opts.fail) return done(1, '', 'voz: deu errado\n')
    if (args[0] === 'mode') st.mode = args[1]!
    if (args[0] === 'size') st.size = args[1]!
    if (args[0] === 'mic') st.mic = args[1]!
    if (args[0] === 'voice') st.voice = args[1]!
    if (args[0] === 'on' || args[0] === 'off') st.on = args[0] === 'on'
    return done(0, 'ok\n')
  })
  await $.session.start({ cwd: '/', surface: opts.surface ?? 'terminal', isInteractive: true })
  await clock.advance(0) // deixa o autoinstall do começo (em segundo plano) terminar
  return { ran, opened, st, lines, toasts, clock, logs }
}

const PANE = {
  plugin: 'speak',
  component: 'Pane',
  requestId: 'speak',
  surface: 'terminal',
  props: { title: 'Voz', isFocused: true, bodyColumns: 60, placement: 'inline', scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const

// Os comandos do speak que rodaram, sem as consultas de estado.
const changes = (ran: string[][]) => ran.filter(a => a[0] !== 'autoinstall' && !(a[0] === 'status' && a[1] === '--json')).map(a => a.join(' '))

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
    'mic play', 'mic auto all', 'voice alex', 'stop']
  for (const a of args) await $.command.run({ command: 'speak', args: a })
  expect(changes(ran)).toEqual(['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'mic play', 'mic auto all', 'voice alex', 'stop'])
})

test('status mostra o estado do speak e install roda direto', async ($, on) => {
  const { ran } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'status' })).text).toBe('ok')
  await $.command.run({ command: 'speak', args: 'install' })
  expect(changes(ran)).toEqual(['status', 'install'])
})

test('/speak update roda o speak update e devolve o texto dele, sem menu', async ($, on) => {
  const { ran, opened } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'update' })).text).toBe(
    'atualizado de 0.8.1 para 0.9.0; rode /reload-plugins ou abra uma sessão nova para valer')
  expect(changes(ran)).toEqual(['update'])
  expect(opened).toEqual([])
})

test('/speak update devolve o erro do speak', async ($, on) => {
  await setup($, on, { fail: true })
  expect((await $.command.run({ command: 'speak', args: 'update' })).text).toBe(
    'voz: `claude plugin update speak@cc-speaker` falhou (código 3):\nsem rede')
})

test('o rodapé do painel mostra a versão do plugin', async ($, on) => {
  await setup($, on, { init: { version: '0.9.0' } })
  const { ui } = await openMenu($)
  expect(await footer(ui)).toBe(HELP + ' · versão 0.9.0')
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
  expect(Object.keys(s)).toEqual(['where', 'power', 'mode', 'size', 'voice', 'mic'])
  expect(s.where.value).toBe('all')
  expect(s.power.value).toBe('on')
  expect(s.mode.value).toBe('summary')
  expect(s.size.value).toBe('medium')
  expect(s.voice.value).toBe('dora')
  expect(s.mic.value).toBe('wait')
  expect(s.mic.label).toMatch(/^Com o microfone em uso\s*$/)
  expect(s.mic.options.map((o: any) => o.label)).toEqual(['Espera', 'Toca', 'Toca nesta reunião'])
  expect(s.where.label).toMatch(/^Mudar em\s*$/)
  expect(s.where.options.map((o: any) => o.label)).toEqual(['Todas as sessões', 'Só nesta sessão'])
  expect(s.where.autoFocus).toBe(true)
  for (const k of ['power', 'mode', 'size', 'voice', 'mic']) expect(s[k].autoFocus).toBeUndefined()
  expect((await texts(ui, 'Button')).map((b: any) => b.props.label)).toEqual(['Resumo', 'Resposta inteira', 'Fechar'])
  expect((await texts(ui, 'Text')).map((t: any) => t.text.trim())).toContain('Ouvir de novo')
  expect(await footer(ui)).toBe(HELP)
  expect(changes(ran)).toEqual([])
  await ui.unmount()
})

test('o tamanho do resumo só aparece com a leitura em "só o resumo"', async ($, on) => {
  const { st } = await setup($, on)
  st.mode = 'full'
  const { ui } = await openMenu($)
  expect(Object.keys(await selects(ui))).toEqual(['where', 'power', 'mode', 'voice', 'mic'])
  expect((await texts(ui, 'Button')).map((b: any) => b.props.label)).toEqual(['Resumo', 'Resposta inteira', 'Fechar'])
  await ui.unmount()
})

test('escolher a leitura no painel esconde e mostra a linha do tamanho na hora', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'mode')
  expect(Object.keys(await selects(ui))).toContain('size')
  await ui.select({ key: 'mode', value: 'full' })
  expect(Object.keys(await selects(ui))).toEqual(['where', 'power', 'mode', 'voice', 'mic'])
  await ui.select({ key: 'mode', value: 'summary' })
  expect(Object.keys(await selects(ui))).toEqual(['where', 'power', 'mode', 'size', 'voice', 'mic'])
  expect(changes(ran)).toEqual(['mode full all', 'mode summary all'])
  await ui.unmount()
})

test('a linha do tamanho segue o valor da Leitura no alcance de "Mudar em" (só nesta sessão)', async ($, on) => {
  const { ran } = await setup($, on, { scope: { mode: 'session' } })
  const { ui } = await openMenu($, 'mode')
  await ui.select({ key: 'where', value: 'session' })
  await ui.select({ key: 'mode', value: 'full' })
  expect((await selects(ui)).mode.value).toBe('full')
  expect(Object.keys(await selects(ui))).not.toContain('size')
  expect(changes(ran)).toEqual(['mode full'])
  await ui.unmount()
})

test('/speak size com a leitura inteira abre o painel com o foco em Leitura; escrito com valor funciona em qualquer modo', async ($, on) => {
  const { ran, st } = await setup($, on)
  st.mode = 'full'
  const { ui } = await openMenu($, 'size')
  const s = await selects(ui)
  expect(s.size).toBeUndefined()
  expect(s.mode.autoFocus).toBe(true)
  expect(s.where.autoFocus).toBeUndefined()
  await ui.unmount()
  const r = await $.command.run({ command: 'speak', args: 'size large' })
  expect(changes(ran)).toEqual(['size large'])
  expect(st.size).toBe('large')
  expect((r as any).text).toMatch(/grande/i)
})

test('com o resumo, /speak size abre com o foco no tamanho', async ($, on) => {
  await setup($, on)
  const { ui } = await openMenu($, 'size')
  expect((await selects(ui)).size.autoFocus).toBe(true)
  await ui.unmount()
})

test('/speak again roda o speak again e diz o que vai tocar', async ($, on) => {
  const { ran, opened } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'again' })).text).toBe('Lendo de novo o resumo da última resposta.')
  expect((await $.command.run({ command: 'speak', args: 'again full' })).text).toBe('Lendo de novo a última resposta inteira.')
  await $.command.run({ command: 'speak', args: 'again summary' })
  expect(changes(ran)).toEqual(['again', 'again full', 'again summary'])
  expect(opened).toEqual([])
})

test('/speak again repete o aviso de quando não havia resumo', async ($, on) => {
  await setup($, on, { again: 'noline' })
  expect((await $.command.run({ command: 'speak', args: 'again summary' })).text).toBe(
    'Essa resposta não tinha resumo; vou ler a resposta inteira. Lendo de novo o resumo da última resposta.')
})

test('/speak again sem resposta guardada devolve o erro; escolha ou "all" inválidos mostram o uso', async ($, on) => {
  const { ran } = await setup($, on, { again: 'none' })
  expect((await $.command.run({ command: 'speak', args: 'again' })).text).toBe('voz: ainda não há uma resposta desta sessão para ouvir de novo')
  for (const args of ['again tudo', 'again full all', 'again summary full']) {
    expect((await $.command.run({ command: 'speak', args })).text).toMatch(/^Escreva a ação/)
  }
  expect(changes(ran)).toEqual(['again'])
})

test('a linha "Ouvir de novo" do painel toca na hora, diz a frase no rodapé e não guarda valor', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($)
  await ui.press({ key: 'again-summary' })
  expect(changes(ran)).toEqual(['again summary'])
  expect(await footer(ui)).toBe('Lendo de novo o resumo da última resposta.')
  await ui.press({ key: 'again-full' })
  expect(changes(ran)).toEqual(['again summary', 'again full'])
  expect(await footer(ui)).toBe('Lendo de novo a última resposta inteira.')
  expect(Object.keys(await selects(ui))).toEqual(['where', 'power', 'mode', 'size', 'voice', 'mic'])
  await ui.unmount()
})

test('na linha "Ouvir de novo", sem resposta guardada o rodapé mostra o erro', async ($, on) => {
  await setup($, on, { again: 'none' })
  const { ui } = await openMenu($)
  await ui.press({ key: 'again-full' })
  expect(await footer(ui)).toBe('voz: ainda não há uma resposta desta sessão para ouvir de novo')
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

test('/speak mic escolhe pela forma escrita e diz o que passou a valer', async ($, on) => {
  const { ran } = await setup($, on)
  const say = async (args: string) => (await $.command.run({ command: 'speak', args })).text
  expect(await say('mic wait')).toBe('A voz passa a esperar o microfone ficar livre nesta sessão.')
  expect(await say('mic play')).toBe('A voz passa a tocar mesmo com o microfone em uso nesta sessão, até você mudar.')
  expect(await say('mic auto all')).toBe(
    'A voz passa a tocar mesmo com o microfone em uso em todas as sessões, e volta a esperar quando o microfone ficar livre.')
  expect(await say('mic bobo')).toContain('/speak mic wait|play|auto')
  expect(changes(ran)).toEqual(['mic wait', 'mic play', 'mic auto all'])
})

test('a linha do microfone troca com "all" e avisa quando a voz toca na reunião', async ($, on) => {
  const { ran } = await setup($, on)
  const { ui } = await openMenu($, 'mic')
  expect((await selects(ui)).mic.autoFocus).toBe(true)
  const warning = 'Com o microfone em uso, a voz toca: ele pode captar a voz e quem está na reunião ouve.'
  expect((await texts(ui, 'Text')).map((t: any) => t.text)).not.toContain(warning)
  await ui.select({ key: 'mic', value: 'auto' })
  expect(changes(ran)).toEqual(['mic auto all'])
  expect((await selects(ui)).mic.value).toBe('auto')
  expect((await texts(ui, 'Text')).map((t: any) => t.text)).toContain(warning)
  await ui.select({ key: 'mic', value: 'wait' })
  expect((await texts(ui, 'Text')).map((t: any) => t.text)).not.toContain(warning)
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
  for (const k of ['where', 'power', 'size', 'voice', 'mic']) expect(s[k].label).not.toContain('só nesta sessão')
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
  await ui.select({ key: 'mode', value: 'full' })
  expect((await selects(ui)).mode.value).toBe('summary')
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
  for (const k of ['power', 'mode', 'size', 'voice', 'mic']) expect(s[k].value).toBeUndefined()
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

test('com o menu aberto o relógio só mexe no rodapé, e só quando o progresso muda', async ($, on) => {
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
  expect(s.mode.value).toBe('summary')
  expect(s.mode.autoFocus).toBe(true) // o pedido de foco vale em todo desenho; o anel que a pessoa moveu fica onde está
  expect(s.where.autoFocus).toBeUndefined()
  expect(reads()).toBeGreaterThan(1)
  await ui.unmount()
})

const WARN = '🔊 Voz não instalada: rode /speak install'
const statuses = (lines: (string | undefined)[]) => lines.filter(l => l !== undefined)

test('ao começar a sessão, o módulo roda o speak autoinstall antes de ler o estado', async ($, on) => {
  const { ran } = await setup($, on, { autoinstall: 'installing', init: { engine: false, installing: true } })
  expect(ran[0]).toEqual(['autoinstall'])
  expect(ran.findIndex(a => a[0] === 'status')).toBeGreaterThan(0)
  expect(ran.filter(a => a[0] === 'autoinstall').length).toBe(1)
})

test('o autoinstall não atrasa o registro do comando nem a sessão', async ($, on) => {
  let release: (() => void) | undefined
  const gate = new Promise<void>(r => { release = r })
  let registered = false
  on('command.register', () => { registered = true; return { value: { command: 'speak' } } })
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  on('process.run', async (_: unknown, e: any) => {
    if (e.argv[3] === 'autoinstall') await gate
    return { value: { exitCode: 0, stdout: 'installing\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true }) // volta sem esperar o autoinstall
  expect(registered).toBe(true)
  release?.()
})

test('sem uv: o aviso fixo diz que falta o uv e não some enquanto o motor faltar', async ($, on) => {
  const { lines, toasts, clock } = await setup($, on, { autoinstall: 'no-uv', init: { engine: false } })
  await clock.advance(60000)
  expect(statuses(lines).at(-1)).toBe('🔊 Voz não instalada: falta o uv; instale-o e rode /speak install')
  expect(lines.at(-1)).not.toBeUndefined()
  expect(toasts).toEqual([])
})

test('falhou antes: o aviso fixo manda rodar /speak install', async ($, on) => {
  const { lines, clock } = await setup($, on, { autoinstall: 'failed', init: { engine: false } })
  await clock.advance(60000)
  expect(lines.at(-1)).toBe(WARN)
})

test('instalação desligada (off) com o motor faltando: aviso fixo', async ($, on) => {
  const { lines, clock } = await setup($, on, { autoinstall: 'off', init: { engine: false } })
  await clock.advance(60000)
  expect(lines.at(-1)).toBe(WARN)
})

test('com o aviso fixo, o motor que aparece depois tira o aviso e traz o Voz pronta', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { autoinstall: 'failed', init: { engine: false } })
  await clock.advance(30000)
  expect(lines.at(-1)).toBe(WARN)
  st.engine = true // por exemplo, outra sessão instalou
  await clock.advance(10000)
  expect(lines.at(-1)).toBeUndefined()
  expect(toasts).toEqual(['Voz pronta'])
  const count = lines.length
  await clock.advance(30000)
  expect(lines.length).toBe(count) // o relógio foi cancelado
})

test('com o aviso fixo, /speak install mostra o progresso na hora e depois o Voz pronta', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { autoinstall: 'failed', init: { engine: false } })
  await clock.advance(30000)
  expect(lines.at(-1)).toBe(WARN)
  st.installing = true
  await $.command.run({ command: 'speak', args: 'install' })
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz...')
  st.engine = true
  st.installing = false
  await clock.advance(2000)
  expect(lines.at(-1)).toBeUndefined()
  expect(toasts).toEqual(['Voz pronta'])
})

test('com o aviso fixo, uma instalação que termina sem motor volta ao aviso', async ($, on) => {
  const { lines, toasts, clock, st } = await setup($, on, { autoinstall: 'failed', init: { engine: false } })
  await clock.advance(30000)
  st.installing = true
  await $.command.run({ command: 'speak', args: 'install' })
  await clock.advance(2000)
  expect(lines.at(-1)).toBe('🔊 Instalando a voz...')
  st.installing = false
  await clock.advance(2000)
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toMatch(/\/speak install/)
  expect(lines.at(-1)).toBe(WARN)
})

test('motor pronto no começo: sem aviso, e o relógio desiste como antes', async ($, on) => {
  const { lines, toasts, clock } = await setup($, on, { autoinstall: 'ready' })
  await clock.advance(30000)
  expect(statuses(lines)).toEqual([])
  expect(toasts).toEqual([])
})

test('autoinstall que falha ou responde algo estranho: cai no relógio de antes, sem aviso fixo', async ($, on) => {
  const { lines, clock } = await setup($, on, { autoinstall: 'lixo', init: { engine: false } })
  await clock.advance(30000)
  expect(statuses(lines)).toEqual([])
})

test('quando este módulo inicia a instalação, deixa uma linha escrita na conversa', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'installing started', init: { engine: false, installing: true } })
  expect(logs).toEqual(['Instalando a voz (cerca de 350 MB, alguns minutos). Acompanhe com /speak status.'])
})

test('se o gancho de começo já iniciou a instalação, o módulo não repete o aviso', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'installing', init: { engine: false, installing: true } })
  expect(logs).toEqual([])
})

test('autoinstall no-uv: nenhuma linha de instalação na conversa', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'no-uv', init: { engine: false } })
  expect(logs).toEqual([])
})

test('autoinstall failed: nenhuma linha de instalação na conversa', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'failed', init: { engine: false } })
  expect(logs).toEqual([])
})

test('autoinstall off: nenhuma linha de instalação na conversa', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'off', init: { engine: false } })
  expect(logs).toEqual([])
})

test('autoinstall ready: nenhuma linha de instalação na conversa', async ($, on) => {
  const { logs } = await setup($, on, { autoinstall: 'ready', init: { engine: false } })
  expect(logs).toEqual([])
})


// Botões "Resumo" e "Resposta inteira" abaixo da última resposta.
const MSG = { plugin: 'speak', component: 'AssistantMessage', surface: 'terminal' } as const
const msg = (text: string, extra: Record<string, unknown> = {}) => ({ ...MSG, props: { text, isFirstOfReply: true, ...extra } })

// O motor, por baixo do plugin: desenha o texto da mensagem.
function engineDraws(on: any) {
  on('turn.start', (_: unknown, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('ui.render', ($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{e.props.text}</Text>
  })
}
const finish = ($: any, answer: string, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer, durationMs: 1, isAborted: false, turnId: 't1', reason: 'answered', ...extra })
const buttons = async (ui: any) => (await ui.findAll({ type: 'Button' })).map((b: any) => b.props.label)

test('depois do turno, o último bloco ganha os dois botões; outro bloco fica sem nada', async ($, on) => {
  engineDraws(on)
  const { ran } = await setup($, on)
  await finish($, 'Feito.\n\n🔊 Resumo falado.')
  const last = await $.ui.mount(msg('Feito.\n\n🔊 Resumo falado.'))
  expect(await buttons(last)).toEqual(['[ ▶ Resumo ]', '[ ▶ Resposta inteira ]'])
  await last.press({ key: 'msg-again-summary' })
  await last.press({ key: 'msg-again-full' })
  expect(changes(ran)).toEqual(['again summary', 'again full'])
  const older = await $.ui.mount(msg('Uma resposta antiga.'))
  expect(await buttons(older)).toEqual([])
  const summary = await $.ui.mount(msg('Feito.\n\n🔊 Resumo falado.', { isSummary: true }))
  expect(await buttons(summary)).toEqual([])
})

test('sem a linha 🔊 só aparece "Resposta inteira"', async ($, on) => {
  engineDraws(on)
  const { ran } = await setup($, on)
  await finish($, 'Resposta sem resumo.')
  const ui = await $.ui.mount(msg('Resposta sem resumo.'))
  expect(await buttons(ui)).toEqual(['[ ▶ Resposta inteira ]'])
  await ui.press({ key: 'msg-again-full' })
  expect(changes(ran)).toEqual(['again full'])
})

test('durante um turno não há botões; no turno novo somem da resposta anterior', async ($, on) => {
  engineDraws(on)
  await setup($, on)
  await finish($, 'Primeira.\n🔊 um')
  expect(await buttons(await $.ui.mount(msg('Primeira.\n🔊 um')))).toHaveLength(2)
  await $.turn.start({ text: 'outra', turnId: 't2' })
  expect(await buttons(await $.ui.mount(msg('Primeira.\n🔊 um')))).toEqual([])
  expect(await buttons(await $.ui.mount(msg('Parcial')))).toEqual([])
  await finish($, 'Segunda.', { turnId: 't2' })
  expect(await buttons(await $.ui.mount(msg('Primeira.\n🔊 um')))).toEqual([])
  expect(await buttons(await $.ui.mount(msg('Segunda.')))).toEqual(['[ ▶ Resposta inteira ]'])
})

test('turno de subagente e turno interrompido não mexem nos botões', async ($, on) => {
  engineDraws(on)
  await setup($, on)
  await finish($, 'Final.')
  await finish($, 'Relatório do agente.', { agentId: 'a1', turnId: 't9' })
  expect(await buttons(await $.ui.mount(msg('Final.')))).toHaveLength(1)
  await finish($, 'Cortada.', { isAborted: true, reason: 'aborted', turnId: 't3' })
  expect(await buttons(await $.ui.mount(msg('Final.')))).toEqual([])
})
