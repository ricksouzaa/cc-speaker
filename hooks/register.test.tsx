import { expect, test } from 'claude-code/testing'

// Nada aqui toca o motor, o áudio nem as pastas reais: `process.run` e as caixas de escolha (`$.ui.ask`, que o motor
// levanta como uma chamada da ferramenta AskUserQuestion) são respondidas pelo teste.

async function setup($: any, on: any, opts: { fail?: boolean; answers?: (string | undefined)[] } = {}) {
  const ran: string[][] = []
  const asked: { question: string; header: string; labels: string[] }[] = []
  const answers = [...(opts.answers ?? [])]
  const st = { on: true, mode: 'full', size: 'medium', engine: true, voice: 'dora' }
  on('command.register', () => ({ value: { command: 'speak' } }))
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
  // Cada caixa tira a próxima resposta da fila; `undefined` é o Esc (a chamada é recusada).
  on('tool.call', (_: unknown, e: any) => {
    const q = e.questions[0]
    asked.push({ question: q.question, header: q.header, labels: q.options.map((o: any) => o.label) })
    const answer = answers.shift()
    if (answer === undefined) return { deny: 'dispensada' }
    return { result: { questions: e.questions, answers: { [q.question]: answer } } }
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
  return { ran, asked }
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

test('escolha completa roda o speak certo, sem caixa', async ($, on) => {
  const { ran, asked } = await setup($, on)
  const args = ['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop']
  for (const a of args) await $.command.run({ command: 'speak', args: a })
  expect(changes(ran)).toEqual(['on', 'off all', 'mode summary', 'mode full all', 'size large', 'size small all',
    'voice alex', 'stop'])
  expect(asked).toEqual([])
})

test('status mostra o estado do speak e install roda direto', async ($, on) => {
  const { ran } = await setup($, on)
  expect((await $.command.run({ command: 'speak', args: 'status' })).text).toBe('ok')
  await $.command.run({ command: 'speak', args: 'install' })
  expect(changes(ran)).toEqual(['status', 'install'])
})

const ALCANCE = 'Vale para quais sessões?'

test('/speak sozinho pergunta o ajuste, o valor e o alcance, e roda o speak uma vez só', async ($, on) => {
  const { ran, asked } = await setup($, on, { answers: ['Leitura', 'Só o resumo', 'Todas as sessões'] })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(asked.map(a => a.question)).toEqual(['O que quer ajustar?', 'O que a voz lê?', ALCANCE])
  expect(asked.map(a => a.header)).toEqual(['Voz', 'Leitura', 'Alcance'])
  expect(asked[0]!.labels).toEqual(['Ligar ou desligar', 'Leitura', 'Tamanho do resumo', 'Voz de leitura'])
  expect(asked[2]!.labels).toEqual(['Só esta sessão', 'Todas as sessões'])
  expect(changes(ran)).toEqual(['mode summary all'])
  expect(r.text).toBe('A voz passa a ler só o resumo em todas as sessões.')
})

test('ligar ou desligar e tamanho rodam com o alcance escolhido', async ($, on) => {
  const { ran } = await setup($, on, {
    answers: ['Ligar ou desligar', 'Desligada', 'Só esta sessão', 'Tamanho do resumo', 'Grande', 'Todas as sessões'],
  })
  await $.command.run({ command: 'speak', args: '' })
  await $.command.run({ command: 'speak', args: '' })
  expect(changes(ran)).toEqual(['off', 'size large all'])
})

test('a voz de leitura não pergunta o alcance', async ($, on) => {
  const { ran, asked } = await setup($, on, { answers: ['Voz de leitura', 'Santa (masculina)'] })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(asked.map(a => a.question)).not.toContain(ALCANCE)
  expect(changes(ran)).toEqual(['voice santa'])
  expect(r.text).toContain('Santa')
})

test('/speak size pula a primeira caixa', async ($, on) => {
  const { ran, asked } = await setup($, on, { answers: ['Pequeno', 'Só esta sessão'] })
  await $.command.run({ command: 'speak', args: 'size' })
  expect(asked.map(a => a.header)).toEqual(['Tamanho', 'Alcance'])
  expect(changes(ran)).toEqual(['size small'])
})

test('/speak mode all pula também o alcance', async ($, on) => {
  const { ran, asked } = await setup($, on, { answers: ['Resposta inteira'] })
  await $.command.run({ command: 'speak', args: 'mode all' })
  expect(asked.length).toBe(1)
  expect(changes(ran)).toEqual(['mode full all'])
})

test('o valor em vigor leva (atual) e o rótulo vale com ou sem o sufixo', async ($, on) => {
  const { ran, asked } = await setup($, on, { answers: ['Médio (atual)', 'Só esta sessão', 'Grande', 'Só esta sessão'] })
  await $.command.run({ command: 'speak', args: 'size' })
  await $.command.run({ command: 'speak', args: 'size' })
  expect(asked[0]!.labels).toEqual(['Pequeno', 'Médio (atual)', 'Grande'])
  expect(changes(ran)).toEqual(['size medium', 'size large'])
})

test('Esc na primeira caixa não roda nada', async ($, on) => {
  const { ran } = await setup($, on, { answers: [undefined] })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('Nada mudou.')
  expect(changes(ran)).toEqual([])
})

test('Esc na caixa do alcance não roda nada', async ($, on) => {
  const { ran } = await setup($, on, { answers: ['Leitura', 'Só o resumo', undefined] })
  const r = await $.command.run({ command: 'speak', args: '' })
  expect(r.text).toContain('Nada mudou.')
  expect(changes(ran)).toEqual([])
})

test('texto livre que não bate com nenhum rótulo não roda nada e explica as formas escritas', async ($, on) => {
  const { ran } = await setup($, on, { answers: ['Leitura', 'qualquer coisa'] })
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
