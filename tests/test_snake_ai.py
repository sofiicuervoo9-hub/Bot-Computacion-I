"""Tests unitarios de snake_ai.py (SnakeStrategy y el wrapper choose_direction)."""

from board import Board, DIRECTIONS
from snake_ai import (
    RACE_STALL_BONUS, RACE_STALL_MAX, SnakeStrategy, WRONG_DIGIT_STEP_PENALTY, choose_direction,
)


def make_board_str(rows):
    return '\n'.join('|' + row + '|' for row in rows)


def test_sin_cabeza_devuelve_direccion_al_azar():
    strategy = SnakeStrategy()
    board_str = make_board_str(['.....', '.....'])
    d = strategy.choose_direction(board_str, 'A')
    assert d in DIRECTIONS


def test_board_invalido_no_rompe_devuelve_direccion():
    strategy = SnakeStrategy()
    # board_str sin ninguna linea que empiece con '|': grid vacio,
    # deberia caer al manejo de excepcion/"sin cabeza" sin explotar.
    d = strategy.choose_direction('esto no es un tablero valido', 'A')
    assert d in DIRECTIONS


def test_va_directo_a_la_comida_mas_cercana_si_es_segura():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.........',
        '.........',
        '..A......',
        '..*......',
        '.........',
    ])
    d = strategy.choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d == 'down'


def test_evita_comida_que_el_rival_alcanza_primero():
    strategy = SnakeStrategy()
    # La comida esta mucho mas cerca del rival (B) que de mi (A): no
    # debe ir directo a competir por ella y perderla.
    board_str = make_board_str([
        'A........',
        '.........',
        '.........',
        '.........',
        '........B',
        '.......*.',
    ])
    d = strategy.choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d in DIRECTIONS  # no explota; el comportamiento fino ya se prueba abajo


def test_no_hay_comida_usa_modo_territorio():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.........',
        '..A......',
        '.........',
    ])
    d = strategy.choose_direction(board_str, 'A')
    assert d in DIRECTIONS


def test_evita_chocar_contra_su_propio_cuerpo():
    strategy = SnakeStrategy()
    # Cabeza rodeada por su propio cuerpo salvo una salida (abajo).
    board_str = make_board_str([
        '.......',
        '.aaa...',
        '.aAa...',
        '.......',
    ])
    d = strategy.choose_direction(board_str, 'A')
    assert d == 'down'


def test_sin_movimiento_seguro_no_rompe():
    strategy = SnakeStrategy()
    # Cabeza totalmente encerrada por el rival: ningun vecino es valido.
    board_str = make_board_str([
        '.......',
        '.BBB...',
        '.BAB...',
        '.BBB...',
    ])
    d = strategy.choose_direction(board_str, 'A')
    assert d in DIRECTIONS


def test_safety_buffer_se_activa_cuando_voy_ganando_y_quedan_pocos_turnos():
    strategy = SnakeStrategy(safety_buffer=3)
    board = None  # construido via Board dentro de choose_direction

    # Con el buffer activo, evita ir a comer si el espacio resultante
    # queda muy justo -- lo confirmamos indirectamente: no explota y
    # sigue devolviendo una direccion valida.
    board_str = make_board_str([
        '.........',
        '..A......',
        '..*......',
        '.........',
    ])
    d = strategy.choose_direction(
        board_str, 'A', my_score=50, opp_score=10, remaining_moves=5,
    )
    assert d in DIRECTIONS


def test_safety_buffer_no_se_activa_si_voy_perdiendo():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.........',
        '..A......',
        '..*......',
        '.........',
    ])
    d = strategy.choose_direction(
        board_str, 'A', my_score=1, opp_score=50, remaining_moves=5,
    )
    assert d in DIRECTIONS


# -- modo cazador (agresivo cuando voy ganando) -----------------------------

def test_is_aggressive_solo_si_gano_por_mas_del_margen():
    strategy = SnakeStrategy(aggressive_margin=10)
    assert strategy._is_aggressive(50, 30) is True     # gano por 20 > margen 10
    assert strategy._is_aggressive(35, 30) is False    # gano por 5 <= margen 10
    assert strategy._is_aggressive(20, 30) is False    # voy perdiendo
    assert strategy._is_aggressive(None, 30) is False  # sin datos de puntaje
    assert strategy._is_aggressive(50, None) is False


