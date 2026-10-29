// Módulo de superfície do menu do /speak: desenha as linhas que recebe por props e trata as setas. Não guarda valores
// (só a linha em foco): cada troca vai ao módulo de ganchos por `post`, que roda o speak e devolve as props novas.
// Cima e baixo mudam de linha; esquerda e direita trocam o valor, em volta; Enter não faz nada; Esc fecha o painel.
import type { ClientSurface, ClientKeyEvent } from 'claude-code'

type Value = { value: string; label: string }
type Row = { key: string; label: string; values: Value[]; value: string; own: boolean }
type Props = { rows: Row[]; focus: string; note: string }
type S = { row: number }

const HELP = '↑↓ ajuste · ←→ valor · Esc fecha'
const OWN = '· só nesta sessão'

export default function Menu(props: Props, surface: ClientSurface<S>) {
  const { Box, Text } = surface.elements
  const rows = props.rows
  const first = rows.findIndex(r => r.key === props.focus)
  const row = Math.min(surface.state?.row ?? (first < 0 ? 0 : first), rows.length - 1)
  surface.onKey((k: ClientKeyEvent) => {
    if (k.key === 'up' || k.key === 'down') {
      surface.setState({ row: (row + (k.key === 'down' ? 1 : rows.length - 1)) % rows.length })
    } else if (k.key === 'left' || k.key === 'right') {
      const current = rows[row]!
      const n = current.values.length
      const at = Math.max(0, current.values.findIndex(v => v.value === current.value))
      const next = current.values[(at + (k.key === 'right' ? 1 : n - 1)) % n]!
      surface.post({ key: current.key, value: next.value })
    }
  })
  const width = Math.max(...rows.map(r => r.label.length)) + 2
  return (
    <Box flexDirection="column">
      {rows.map((r, i) => {
        const shown = r.values.find(v => v.value === r.value)?.label ?? r.value
        return (
          <Text key={r.key} bold={i === row}>
            {(i === row ? '❯ ' : '  ') + r.label.padEnd(width) + '‹ ' + shown + ' ›' + (r.own ? '  ' + OWN : '')}
          </Text>
        )
      })}
      <Text dimColor>{props.note || HELP}</Text>
    </Box>
  )
}
