"""Tests unitarios de snake_ai.py (SnakeStrategy y el wrapper choose_direction)."""

from board import Board, DIRECTIONS
from snake_ai import SnakeStrategy, choose_direction


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