def test_build_candidates_calcula_opp_space_en_cuello_de_botella():
    # Pared que separa al rival del resto del tablero salvo una unica
    # abertura en (3,3), justo arriba de mi cabeza: si tapo esa celda
    # ('up'), el rival queda encerrado en una zona mucho mas chica.
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[1][2] = 'B'
    grid[4][3] = 'A'
    for c in range(n_cols):
        grid[3][c] = 'b'
    grid[3][3] = '.'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    board = Board(board_str, 'A', f'{n_rows}x{n_cols}')
    strategy = SnakeStrategy()
    candidates = strategy._build_candidates(board)

    assert candidates['up']['opp_space'] < candidates['down']['opp_space']
    assert candidates['up']['opp_space'] < candidates['left']['opp_space']
    assert candidates['up']['opp_space'] < candidates['right']['opp_space']


def test_modo_agresivo_prioriza_achicar_espacio_del_rival_sobre_territorio():
    # Candidatos hechos a mano para aislar la logica de ranking: sin
    # modo agresivo se elige el de mayor territorio (B); con modo
    # agresivo se elige el que mas le achica el espacio al rival (A),
    # aunque tenga menos territorio propio.
    board = Board(make_board_str(['.....', '..A..', '.....']), 'A')
    strategy = SnakeStrategy()
    candidates = {
        'up': {
            'dir': 'up', 'pos': (0, 2), 'space': 10, 'body_len': 1,
            'territory': 5, 'opp_space': 2, 'wrong_digit': False,
        },
        'down': {
            'dir': 'down', 'pos': (2, 2), 'space': 10, 'body_len': 1,
            'territory': 9, 'opp_space': 20, 'wrong_digit': False,
        },
    }
    assert strategy._best_territory_move(board, candidates, aggressive=False) == 'down'
    assert strategy._best_territory_move(board, candidates, aggressive=True) == 'up'


def test_choose_direction_modo_agresivo_end_to_end():
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[1][2] = 'B'
    grid[4][3] = 'A'
    for c in range(n_cols):
        grid[3][c] = 'b'
    grid[3][3] = '.'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    strategy = SnakeStrategy()
    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}',
        my_score=100, opp_score=0, remaining_moves=200,
    )
    assert d == 'up'  # tapa la unica abertura y encierra al rival


def test_prefiere_paso_sin_digito_incorrecto_en_empate():
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[2][2] = 'A'
    grid[2][3] = '7'   # incorrecto, adyacente (empate de distancia con 'down')
    grid[5][5] = '5'   # correcto, mas lejos
    grid[0][0] = '6'
    grid[0][9] = '8'
    grid[9][0] = '9'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}',
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'down'


def test_evita_pisar_digito_equivocado_aunque_sea_el_camino_mas_corto():
    # Reproduce un bug real que aparecio en una partida: el objetivo (1)
    # queda en linea recta detras de un digito equivocado (6) pegado a
    # la cabeza. Ir derecho es el camino MAS CORTO hacia el objetivo,
    # pero pisa el 6 en el primer paso (-500 inmediato). El desempate
    # por wrong_digit antes solo actuaba en empates de distancia, asi
    # que el camino corto ganaba igual y el bot comia el digito
    # equivocado. Ahora un primer paso que pisa un digito equivocado se
    # penaliza fuerte en la distancia total, asi que pierde contra
    # cualquier rodeo mas largo pero seguro.
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[5][1] = '1'   # objetivo, en linea recta a la izquierda
    grid[5][4] = '6'   # incorrecto, pegado a la cabeza -- tapa el camino directo
    grid[5][5] = 'A'
    grid[0][0] = '2'
    grid[0][9] = '3'
    grid[9][9] = '4'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    b = Board(board_str, 'A', f'{n_rows}x{n_cols}', next_digit=1)
    candidates = strategy._build_candidates(b)
    assert candidates['left']['wrong_digit'] is True

    step, dist = strategy._best_target_move(candidates, b.food, 0)
    assert step != 'left'  # ya no elige el camino corto que pisa el 6
    assert dist < WRONG_DIGIT_STEP_PENALTY  # el elegido no arrastra la penalidad

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=1,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d != 'left'


def test_next_digit_del_server_dirige_la_estrategia():
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[2][2] = 'A'
    grid[2][3] = '7'
    grid[5][5] = '5'
    grid[0][0] = '6'
    grid[0][9] = '8'
    grid[9][0] = '9'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=7,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'right'  # ahora el objetivo es el 7, pegado a la cabeza


