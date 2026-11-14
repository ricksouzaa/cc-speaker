"""Numbers written out in Brazilian Portuguese words. The engine (Pocket TTS) takes text only and does not read
digits: handed "R$ 1.250,00" or "70%", it says noise, and the words around go with it. So nothing with a digit
reaches it: `forms` writes out what has a shape of its own (money, hours, dates, percentages, ordinals, units,
decimals) and `digits` whatever digit is left. Standard library only."""
import re

UNITS = ('zero um dois três quatro cinco seis sete oito nove dez onze doze treze catorze quinze dezesseis dezessete '
         'dezoito dezenove').split()
TENS = '- - vinte trinta quarenta cinquenta sessenta setenta oitenta noventa'.split()
HUNDREDS = '- cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos'.split()
SCALES = ((None, None), ('mil', 'mil'), ('milhão', 'milhões'), ('bilhão', 'bilhões'), ('trilhão', 'trilhões'))
LIMIT = 10 ** 15  # from here on a number is said digit by digit
ORDINAL_UNITS = '- primeiro segundo terceiro quarto quinto sexto sétimo oitavo nono'.split()
ORDINAL_TENS = ('- décimo vigésimo trigésimo quadragésimo quinquagésimo sexagésimo septuagésimo octogésimo '
                'nonagésimo').split()
MONTHS = 'janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro'.split()
# Nouns that make the number before them feminine ("duas horas", "vinte e uma vozes"), written one and many; any
# other is masculine. The number has to agree with the noun (one with "hora", more with "horas"): in "a opção 2
# conta com" and "em 2021 parte do código" the word after is a verb, not what is counted.
FEMININE = tuple((
    'hora horas vez vezes semana semanas linha linhas voz vozes sessão sessões versão versões pessoa pessoas página '
    'páginas palavra palavras frase frases mensagem mensagens resposta respostas pergunta perguntas opção opções '
    'função funções pasta pastas máquina máquinas tentativa tentativas etapa etapas parte partes coisa coisas '
    'mudança mudanças correção correções verificação verificações instalação instalações marca marcas chamada '
    'chamadas conexão conexões fila filas fala falas lista listas tabela tabelas coluna colunas tela telas janela '
    'janelas aba abas tecla teclas nota notas dúvida dúvidas questão questões decisão decisões pendência pendências '
    'amostra amostras gravação gravações sílaba sílabas letra letras sigla siglas regra regras variável variáveis '
    'chave chaves conta contas casa casas noite noites manhã manhãs tarde tardes reunião reuniões tarefa tarefas '
    'categoria categorias camada camadas cópia cópias rodada rodadas').split())
FEMININE_ONE = frozenset(FEMININE[0::2]) | frozenset('primeira última próxima nova outra mesma única'.split())
FEMININE_MANY = frozenset(FEMININE[1::2]) | frozenset('primeiras últimas próximas novas outras mesmas únicas'.split())
# "o passo 1 lista os arquivos": after a noun that numbers things, a 1 before one of these verbs is not counting it.
LABELS = frozenset(('passo opção item etapa fase linha página capítulo seção caso teste tarefa versão nível tipo grupo '
                    'figura tabela questão exemplo número porta andar sala').split())
VERBS_TOO = frozenset('conta lista marca fala nota parte casa pergunta tecla amostra'.split())
# What follows a number, written as it is said: (one, many).
MEASURES = {'KB': ('quilobaite', 'quilobaites'), 'MB': ('megabaite', 'megabaites'), 'GB': ('gigabaite', 'gigabaites'),
            'TB': ('terabaite', 'terabaites'), 'ms': ('milissegundo', 'milissegundos'), 's': ('segundo', 'segundos'),
            'min': ('minuto', 'minutos'), 'km': ('quilômetro', 'quilômetros'), 'kg': ('quilo', 'quilos'),
            'cm': ('centímetro', 'centímetros'), 'mm': ('milímetro', 'milímetros'), 'Hz': ('hertz', 'hertz'),
            'kHz': ('quilohertz', 'quilohertz'), 'MHz': ('megahertz', 'megahertz'), 'GHz': ('gigahertz', 'gigahertz')}
