"""lib/speak_numbers.py: numbers written out in Portuguese words, because the engine does not read digits."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
import speak_numbers  # noqa: E402


def spoken(text):
    return speak_numbers.digits(speak_numbers.forms(text))


class Cardinal(unittest.TestCase):
    def test_up_to_a_thousand(self):
        for n, words in ((0, 'zero'), (1, 'um'), (14, 'catorze'), (16, 'dezesseis'), (20, 'vinte'), (21, 'vinte e um'),
                         (38, 'trinta e oito'), (70, 'setenta'), (100, 'cem'), (101, 'cento e um'),
                         (250, 'duzentos e cinquenta'), (447, 'quatrocentos e quarenta e sete'), (800, 'oitocentos'),
                         (999, 'novecentos e noventa e nove')):
            self.assertEqual(speak_numbers.cardinal(n), words)

    def test_thousands_and_millions_and_where_the_e_goes(self):
        for n, words in ((1000, 'mil'), (1001, 'mil e um'), (1100, 'mil e cem'), (1250, 'mil duzentos e cinquenta'),
                         (2000, 'dois mil'), (2022, 'dois mil e vinte e dois'), (2500, 'dois mil e quinhentos'),
                         (12500, 'doze mil e quinhentos'), (100000, 'cem mil'),
                         (1000000, 'um milhão'), (2500000, 'dois milhões e quinhentos mil'),
                         (1250000, 'um milhão duzentos e cinquenta mil'), (203000000, 'duzentos e três milhões'),
                         (1000000000, 'um bilhão'), (3000000000000, 'três trilhões')):
            self.assertEqual(speak_numbers.cardinal(n), words)

    def test_feminine(self):
        for n, words in ((1, 'uma'), (2, 'duas'), (21, 'vinte e uma'), (22, 'vinte e duas'), (200, 'duzentas'),
                         (301, 'trezentas e uma'), (2000, 'duas mil'), (12, 'doze'), (100, 'cem'),
                         (2000002, 'dois milhões e duas')):
            self.assertEqual(speak_numbers.cardinal(n, feminine=True), words)


class Ordinal(unittest.TestCase):
    def test_ordinals(self):
        for n, fem, words in ((1, False, 'primeiro'), (2, True, 'segunda'), (3, False, 'terceiro'), (10, False, 'décimo'),
                              (11, False, 'décimo primeiro'), (22, True, 'vigésima segunda'), (100, False, 'centésimo'),
                              (40, False, 'quadragésimo')):
            self.assertEqual(speak_numbers.ordinal(n, fem), words)

    def test_beyond_the_table_it_is_the_cardinal(self):
        self.assertEqual(speak_numbers.ordinal(250, False), 'duzentos e cinquenta')


class Forms(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(spoken('os 447 testes passaram em 38 segundos'),
                         'os quatrocentos e quarenta e sete testes passaram em trinta e oito segundos')
        self.assertEqual(spoken('caiu de 800 para 250'), 'caiu de oitocentos para duzentos e cinquenta')
        self.assertEqual(spoken('no censo de 2022'), 'no censo de dois mil e vinte e dois')

    def test_thousands_with_dots(self):
        self.assertEqual(spoken('são 1.250 itens'), 'são mil duzentos e cinquenta itens')
        self.assertEqual(spoken('203.000.000 de habitantes'), 'duzentos e três milhões de habitantes')

    def test_a_version_is_not_a_thousand(self):
        self.assertEqual(speak_numbers.forms('a 0.24.0 e a 2.4.1 e a v1.250'), 'a 0.24.0 e a 2.4.1 e a v1.250')

    def test_money(self):
        for text, words in (('R$ 1.250,00', 'mil duzentos e cinquenta reais'),
                            ('R$ 12.500,00', 'doze mil e quinhentos reais'),
                            ('R$ 1,00', 'um real'), ('R$1', 'um real'),
                            ('R$ 2,50', 'dois reais e cinquenta centavos'),
                            ('R$ 0,01', 'um centavo'), ('R$ 0,50', 'cinquenta centavos'),
                            ('R$ 2.000.000', 'dois milhões de reais'),
                            ('R$ 2 milhões', 'dois milhões de reais'),
                            ('R$ 1,5 bilhão', 'um vírgula cinco bilhão de reais'),
                            ('R$ 12 mil', 'doze mil reais'),
                            ('R$ 1 mil', 'mil reais'), ('R$ 2.50', 'dois reais e cinquenta centavos'),
                            ('US$ 5,00', 'cinco dólares'), ('US$ 1', 'um dólar'), ('€ 20', 'vinte euros'),
                            ('US$ 0.25', 'vinte e cinco centavos de dólar'), ('US$ 3.5', 'três vírgula cinco dólares'),
                            ('$3', 'três dólares'), ('$ 1.250', 'mil duzentos e cinquenta dólares')):
            self.assertEqual(spoken('de %s.' % text), 'de %s.' % words)

    def test_money_too_long_does_not_break(self):
        self.assertEqual(spoken('R$ 12345678901234567'), 'um dois três quatro cinco seis sete oito nove zero um dois três '
                                                         'quatro cinco seis sete reais')
        self.assertNotRegex(spoken('9' * 5000), r'\d')
        self.assertEqual(speak_numbers.cardinal(10 ** 15), 'um zero zero zero zero zero zero zero zero zero zero zero '
                                                           'zero zero zero zero')

    def test_percent(self):
        self.assertEqual(spoken('quase 70%.'), 'quase setenta por cento.')
        self.assertEqual(spoken('subiu 12,5% e 1 %'), 'subiu doze vírgula cinco por cento e um por cento')

    def test_hours(self):
        for text, words in (('às 16h', 'às dezesseis horas'), ('às 23h30', 'às vinte e três horas e trinta'),
                            ('à 1h', 'à uma hora'), ('às 14h00', 'às catorze horas'),
                            ('às 22h05min', 'às vinte e duas horas e cinco'),
                            ('às 14:30', 'às catorze e trinta'), ('às 21:00', 'às vinte e uma horas'),
                            ('às 14:30h', 'às catorze e trinta'),
                            ('em 00:01:30', 'em um minuto e trinta segundos'),
                            ('em 00:03:35', 'em três minutos e trinta e cinco segundos'),
                            ('em 12:30:00', 'em doze horas e trinta minutos'),
                            ('em 01:00:00', 'em uma hora'), ('em 00:00:01', 'em um segundo')):
            self.assertEqual(spoken(text), words)

    def test_a_count_of_hours(self):
        self.assertEqual(spoken('em até 48h, ou 72h'), 'em até quarenta e oito horas, ou setenta e duas horas')
        self.assertEqual(spoken('às 14 h e por 1 h'), 'às catorze horas e por uma hora')

    def test_a_range_of_hours(self):
        self.assertEqual(spoken('das 14h-16h, pronto em 2-3h'),
                         'das catorze horas a dezesseis horas, pronto em duas a três horas')
        self.assertEqual(spoken('das 10:30-11:30'), 'das dez e trinta a onze e trinta')

    def test_per_something(self):
        self.assertEqual(spoken('custa R$ 30/ano ou US$ 20/mês'), 'custa trinta reais por ano ou vinte dólares por mês')
        self.assertEqual(spoken('a 120 km/h e 10 MB/s'), 'a cento e vinte quilômetros por hora e dez megabaites por segundo')
        self.assertEqual(spoken('3 vezes/dia'), 'três vezes/dia')

    def test_what_is_not_an_hour(self):
        self.assertEqual(spoken('tela 16:9'), 'tela dezesseis por nove')
        self.assertEqual(spoken('às 25h'), 'às vinte e cinco horas')

    def test_dates(self):
        self.assertEqual(spoken('em 14/11/2026.'), 'em catorze de novembro de dois mil e vinte e seis.')
        self.assertEqual(spoken('em 01/03.'), 'em primeiro de março.')
        self.assertEqual(spoken('em 2026-10-29 sim'), 'em vinte e nove de outubro de dois mil e vinte e seis sim')
        self.assertEqual(spoken('dia 14 de novembro'), 'dia catorze de novembro')

    def test_a_date_without_the_year_asks_for_a_sign_of_date(self):
        self.assertEqual(spoken('Passaram 10/12 testes; a nota foi 9/10.'),
                         'Passaram dez de doze testes; a nota foi nove de dez.')
        self.assertEqual(spoken('11/11 verificações'), 'onze de onze verificações')
        self.assertEqual(spoken('em 14/11, até 10/12 e no dia 3/11'),
                         'em catorze de novembro, até dez de dezembro e no dia três de novembro')
        self.assertEqual(spoken('reunião 05/11'), 'reunião cinco de novembro')

    def test_a_slash_that_is_not_a_date(self):
        self.assertEqual(spoken('passaram 3/5'), 'passaram três de cinco')
        self.assertEqual(spoken('suporte 24/7'), 'suporte vinte e quatro por sete')
        self.assertEqual(spoken('em 40/13/2026'), 'em quarenta de treze de dois mil e vinte e seis')

    def test_ordinals(self):
        self.assertEqual(spoken('o 1º lugar e a 2ª vez'), 'o primeiro lugar e a segunda vez')
        self.assertEqual(spoken('o 10º andar, nº 5'), 'o décimo andar, número cinco')

    def test_units(self):
        self.assertEqual(spoken('cerca de 280 MB e 2 GB'), 'cerca de duzentos e oitenta megabaites e dois gigabaites')
        self.assertEqual(spoken('1 GB, 0,9 GB e 1 ms'), 'um gigabaite, zero vírgula nove gigabaites e um milissegundo')
        self.assertEqual(spoken('250ms, 30s, 5 min e 10 km'),
                         'duzentos e cinquenta milissegundos, trinta segundos, cinco minutos e dez quilômetros')
        self.assertEqual(spoken('a 24 kHz'), 'a vinte e quatro quilohertz')
        self.assertEqual(spoken('2.5 GB livres em 1.5 s'), 'dois vírgula cinco gigabaites livres em um vírgula cinco segundos')
        self.assertEqual(spoken('fez 25°C e 30 °C'), 'fez vinte e cinco graus e trinta graus')

    def test_decimals(self):
        self.assertEqual(spoken('nota 3,5 e 0,75'), 'nota três vírgula cinco e zero vírgula setenta e cinco')
        self.assertEqual(spoken('vale 3,05 e 3,1416'), 'vale três vírgula zero cinco e três vírgula um quatro um seis')
        self.assertEqual(spoken('um, 2, 3'), 'um, dois, três')

    def test_the_x_of_a_speed(self):
        self.assertEqual(spoken('a 1,25x e 2x'), 'a um vírgula vinte e cinco xis e dois xis')

    def test_the_x_of_so_many_times(self):
        self.assertEqual(spoken('ficou 2x mais rápido, em 12x de R$ 99,90'),
                         'ficou duas vezes mais rápido, em doze vezes de noventa e nove reais e noventa centavos')

    def test_gender_follows_the_noun(self):
        self.assertEqual(spoken('2 horas, 1 semana, 2 dias e 21 vozes'), 'duas horas, uma semana, dois dias e vinte e uma vozes')
        self.assertEqual(spoken('200 linhas e 2 arquivos'), 'duzentas linhas e dois arquivos')
        self.assertEqual(spoken('as 2 primeiras linhas e 2 mil vezes'), 'as duas primeiras linhas e duas mil vezes')
        self.assertEqual(spoken('as 2 últimas rodadas e 1 nova tentativa'), 'as duas últimas rodadas e uma nova tentativa')

    def test_a_number_that_is_a_label_or_a_year_stays_masculine(self):
        self.assertEqual(spoken('A opção 2 conta com mais memória.'), 'A opção dois conta com mais memória.')
        self.assertEqual(spoken('O passo 1 lista os arquivos e o passo 2 marca os prontos.'),
                         'O passo um lista os arquivos e o passo dois marca os prontos.')
        self.assertEqual(spoken('Em 2021 parte do código foi reescrita.'),
                         'Em dois mil e vinte e um parte do código foi reescrita.')
        self.assertEqual(spoken('rodei o teste 2 vezes e a tarefa 1 vez'), 'rodei o teste duas vezes e a tarefa uma vez')

    def test_ranges_and_minus(self):
        self.assertEqual(spoken('páginas 3-5, de 2022-2024'), 'páginas três a cinco, de dois mil e vinte e dois a dois mil e vinte e quatro')
        self.assertEqual(spoken('fez -5 graus'), 'fez menos cinco graus')
        self.assertEqual(spoken('subiu +3 pontos'), 'subiu mais três pontos')

    def test_an_address_of_the_network_is_not_a_thousand(self):
        self.assertEqual(spoken('em 255.255.255.255 e 192.168.0.1'),
                         'em duzentos e cinquenta e cinco ponto duzentos e cinquenta e cinco ponto duzentos e cinquenta e '
                         'cinco ponto duzentos e cinquenta e cinco e cento e noventa e dois ponto cento e sessenta e oito '
                         'ponto zero ponto um')
        self.assertEqual(spoken('203.000.000.000 de reais'), 'duzentos e três bilhões de reais')

    def test_digits_stuck_to_letters_and_leading_zeros(self):
        self.assertEqual(spoken('o v2 e o utf8'), 'o v dois e o utf oito')
        self.assertEqual(spoken('código 007 e 04'), 'código zero zero sete e zero quatro')
        self.assertEqual(spoken('0 ponto 9 ponto 1'), 'zero ponto nove ponto um')
        self.assertEqual(spoken('e 1.2.3.4.5 e 1.5x2.5'), 'e um ponto dois ponto três ponto quatro ponto cinco e um ponto cinco x dois ponto cinco')
        self.assertEqual(spoken('os itens 1,2,3'), 'os itens um, dois, três')

    def test_a_number_too_long_is_said_digit_by_digit(self):
        self.assertEqual(spoken('1234567890123456'), 'um dois três quatro cinco seis sete oito nove zero um dois três quatro cinco seis')

    def test_no_digit_is_ever_left(self):
        for text in ('R$ 1.250,00 em 14/11 às 23h30, 70% de 3,5 GB; v2.4.1, 1º, 16:9, 3/5, 10-20, -1, 1e9, 0x1F, 1.2.3.4.5',
                     '192.168.0.1, 2026-13-45, 99/99/9999, 1,2,3, 5%%, 1.000.000,50'):
            self.assertNotRegex(spoken(text), r'\d')

    def test_text_without_numbers_is_left_alone(self):
        text = 'Nada de número aqui, só texto: às vezes, por cento, R$ e %.'
        self.assertEqual(spoken(text), text)


if __name__ == '__main__':
    unittest.main()