def test_board_construction_exception_devuelve_direccion_al_azar():
    strategy = SnakeStrategy()
    # side=None hace explotar Board.__init__ en side.lower(); el except
    # generico de choose_direction debe atajarlo sin propagar el error.
    d = strategy.choose_direction(make_board_str(['...', '...']), None)
    assert d in DIRECTIONS


def test_candidato_que_no_alcanza_la_comida_se_descarta():
    strategy = SnakeStrategy()
    # (2,1) es un bolsillo sin salida (con cuerpo detras de la cabeza,
    # la vieja celda de la cabeza queda bloqueada al moverse, asi que
    # 'left' no tiene por donde escapar); la comida esta en otra zona.
    # La busqueda de comida debe saltear ese candidato (no esta en su
    # dist_map, dispara el "continue") sin romperse.
    board_str = make_board_str([
        '......',
        '.b....',
        'b.Aa..',
        '.b....',
        '...*..',
    ])
    d = strategy.choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d in DIRECTIONS
    assert d != 'left'  # 'left' es el bolsillo sin salida


def test_wrapper_choose_direction_compatibilidad():
    board_str = make_board_str([
        '.........',
        '..A......',
        '..*......',
        '.........',
    ])
    d = choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d == 'down'


# -- v4: pickups de multiplicador ('X') --------------------------------

def test_va_al_pickup_de_multiplicador_si_no_hay_comida():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.........',
        '.........',
        '..A......',
        '..X......',
        '.........',
    ])
    d = strategy.choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d == 'down'


def test_prioriza_digito_correcto_sobre_pickup_de_multiplicador():
    # El digito correcto (2) esta pegado a la cabeza; el pickup 'X' esta
    # mas lejos -- el digito, que ademas hace crecer, gana la prioridad.
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[2][2] = 'A'
    grid[2][3] = '2'   # objetivo, adyacente
    grid[8][8] = 'X'   # pickup, lejos
    grid[0][0] = '3'
    grid[0][9] = '4'
    grid[9][0] = '5'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=2,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'right'


def test_va_por_el_pickup_cuando_esta_mas_cerca_que_el_digito():
    # Al reves del test anterior: ahora el pickup 'X' esta pegado a la
    # cabeza y el digito correcto queda lejos -- como el 'X' da un
    # multiplicador permanente, conviene desviarse a buscarlo primero
    # aunque el digito siga siendo territorio "seguro".
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[2][2] = 'A'
    grid[2][3] = 'X'   # pickup, adyacente
    grid[8][8] = '2'   # objetivo correcto, lejos
    grid[0][0] = '3'
    grid[0][9] = '4'
    grid[9][0] = '5'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=2,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'right'


def test_a_igual_distancia_prefiere_el_pickup_de_multiplicador():
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[2][2] = 'A'
    grid[2][3] = 'X'   # pickup, a distancia 1 (derecha)
    grid[1][2] = '2'   # objetivo correcto, tambien a distancia 1 (arriba)
    grid[0][0] = '3'
    grid[0][9] = '4'
    grid[9][0] = '5'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=2,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'right'  # empate de distancia -> gana el pickup


def test_pickup_de_multiplicador_no_hace_crecer_la_vibora():
    # Con la vibora larga, pisar el 'X' no debe agregar al conteo de
    # cuerpo esperado -- lo confirmamos indirectamente: el candidato que
    # pisa el pickup exige el mismo espacio que un paso comun, no uno
    # mas (como exigiria comer un digito).
    strategy = SnakeStrategy()
    board = Board(make_board_str(['.......', '.aaA...', '.......']), 'A')
    candidates = strategy._build_candidates(board)
    board_con_pickup = Board(make_board_str(['.......', '.aaA...', '..X....']), 'A')
    candidates_con_pickup = strategy._build_candidates(board_con_pickup)
    # 'down' en ambos casos no come nada que haga crecer: mismo body_len.
    assert candidates['down']['body_len'] == candidates_con_pickup['down']['body_len']


def test_best_multiplier_move_evita_que_el_rival_lo_alcance_primero():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        'A........',
        '.........',
        '.........',
        '.........',
        '........B',
        '.......X.',
    ])
    d = strategy.choose_direction(board_str, 'A', my_score=0, opp_score=0, remaining_moves=100)
    assert d in DIRECTIONS  # no explota; el rival esta mucho mas cerca del pickup


def test_choose_direction_acepta_multiplicadores_sin_romper():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.........',
        '..A......',
        '..*......',
        '.........',
    ])
    d = strategy.choose_direction(
        board_str, 'A', my_score=0, opp_score=0, remaining_moves=100,
        my_multiplier=3, opp_multiplier=1,
    )
    assert d == 'down'