CURRENCIES = {'R$': ('real', 'reais'), 'US$': ('dólar', 'dólares'), '$': ('dólar', 'dólares'), '€': ('euro', 'euros')}
NUMBER = r'\d+(?:,\d+)?'  # as written after the dots of the thousands are gone
POINT_NUMBER = r'\d+(?:[.,]\d+)?'  # the same, or with the point of the English decimals ("US$ 0.25", "2.5 GB")
PER = {'h': 'hora', 's': 'segundo', 'min': 'minuto'}  # "km/h", "MB/s"


def _under_a_thousand(n, feminine):
    if n == 100:
        return 'cem'
    hundreds, rest = divmod(n, 100)
    words = []
    if hundreds:
        words.append(HUNDREDS[hundreds][:-2] + 'as' if feminine and hundreds > 1 else HUNDREDS[hundreds])
    if rest:
        tens, unit = (0, rest) if rest < 20 else divmod(rest, 10)
        if tens:
            words.append(TENS[tens])
        if unit:
            words.append({1: 'uma', 2: 'duas'}.get(unit, UNITS[unit]) if feminine else UNITS[unit])
    return ' e '.join(words)


def cardinal(n, feminine=False):
    """1250 -> "mil duzentos e cinquenta"; feminine: 2 -> "duas", 200 -> "duzentas" (the millions stay masculine)."""
    if n == 0:
        return 'zero'
    if n >= LIMIT:
        return _one_by_one(str(n))
    groups, scale = [], 0
    while n:
        n, group = divmod(n, 1000)
        if group:
            groups.append((group, scale))
        scale += 1
    parts = []
    for group, scale in reversed(groups):
        if scale == 0:
            parts.append(_under_a_thousand(group, feminine))
        elif scale == 1:
            parts.append('mil' if group == 1 else _under_a_thousand(group, feminine) + ' mil')
        else:
            parts.append('%s %s' % (_under_a_thousand(group, False), SCALES[scale][0 if group == 1 else 1]))
    if len(parts) == 1:
        return parts[0]
    last = groups[0][0]  # "mil e cem", "dois mil e vinte", but "mil duzentos e cinquenta"
    return ' '.join(parts[:-1]) + (' e ' if last < 100 or last % 100 == 0 else ' ') + parts[-1]


def ordinal(n, feminine=False):
    """1 -> "primeiro", 22 feminine -> "vigésima segunda"; past 100 it is the cardinal."""
    if not 1 <= n <= 100:
        return cardinal(n, feminine)
    if n == 100:
        words = ['centésimo']
    else:
        tens, unit = divmod(n, 10)
        words = [w for w in (ORDINAL_TENS[tens] if tens else '', ORDINAL_UNITS[unit] if unit else '') if w]
    return ' '.join(w[:-1] + 'a' if feminine else w for w in words)


def _one_by_one(run):
    return ' '.join(UNITS[int(c)] for c in run)


def _whole(run, feminine=False):
    """A run of digits as it is said: "007" -> "zero zero sete"; one too long, digit by digit."""
    bare = run.lstrip('0')
    zeros = len(run) - len(bare) if bare else len(run) - 1
    if not bare:
        bare = '0'
    said = _one_by_one(bare) if len(bare) > 15 else cardinal(int(bare), feminine)
    return ' '.join(['zero'] * zeros + [said])


def _decimal(text):
    """"3,5" -> "três vírgula cinco"; "1250" -> "mil duzentos e cinquenta"."""
    whole, _, fraction = text.partition(',')
    if not fraction:
        return _whole(whole)
    return '%s vírgula %s' % (_whole(whole), _whole(fraction) if len(fraction) <= 3 else _one_by_one(fraction))


def _money(match):
    one, many = CURRENCIES[match.group(1)]
    amount, scale = match.group(2).replace('.', ','), match.group(3)
    if scale:
        if scale == 'mil':
            return '%smil %s' % ('' if amount == '1' else _decimal(amount) + ' ', many)
        return '%s %s de %s' % (_decimal(amount), scale, many)
    whole, _, cents = amount.partition(',')
    if cents and len(cents) != 2:
        return '%s %s' % (_decimal(amount), many)
    if len(whole) > 15:
        return '%s %s' % (_one_by_one(whole), many)
    whole, cents = int(whole), int(cents or 0)
    said = []
    if whole or not cents:
        round_million = whole >= 10 ** 6 and whole % 10 ** 6 == 0
        said.append('%s %s%s' % (cardinal(whole), 'de ' if round_million else '', one if whole == 1 else many))
    if cents:
        said.append('%s %s%s' % (cardinal(cents), 'centavo' if cents == 1 else 'centavos',
                                 '' if whole or match.group(1) == 'R$' else ' de ' + one))
    return ' e '.join(said)


