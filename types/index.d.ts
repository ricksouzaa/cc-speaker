// Contrato do estado que o módulo de ganchos do plugin guarda na sessão (`$.state`): o menu do /speak.
export type SpeakWhere = 'all' | 'session'

declare module 'claude-code' {
  interface PluginState {
    speak: {
      // Onde as próximas trocas do menu são gravadas; volta a 'all' a cada abertura do /speak, nunca é gravada em disco.
      where: SpeakWhere
      // A linha do rodapé: a frase do que passou a valer ou o erro do speak; vazia mostra a ajuda.
      note: string
      // A linha em que o menu abre.
      focus: string
    }
  }
}