# -- v5: muro ('#') -----------------------------------------------------

def test_build_candidates_marca_wall_hit_y_lo_deja_sin_espacio():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.....',
        '.....',
        '..A#.',
        '.....',
        '.....',
    ])
    b = Board(board_str, 'A')
    candidates = strategy._build_candidates(b)
    assert candidates['right']['wall_hit'] is True
    assert candidates['right']['space'] == 0  # nadie puede entrar a un muro este turno
    assert candidates['up']['wall_hit'] is False


def test_evita_el_muro_cuando_hay_alternativa_segura():
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.....',
        '.....',
        '..A#.',
        '.....',
        '.....',
    ])
    d = strategy.choose_direction(board_str, 'A')
    assert d != 'right'  # ahi esta el muro, hay tres salidas abiertas


def test_elige_el_muro_como_ultimo_recurso_antes_que_morir():
    # La cabeza queda encerrada por el rival salvo una unica abertura,
    # que es una celda de muro: chocar ahi cuesta -500 y no te moves,
    # pero no mata -- a diferencia de las otras tres direcciones (cuerpo
    # rival), asi que sigue siendo la mejor opcion disponible.
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.b.',
        'bA#',
        '.b.',
    ])
    d = strategy.choose_direction(board_str, 'A')
    assert d == 'right'


def test_muro_no_se_pisa_para_llegar_a_la_comida_si_hay_rodeo():
    # La comida queda justo detras de una celda de muro, pero se puede
    # rodear: el bot no debe atravesar (intentar entrar a) el muro solo
    # porque geometricamente sea el camino mas corto.
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[5][5] = 'A'
    grid[5][4] = '#'   # tapa el camino directo a la izquierda
    grid[5][2] = '*'   # comida, alcanzable rodeando
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}',
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d != 'left'


def test_is_aggressive_por_muro_independiente_del_puntaje():
    strategy = SnakeStrategy()
    board_sin_muro = Board(make_board_str(['.....', '..A..', '.....']), 'A')
    board_con_muro = Board(make_board_str(['.....', '..A..', '..#..']), 'A')
    assert strategy._is_aggressive(0, 0, board_sin_muro) is False
    assert strategy._is_aggressive(0, 0, board_con_muro) is True
    assert strategy._is_aggressive(0, 50, board_con_muro) is True  # incluso perdiendo
    assert strategy._is_aggressive(0, 0) is False  # sin board: se ignora el chequeo de muro


def test_safety_buffer_extra_cerca_del_final_si_hay_muro_aunque_no_gane():
    strategy = SnakeStrategy(safety_buffer=3)
    board_sin_muro = Board(make_board_str(['.....', '..A..', '.....']), 'A')
    board_con_muro = Board(make_board_str(['.....', '..A..', '..#..']), 'A')
    # Perdiendo, quedan pocos turnos: sin muro no hay buffer extra.
    assert strategy._safety_buffer(board_sin_muro, my_score=0, opp_score=50, remaining_moves=5) == 0
    # Con muro en juego, si -- aunque vaya perdiendo, cuidado extra.
    assert strategy._safety_buffer(board_con_muro, my_score=0, opp_score=50, remaining_moves=5) == 3
    # Lejos del final, ni con muro hace falta el buffer extra.
    assert strategy._safety_buffer(board_con_muro, my_score=0, opp_score=50, remaining_moves=200) == 0


def test_modo_agresivo_se_activa_por_presencia_de_muro_sin_ir_ganando():
    # Mismo cuello de botella que test_choose_direction_modo_agresivo_end_to_end,
    # pero ahora el modo cazador se activa por la presencia de un muro
    # en el tablero (en una celda que no interfiere con el cuello de
    # botella), no por ir ganando: el bot igual debe tapar la unica
    # salida del rival para achicarle el terreno.
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[1][2] = 'B'
    grid[4][3] = 'A'
    for c in range(n_cols):
        grid[3][c] = 'b'
    grid[3][3] = '.'
    grid[9][9] = '#'   # muro lejos del cuello de botella, solo para activar el modo
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    strategy = SnakeStrategy()
    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}',
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'up'  # tapa la unica abertura y encierra al rival


# -- v6: copias multiples de cada digito ---------------------------------