def _hour(hours, minutes, clock=False):
    hours, minutes = int(hours), int(minutes or 0)
    said = cardinal(hours, feminine=True)
    if not minutes or not clock:
        said += ' hora' if hours == 1 else ' horas'
    return said + (' e ' + cardinal(minutes) if minutes else '')


def _letter_hour(match):
    """23h30, and a count of hours too: 48h -> "quarenta e oito horas"."""
    if int(match.group(2) or 0) > 59:
        return match.group(0)
    return _hour(match.group(1), match.group(2))


def _hour_range(match):
    """14h-16h -> "catorze horas a dezesseis horas"; 2-3h -> "duas a três horas"."""
    first, mark, first_minutes, second, second_minutes = match.groups()
    if int(first_minutes or 0) > 59 or int(second_minutes or 0) > 59:
        return match.group(0)
    return '%s a %s' % (_hour(first, first_minutes) if mark else cardinal(int(first), feminine=True),
                        _hour(second, second_minutes))


def _duration(hours, minutes, seconds):
    """00:03:35 -> "três minutos e trinta e cinco segundos"."""
    parts = [cardinal(n, feminine=one == 'hora') + ' ' + (one if n == 1 else one + 's')
             for n, one in ((hours, 'hora'), (minutes, 'minuto'), (seconds, 'segundo')) if n]
    if not parts:
        return 'zero segundos'
    return ', '.join(parts[:-1]) + (' e ' if len(parts) > 1 else '') + parts[-1]


def _clock_hour(match):
    hours, minutes, seconds = int(match.group(1)), int(match.group(2)), match.group(3)
    if minutes > 59 or int(seconds or 0) > 59:
        return match.group(0)
    if seconds is not None:
        return _duration(hours, minutes, int(seconds))
    if hours > 23:
        return match.group(0)
    return _hour(hours, minutes, clock=True)


def _date(day, month, year=None):
    day, month = int(day), int(month)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    said = '%s de %s' % ('primeiro' if day == 1 else cardinal(day), MONTHS[month - 1])
    return said + (' de ' + _whole(year) if year else '')


def _slashes(match):
    parts = match.group(0).split('/')
    if parts == ['24', '7']:
        return '24 por 7'
    said = None
    if len(parts) == 3 and len(parts[2]) in (2, 4):
        said = _date(*parts)
    elif len(parts) == 2 and len(parts[1]) == 2 and (parts[0][0] == '0' or parts[1][0] == '0' or DATE_SIGN.search(
            match.string, 0, match.start())):
        said = _date(*parts)  # without the year it takes a sign of date: "10/12 testes" is a count
    return said or ' de '.join(parts)


DATE_WORD = r'(?:em|dia|dias|desde|até|no|para|entre)'
DATE_SIGN = re.compile(r'(?i)\b%s\s+(?:\d{1,2}/\d{2}\s+(?:e|a|ou)\s+)?$' % DATE_WORD)


def _thousand(match):
    """1.250 -> 1250; four groups up to 255 are an address of the network and stay."""
    groups = match.group(0).split('.')
    if len(groups) == 4 and all(int(g) <= 255 for g in groups) and set(groups[1:]) != {'000'}:
        return match.group(0)
    return ''.join(groups)


def _iso_date(match):
    return _date(match.group(3), match.group(2), match.group(1)) or match.group(0)


def _measure(match):
    one, many = MEASURES[match.group(2)]
    return '%s %s' % (match.group(1).replace('.', ','), one if match.group(1) == '1' else many)


