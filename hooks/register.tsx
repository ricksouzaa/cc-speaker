// Módulo de ganchos do plugin: o comando /speak. Sem escolha escrita, pergunta em caixas de escolha nativas
// (`$.ui.ask`, o diálogo do AskUserQuestion, que abre abaixo do campo de digitação, como o /model), uma pergunta por
// vez: o ajuste, o valor e, se couber, o alcance. Só depois roda o `bin/speak` uma vez, com tudo já escolhido. Esc em
// qualquer caixa não muda nada. Responde sozinho, sem o modelo. Com a escolha escrita (/speak voice alex), roda
// direto, sem caixa, e responde uma linha.
import type { EngineInterface, Register } from 'claude-code'

type Engine = EngineInterface
type Reply = { text?: string }
type State = { on: boolean; mode: string; size: string; voice: string; engine: boolean }
type Setting = 'power' | 'mode' | 'size' | 'voice'

const MODES: Record<string, string> = { full: 'Resposta inteira', summary: 'Só o resumo' }
const SIZES: Record<string, string> = { small: 'Pequeno', medium: 'Médio', large: 'Grande' }
const VOICES: Record<string, string> = { dora: 'Dora (feminina)', alex: 'Alex (masculina)', santa: 'Santa (masculina)' }
const POWER: Record<string, string> = { on: 'Ligada', off: 'Desligada' }
const SETTINGS: Record<Setting, string> = {
  power: 'Ligar ou desligar', mode: 'Leitura', size: 'Tamanho do resumo', voice: 'Voz de leitura',
}
const SESSION = 'Só esta sessão'
const ALL = 'Todas as sessões'
const CURRENT = ' (atual)'
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

// Escrita completa: roda direto, sem caixa. Devolve undefined quando falta a escolha (então pergunta em caixas).
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

// Cada ajuste: a tabela de valores, o título da caixa e como o valor atual sai do estado.
const ASK: Record<Setting, { table: Record<string, string>; question: string; header: string; current: (s: State) => string }> = {
  power: { table: POWER, question: 'A voz fica ligada ou desligada?', header: 'Voz', current: s => (s.on ? 'on' : 'off') },
  mode: { table: MODES, question: 'O que a voz lê?', header: 'Leitura', current: s => s.mode },
  size: { table: SIZES, question: 'Qual o tamanho do resumo falado?', header: 'Tamanho', current: s => s.size },
  voice: { table: VOICES, question: 'Qual voz lê as respostas?', header: 'Voz leitura', current: s => s.voice },
}

const stripCurrent = (answer: string) => (answer.endsWith(CURRENT) ? answer.slice(0, -CURRENT.length) : answer)
const keyOf = (table: Record<string, string>, answer: string) => {
  const label = stripCurrent(answer)
  return Object.keys(table).find(k => table[k] === label)
}

class Stop extends Error {}

// Pergunta numa caixa. Esc (ou execução sem tela) vira Stop; texto livre que não bate com nenhum rótulo, undefined.
async function ask($: Engine, question: string, header: string, labels: string[]): Promise<string> {
  try {
    return await $.ui.ask(question, { header, options: labels })
  } catch {
    throw new Stop()
  }
}

// Sem escolha escrita: pergunta o ajuste (se não veio), o valor e o alcance, e então roda o speak uma vez.
async function asked($: Engine, first: string | undefined, wantsAll: boolean): Promise<Reply> {
  let setting = first as Setting | undefined
  if (!setting) {
    const answer = await ask($, 'O que quer ajustar?', 'Voz', Object.values(SETTINGS))
    setting = (Object.keys(SETTINGS) as Setting[]).find(k => SETTINGS[k] === answer)
    if (!setting) return { text: USAGE }
  }
  const { table, question, header, current } = ASK[setting]
  const now = await state($)
  const labels = Object.keys(table).map(k => table[k]! + (now && current(now) === k ? CURRENT : ''))
  const value = keyOf(table, await ask($, question, header, labels))
  if (!value) return { text: USAGE }
  let all = wantsAll
  if (setting !== 'voice' && !wantsAll) {
    const scope = await ask($, 'Vale para quais sessões?', 'Alcance', [SESSION, ALL])
    if (scope !== SESSION && scope !== ALL) return { text: USAGE }
    all = scope === ALL
  }
  const tail = all ? ['all'] : []
  const args = setting === 'power' ? [value, ...tail] : setting === 'voice' ? ['voice', value] : [setting, value, ...tail]
  return { text: (await change($, args)).text }
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
      return await asked($, body[0], wantsAll)
    } catch (error) {
      if (error instanceof Stop) return { text: `Nada mudou. ${USAGE}` }
      return { text: `O speak falhou: ${String((error as { message?: unknown })?.message ?? error)}` }
    }
  })
}