def test_v6_va_a_la_copia_mas_cercana_del_objetivo():
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[5][5] = 'A'
    grid[0][0] = '2'   # copia lejana
    grid[9][0] = '2'   # copia lejana
    grid[5][7] = '2'   # copia cercana, a la derecha
    grid[0][9] = '3'
    grid[9][9] = '4'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=2,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d == 'right'


def test_v6_mide_el_camino_limpio_aunque_el_digito_equivocado_no_este_pegado():
    # El objetivo (1) esta a la izquierda y el camino recto pasa por un
    # digito equivocado (6) en el SEGUNDO paso, no en el primero. Antes
    # la distancia medida era 4 (atravesando el 6) y le ganaba a un 'X'
    # a distancia 5; ahora se mide el rodeo limpio (6), asi que el 'X'
    # gana la comparacion y se evita el -500.
    strategy = SnakeStrategy()
    n_rows, n_cols = 10, 10
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[5][5] = 'A'
    grid[5][3] = '6'   # equivocado, dos pasos a la izquierda
    grid[5][1] = '1'   # objetivo
    grid[6][9] = 'X'   # pickup a distancia 5, camino limpio
    grid[0][0] = '2'
    grid[0][9] = '3'
    grid[9][0] = '4'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)

    b = Board(board_str, 'A', f'{n_rows}x{n_cols}', next_digit=1)
    candidates = strategy._build_candidates(b)
    _, food_dist = strategy._best_target_move(candidates, b.food, 0)
    assert food_dist == 6  # rodeo limpio, no los 4 pasos que pisan el 6

    d = strategy.choose_direction(
        board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=1,
        my_score=0, opp_score=0, remaining_moves=200,
    )
    assert d in ('right', 'down')  # va por el 'X'


def test_v6_si_solo_se_llega_pisando_un_digito_equivocado_se_penaliza():
    # El objetivo queda encerrado detras de digitos equivocados: no hay
    # camino limpio, solo uno que pisa alguno. Sigue siendo alcanzable,
    # pero la distancia lleva la penalidad encima.
    strategy = SnakeStrategy()
    board_str = make_board_str([
        '.......',
        '.A.....',
        '.......',
        '....5..',
        '...515.',
        '....5..',
    ])
    b = Board(board_str, 'A', next_digit=1)
    candidates = strategy._build_candidates(b)
    _, dist = strategy._best_target_move(candidates, b.food, 0)
    assert dist >= WRONG_DIGIT_STEP_PENALTY


def test_wrapper_choose_direction_con_next_digit():
    n_rows, n_cols = 6, 6
    grid = [['.' for _ in range(n_cols)] for _ in range(n_rows)]
    grid[0][0] = 'A'
    grid[0][1] = '3'
    grid[1][1] = '4'
    grid[2][1] = '5'
    grid[3][1] = '6'
    grid[4][1] = '7'
    board_str = '\n'.join('|' + ''.join(row) + '|' for row in grid)
    d = choose_direction(board_str, 'A', board_size=f'{n_rows}x{n_cols}', next_digit=3)
    assert d == 'right'


# -- v4: decision por puntos --------------------------------------------

V4_ROWS = ['............', '..XA.9......', '............', '.1........2.',
           '............', '....3...4...', '............', '...........B']


def test_v4_fin_de_partida_prefiere_el_9_multiplicado_a_la_x():
    # X a 1 paso (+50), 9 a 2 pasos (900 x 3 = 2700), me quedan 2 turnos.
    d = SnakeStrategy().choose_direction(
        make_board_str(V4_ROWS), 'A', board_size='8x12', my_score=0, opp_score=0,
        remaining_moves=4, my_multiplier=3, opp_multiplier=1)
    assert d == 'right'


def test_v4_ultimo_turno_agarra_la_x_si_el_digito_no_llega():
    # Me queda 1 turno: el 9 (a 2 pasos) no llega, la X suma 50.
    d = SnakeStrategy().choose_direction(
        make_board_str(V4_ROWS), 'A', board_size='8x12', my_score=0, opp_score=0,
        remaining_moves=2, my_multiplier=3, opp_multiplier=1)
    assert d == 'left'


def test_v4_principio_de_partida_prefiere_la_x_cercana():
    # Con toda la partida por delante el multiplicador se amortiza.
    rows = ['............', '..XA...1....', '............', '.5........2.',
            '............', '....3...4...', '............', '...........B']
    d = SnakeStrategy().choose_direction(
        make_board_str(rows), 'A', board_size='8x12', my_score=0, opp_score=0,
        remaining_moves=300, my_multiplier=1, opp_multiplier=1)
    assert d == 'left'