def forms(text):
    """Writes out the numbers that have a shape of their own, before other rules take their pieces for something
    else (a date for a path, the dots of a thousand for a version). Plain whole numbers are left for `digits`."""
    if not re.search(r'\d', text):
        return text
    # 1.250 and 203.000.000 lose the dots; 0.24.0, 2.4.1 and v1.250 are versions and keep them
    text = re.sub(r'(?<![\w.,/-])[1-9]\d{0,2}(?:\.\d{3})+(?![\w]|\.\d)', _thousand, text)
    # "R$ 30/ano", "120 km/h": before the slash is taken for a path
    text = re.sub(r'(?<=\d)(\s?[A-Za-z]{1,3})?/(ano|mês|dia|semana|hora|min|h|s)(?![\w/-])',
                  lambda m: '%s por %s' % (m.group(1) or '', PER.get(m.group(2), m.group(2))), text)
    text = re.sub(r'(?<![\w/.-])(\d{4})-(\d{2})-(\d{2})(?![\w/-])', _iso_date, text)
    text = re.sub(r'(?<![\w/.,-])\d+(?:/\d+)+(?![\w/-])', _slashes, text)
    text = re.sub(r'(?<![\w/.,:-])(\d{1,2}:\d{2})-(?=\d{1,2}:\d{2}(?![\w:-]))', r'\1 a ', text)  # 10:30-11:30
    text = re.sub(r'(?<![\w/.,:-])(\d{1,2})(h(\d{2})?)?-(\d{1,3})h(\d{2})?(?![\w-])', _hour_range, text)
    text = re.sub(r'(?<![\w/.,:-])(\d{1,3})\s?h(\d{2})?(?:min)?(?![\w-])', _letter_hour, text)
    text = re.sub(r'(?<![\w/.,:-])(\d{1,2}):(\d{2})(?::(\d{2}))?h?(?![\w:-])', _clock_hour, text)
    text = re.sub(r'(R\$|US\$|€|(?<![\w$])\$)\s?(%s)(?:\s(mil|milh(?:ão|ões)|bilh(?:ão|ões)|trilh(?:ão|ões))\b)?(?!\d)'
                  % POINT_NUMBER, _money, text)
    text = re.sub(r'(?<=\d)\s?%', ' por cento', text)
    text = re.sub(r'\bnº\s?(?=\d)', 'número ', text)
    text = re.sub(r'(?<![\w,.])(\d{1,3})([ºª])', lambda m: ordinal(int(m.group(1)), m.group(2) == 'ª'), text)
    text = re.sub(r'(?<![\w.])(%s)\s?(%s)(?![\w-])' % (POINT_NUMBER, '|'.join(sorted(MEASURES, key=len, reverse=True))),
                  _measure, text)
    text = re.sub(r'(?<=\d)\s?°\s?[CF]?(?!\w)', ' graus', text)
    text = re.sub(r'(?<![\w,.])(\d+)[xX](?=\s+(?:mais|menos|maior|menor|de)\b)', r'\1 vezes', text)  # 2x mais rápido
    text = re.sub(r'(?<=\d)[xX](?![\w-])', ' xis', text)
    text = re.sub(r'(?<![\w,.])\d+,\d+(?![\w]|,\d)', lambda m: _decimal(m.group(0)), text)
    return text


def digits(text):
    """Writes out every digit that is left, so none reaches the engine: a whole number as its cardinal ("duas"
    before a feminine noun), "3-5" as "três a cinco", "-5" as "menos cinco", "16:9" as "dezesseis por nove", a dot
    between two as "ponto", digits stuck to letters apart."""
    if not re.search(r'\d', text):
        return text
    text = re.sub(r'(?<![\w-])(\d+)-(?=\d+(?![\w-]))', r'\1 a ', text)
    text = re.sub(r'(?<![\w)\]])[-−](?=\d)', 'menos ', text)
    text = re.sub(r'(?<![\w)\]+])\+(?=\d)', 'mais ', text)
    text = re.sub(r'(?<=[^\W\d_])-(?=\d)', ' ', text)  # UTF-8, covid-19
    text = re.sub(r'(?<=\d)\.(?=\d)', ' ponto ', text)  # 1.2.3.4.5, 1.5x2.5
    text = re.sub(r'(?<=\d),(?=\d)', ', ', text)  # 1,2,3
    text = re.sub(r'(?<=\d):(?=\d)', ' por ', text)  # 16:9
    text = re.sub(r'(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])', ' ', text)

    def say(match):
        following = re.match(r'(\s+a\s+\d+)?(\s+mil)?\s+([^\W\d_]+)', text[match.end():])
        if not following:
            return _whole(match.group(0))
        word = following.group(3).lower()
        one = match.group(0).lstrip('0') == '1' and not following.group(1) and not following.group(2)
        feminine = word in (FEMININE_ONE if one else FEMININE_MANY)
        if feminine and one and word in VERBS_TOO:
            before = re.search(r'([^\W\d_]+)\s+$', text[:match.start()])
            feminine = not (before and before.group(1).lower() in LABELS)
        return _whole(match.group(0), feminine)
    return re.sub(r'\d+', say, text)