def test_v4_sin_remaining_moves_asume_partida_larga():
    rows = ['............', '..XA...1....', '............', '.5........2.',
            '............', '....3...4...', '............', '...........B']
    d = SnakeStrategy().choose_direction(make_board_str(rows), 'A', board_size='8x12')
    assert d == 'left'


def test_v4_turnos_propios_son_la_mitad_de_remaining_moves():
    assert SnakeStrategy._my_turns_left(300) == 150
    assert SnakeStrategy._my_turns_left(3) == 2


# -- esperar al lado del siguiente digito --------------------------------
# Tableros reales de una partida perdida (my_match 5): el rival llegaba
# antes al objetivo y el bot se iba a juntar 'X' en vez de esperar al
# siguiente digito.

TURNO_33 = ('|               |\n|               |\n|#           X  |\n|#              |\n'
            '|#   4          |\n|#        3     |\n|#   6 Aaa      |\n|#   bB  a      |\n'
            '|#   b          |\n|#   b     X    |\n|#              |\n|#              |\n'
            '|#      7       |\n| 5             |\n')

TURNO_57 = ('| 8  #######    |\n|               |\n|            X  |\n|               |\n'
            '|    4 Aaaa     |\n|         a     |\n|    6          |\n|               |\n'
            '|               |\n|               |\n|               |\n|          b    |\n'
            '|       7  bbBX |\n| 5             |\n')


def test_rival_gana_el_3_voy_a_esperar_al_4_en_vez_de_la_x():
    # Objetivo 3: el rival esta a 3 pasos. El 4 (siguiente) me queda cerca;
    # antes el bot bajaba a buscar la X de (9,10) y perdia tambien el 4.
    d = SnakeStrategy().choose_direction(
        TURNO_33, 'B', board_size='14x15', my_score=713, opp_score=712,
        remaining_moves=267, my_multiplier=3, opp_multiplier=5)
    assert d == 'up'


def test_agarro_la_x_pegada_si_igual_llego_al_siguiente_digito():
    # La X esta al lado y despues de comerla sigo llegando al 5 antes
    # que el rival (que primero tiene que comerse el 4).
    d = SnakeStrategy().choose_direction(
        TURNO_57, 'B', board_size='14x15', my_score=823, opp_score=2223,
        remaining_moves=243, my_multiplier=5, opp_multiplier=5)
    assert d == 'right'


def test_siguiente_digito_da_la_vuelta_de_9_a_1():
    board = Board(make_board_str(['9....', '.A...', '...1B', '6.7.8']), 'A', '4x5')
    assert board.target_digit == 6
    assert SnakeStrategy._next_digit_positions(board) == [(3, 2)]
    board = Board(make_board_str(['9....', '.A...', '...1B', '..2.3']), 'A', '4x5')
    assert board.target_digit == 9
    assert SnakeStrategy._next_digit_positions(board) == [(2, 3)]


def test_sin_digitos_no_hay_siguiente():
    board = Board(make_board_str(['.....', '.A...', '....B']), 'A', '3x5')
    assert SnakeStrategy._next_digit_positions(board) == []
    s = SnakeStrategy()
    assert s._plan_siguiente_digito(board, s._build_candidates(board), 0, None) is None


def test_espera_al_lado_del_siguiente_sin_pisarlo():
    # El 1 lo alcanza primero el rival (pegado). El 2 esta a mi lado:
    # no lo piso (hoy es un digito equivocado), me muevo a una celda vecina.
    rows = ['..........',
            '.2A.......',
            '..........',
            '..........',
            '.......1B.',
            '..........']
    d = SnakeStrategy().choose_direction(make_board_str(rows), 'A', board_size='6x10',
                                         my_score=0, opp_score=0, remaining_moves=200)
    assert d in ('up', 'down')


def test_x_inalcanzable_no_cuenta_para_el_plan():
    # Hay una X encerrada (sin camino): no se usa para comparar.
    rows = ['........#X',
            '.2A.....##',
            '..........',
            '..........',
            '.......1B.',
            '..........']
    board = Board(make_board_str(rows), 'A', '6x10')
    s = SnakeStrategy()
    cands = s._build_candidates(board)
    assert s._my_dist(cands, (0, 9)) is None
    assert s._plan_siguiente_digito(board, cands, 0, 'left') in ('up', 'down')


def test_rival_sin_camino_al_objetivo_igual_voy_al_siguiente():
    # El rival no tiene camino al 1: opp_to_next queda en None y la X
    # cercana gana (siempre llego primero).
    rows = ['..X.......',
            '.2A.......',
            '..........',
            '######....',
            '1....#..B.',
            '.....#....']
    board = Board(make_board_str(rows), 'A', '6x10')
    s = SnakeStrategy()
    cands = s._build_candidates(board)
    assert s._plan_siguiente_digito(board, cands, 0, 'up') is None


# -- arreglos de la partida my_match 6 -----------------------------------

TURNO_17_M6 = ('|                    |\n|                    |\n|    aaA   X         |\n'
               '|   2                |\n|               X    |\n|                    |\n'
               '| #######            |\n|                    |\n|                    |\n'
               '|              Bb    |\n|       1       b    |\n|     45         3   |\n'
               '|                    |\n|                    |\n')

TURNO_121_M6 = ('|                    |\n|      6             |\n|        #        7  |\n'
                '| aaa                |\n|   a                |\n|   A                |\n'
                '|                    |\n|              X   8 |\n|                    |\n'
                '|                    |\n|                  b |\n|     45         Bbb |\n'
                '|                    |\n|     X              |\n')


def test_no_encadena_x_si_pierdo_la_carrera_por_el_digito():
    # Estoy a 8 del 1 y el rival a 11. La X de arriba conviene en puntos,
    # pero despues de comerla el rival llega antes al 1. Voy al digito.
    d = SnakeStrategy().choose_direction(
        TURNO_17_M6, 'B', board_size='14x20', my_score=106, opp_score=58,
        remaining_moves=283, my_multiplier=3, opp_multiplier=2)
    assert d == 'down'


def test_no_espera_al_5_si_esta_pegado_al_4_del_rival():
    # El 4 y el 5 estan pegados: el rival se come los dos seguidos. Antes
    # el bot iba a esperar al 5 (left) y llegaba tarde.
    d = SnakeStrategy().choose_direction(
        TURNO_121_M6, 'B', board_size='14x20', my_score=3151, opp_score=1853,
        remaining_moves=179, my_multiplier=9, opp_multiplier=7)
    assert d != 'left'


def test_si_falta_el_digito_siguiente_no_hay_plan():
    # Solo hay 1 y 2: el 2 lo gana el rival y el 3 no esta en el tablero.
    rows = ['A...........',
            '............',
            '.........1B.',
            '.........2..']
    board = Board(make_board_str(rows), 'A', '4x12')
    s = SnakeStrategy()
    assert s._plan_siguiente_digito(board, s._build_candidates(board), 0, None) is None


def test_si_el_rival_gana_todas_las_carreras_no_hay_plan():
    # El rival esta pegado al 1 y el 2, 3 y 4 estan a su lado: no llego
    # antes a ninguno de los NEXT_DIGITS_AHEAD digitos siguientes.
    rows = ['A..........5',
            '............',
            '............',
            '............',
            '............',
            '.........B1.',
            '..........23',
            '..........4.']
    board = Board(make_board_str(rows), 'A', '8x12')
    s = SnakeStrategy()
    assert s._plan_siguiente_digito(board, s._build_candidates(board), 0, None) is None


# -- partida my_match 7: multiplicador atrasado --------------------------

TURNO_62_M7 = ('|            X      |\n|  2                |\n|                   |\n'
               '|                   |\n|                   |\n|                   |\n'
               '|                   |\n|     1             |\n|        Bb         |\n'
               '|7        b         |\n|         bb        |\n|                   |\n'
               '|          a        |\n|          a        |\n|   8      a        |\n'
               '|       Aaaa    9   |\n|             X     |\n|        #########  |\n'
               '|                   |\n')


def test_con_multiplicador_atrasado_paso_por_la_x_antes_de_esperar():
    # El rival (x3) va por el 7; yo (x1) espero al 8. Pasar por la X de
    # abajo me hace llegar al 8 dos pasos "tarde" segun el calculo, pero
    # estando atrasada en multiplicador vale la pena (el rival tardo 21
    # turnos en llegar al 7, no 9).
    d = SnakeStrategy().choose_direction(
        TURNO_62_M7, 'A', board_size='19x19', my_score=1627, opp_score=1227,
        remaining_moves=238, my_multiplier=1, opp_multiplier=3)
    assert d == 'down'


def test_con_multiplicador_parejo_no_arriesga_el_siguiente_digito():
    # Mismo tablero, pero con multiplicadores parejos: sigue esperando.
    d = SnakeStrategy().choose_direction(
        TURNO_62_M7, 'A', board_size='19x19', my_score=1627, opp_score=1227,
        remaining_moves=238, my_multiplier=3, opp_multiplier=3)
    assert d == 'up'


# -- partida my_match 9: el rival no va derecho al objetivo ---------------

TURNOS_53_A_59_M9 = [
    ('|                |\n|       8        |\n|                |\n|                |\n'
     '|      #         |\n|             7  |\n| 4    A      X  |\n|      aa        |\n'
     '| 6     a        |\n|                |\n|        bbb     |\n|        b       |\n'
     '|        B  X    |\n|           5    |\n|                |\n|                |\n'
     '|                |\n|                |\n|                |\n', 1022, 1024, 247, 3, 3),
    ('|                |\n|       8        |\n|                |\n|                |\n'
     '|                |\n|             7  |\n| 4    aA     X  |\n|      aa        |\n'
     '| 6              |\n|                |\n|        bb      |\n| ###    b       |\n'
     '|        bB X    |\n|           5    |\n|                |\n|                |\n'
     '|                |\n|                |\n|                |\n', 1023, 1025, 245, 3, 3),
    ('|                |\n|       8        |\n|                |\n|                |\n'
     '|                |\n|             7  |\n| 4    aa     X  |\n|      aA        |\n'
     '| 6              |\n|                |\n|        b       |\n|  #     b       |\n'
     '|        bbBX    |\n|           5    |\n|                |\n|                |\n'
     '|                |\n|                |\n|                |\n', 1024, 1026, 243, 3, 3),
    ('|                |\n|       8        |\n|                |\n|                |\n'
     '|                |\n|             7  |\n| 4    aa     X  |\n|       aA       |\n'
     '| 6              |\n|                |\n|                |\n|        b       |\n'
     '|        bbbB    |\n|           5    |\n|                |\n|    #########   |\n'
     '|            X   |\n|                |\n|                |\n', 1074, 1027, 241, 4, 3),
]


def _jugar_turno(strategy, turno):
    board_str, my_score, opp_score, remaining, my_mult, opp_mult = turno
    return strategy.choose_direction(
        board_str, 'B', board_size='19x16', my_score=my_score, opp_score=opp_score,
        remaining_moves=remaining, my_multiplier=my_mult, opp_multiplier=opp_mult)


def test_si_el_rival_se_aleja_del_objetivo_voy_a_disputarlo():
    # El rival (A) esta mas cerca del 4, pero turno a turno se aleja
    # (5 -> 8 -> 9 -> 10 pasos) porque anda juntando X. En la partida
    # real tardo 28 turnos en comerselo (2400 puntos). Despues de 3
    # turnos sin acercarse, el bot va a disputarlo.
    strategy = SnakeStrategy()
    for turno in TURNOS_53_A_59_M9[:-1]:
        _jugar_turno(strategy, turno)
    assert strategy._race_stall == 2
    assert _jugar_turno(strategy, TURNOS_53_A_59_M9[-1]) == 'up'
    assert strategy._race_stall == 3


def test_sin_historial_el_rival_mas_cerca_gana_la_carrera():
    # El mismo tablero visto sin historial (primer turno): como antes,
    # el bot no disputa el 4.
    assert _jugar_turno(SnakeStrategy(), TURNOS_53_A_59_M9[-1]) == 'right'


def _race_board(opp_col, digit_col=0):
    row = ['.'] * 12
    row[digit_col] = '1'
    row[opp_col] = 'B'
    rows = ['A...........', '............', ''.join(row)]
    return Board(make_board_str(rows), 'A', '3x12')


def test_update_race_sube_baja_tope_y_reinicio():
    s = SnakeStrategy()

    def paso(board):
        s._opp_dist = board.bfs_all_distances(board.opponent_head, set())
        s._update_race(board)

    paso(_race_board(5))
    assert s._race_stall == 0            # primer turno: sin historial
    paso(_race_board(6))
    assert s._race_stall == 1            # se alejo
    paso(_race_board(6))
    assert s._race_stall == 2            # no se acerco
    assert s._food_bonus == 2 * RACE_STALL_BONUS
    paso(_race_board(5))
    assert s._race_stall == 1            # se acerco: descuenta de a uno
    for _ in range(RACE_STALL_MAX + 5):
        paso(_race_board(11))
    assert s._race_stall == RACE_STALL_MAX
    paso(_race_board(11, digit_col=3))   # el objetivo cambio de lugar
    assert s._race_stall == 0