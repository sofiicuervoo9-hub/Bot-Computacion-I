"""Tests unitarios de board.py."""

from board import Board, DIRECTIONS


def make_board_str(rows):
    return '\n'.join('|' + row + '|' for row in rows)


# -- parseo y dimensiones -------------------------------------------------

def test_parse_dimensions_from_board_size():
    board_str = make_board_str(['.....', '.A...', '.....'])
    b = Board(board_str, 'A', board_size='3x5')
    assert (b.n_rows, b.n_cols) == (3, 5)


def test_parse_dimensions_fallback_sin_board_size():
    board_str = make_board_str(['.....', '.A...', '.....'])
    b = Board(board_str, 'A')
    assert (b.n_rows, b.n_cols) == (3, 5)


def test_parse_dimensions_board_size_malformado_usa_fallback():
    board_str = make_board_str(['.....', '.A...', '.....'])
    b = Board(board_str, 'A', board_size='no-es-un-tamano')
    assert (b.n_rows, b.n_cols) == (3, 5)


def test_parse_dimensions_filas_desparejas_usa_minimo():
    # la fila mas corta (".A", 2 caracteres tras sacar los bordes '|')
    # marca el limite de columnas usable, no la mas larga (5)
    board_str = "|.....|\n|.A|\n|.....|"
    b = Board(board_str, 'A')
    assert b.n_cols == 2


def test_char_at_fuera_de_rango_no_rompe():
    board_str = make_board_str(['.....', '.A...'])
    # board_size mas grande que las filas reales: _char_at debe devolver
    # None para las filas/columnas que no existen, sin explotar.
    b = Board(board_str, 'A', board_size='5x8')
    assert b.n_rows == 5
    assert b.head == (1, 1)


# -- cabeza, cuerpo, comida, rival -----------------------------------------

def test_detecta_cabeza_cuerpo_comida_y_rival():
    board_str = make_board_str([
        '.......',
        '.aaA...',
        '.......',
        '...*...',
        '...bB..',
    ])
    b = Board(board_str, 'A')
    assert b.head == (1, 3)
    assert b.opponent_head == (4, 4)
    assert (1, 1) in b.body_cells and (1, 2) in b.body_cells
    assert (4, 3) in b.opponent_blocked and (4, 4) in b.opponent_blocked
    assert (3, 3) in b.food


def test_sin_cabeza_propia():
    board_str = make_board_str(['.....', '.....'])
    b = Board(board_str, 'A')
    assert b.head is None
    assert b.ordered_body == []
    assert b.tail is None


def test_trace_body_encuentra_la_cola():
    board_str = make_board_str([
        '.......',
        '.aaaA..',
        '.......',
    ])
    b = Board(board_str, 'A')
    assert b.ordered_body[0] == b.head
    assert b.tail == (1, 1)  # el extremo mas lejano de la cabeza


def test_trace_body_cuerpo_desconectado_no_encuentra_cola():
    # 'a' suelto, no adyacente a la cabeza: trace_body no la alcanza,
    # asi que ordered_body queda mas corto que body_cells y tail es None.
    board_str = make_board_str([
        'a......',
        '.......',
        '...A...',
    ])
    b = Board(board_str, 'A')
    assert b.tail is None


# -- geometria: vecinos, manhattan, bfs -------------------------------------

def test_neighbors_respeta_bordes():
    board_str = make_board_str(['...', '...', '...'])
    b = Board(board_str, 'A')
    vecinos = dict(b.neighbors((0, 0)))
    assert set(vecinos.keys()) == {'down', 'right'}
    assert vecinos['down'] == (1, 0)
    assert vecinos['right'] == (0, 1)


def test_neighbors_centro_tiene_las_cuatro_direcciones():
    board_str = make_board_str(['...', '...', '...'])
    b = Board(board_str, 'A')
    vecinos = dict(b.neighbors((1, 1)))
    assert set(vecinos.keys()) == set(DIRECTIONS.keys())


def test_manhattan():
    assert Board.manhattan((0, 0), (3, 4)) == 7
    assert Board.manhattan((2, 2), (2, 2)) == 0


def test_bfs_all_distances_basico():
    board_str = make_board_str(['.....', '.....', '.....'])
    b = Board(board_str, 'A')
    dist = b.bfs_all_distances((0, 0), blocked=set())
    assert dist[(0, 0)] == 0
    assert dist[(2, 4)] == 6  # manhattan en grilla abierta


def test_bfs_all_distances_start_none_o_bloqueado():
    board_str = make_board_str(['...', '...'])
    b = Board(board_str, 'A')
    assert b.bfs_all_distances(None, set()) == {}
    assert b.bfs_all_distances((0, 0), blocked={(0, 0)}) == {}


def test_bfs_all_distances_respeta_bloqueados():
    board_str = make_board_str(['...', '...', '...'])
    b = Board(board_str, 'A')
    # bloqueamos toda la fila del medio salvo una celda, para forzar un
    # desvio y confirmar que blocked realmente restringe el paso.
    blocked = {(1, 0), (1, 1)}
    dist = b.bfs_all_distances((0, 0), blocked)
    assert (2, 0) in dist
    assert dist[(2, 0)] > 2  # tuvo que rodear


# -- v3: comida numerica ----------------------------------------------------

def test_sin_digitos_es_modo_apple():
    board_str = make_board_str(['.....', '.A*..'])
    b = Board(board_str, 'A')
    assert b.target_digit is None
    assert b.target_digit_pos is None
    assert b.wrong_digit_positions == set()
    assert b.food == [(1, 2)]


def test_target_digit_inferido_sin_wraparound():
    board_str = make_board_str(['.1...', '..2..', '...3.', 'A..4.', '....5'])
    b = Board(board_str, 'A')
    assert b.target_digit == 1
    assert b.target_digit_pos == (0, 1)
    assert b.food == [(0, 1)]
    assert b.wrong_digit_positions == {(1, 2), (2, 3), (3, 3), (4, 4)}


def test_target_digit_inferido_con_wraparound():
    board_str = make_board_str(['.7...', '..8..', '...9.', 'A..1.', '....2'])
    b = Board(board_str, 'A')
    assert b.target_digit == 7
    assert b.target_digit_pos == (0, 1)


def test_next_digit_del_server_pisa_la_inferencia():
    board_str = make_board_str(['.7...', '..8..', '...9.', 'A..1.', '....2'])
    b = Board(board_str, 'A', next_digit=9)
    assert b.target_digit == 9
    assert b.target_digit_pos == (2, 3)
    assert b.food == [(2, 3)]
    assert (0, 1) in b.wrong_digit_positions


def test_next_digit_no_presente_en_tablero():
    board_str = make_board_str(['.7...', '..8..', '...9.', 'A..1.', '....2'])
    b = Board(board_str, 'A', next_digit=4)
    assert b.target_digit == 4
    assert b.target_digit_pos is None
    assert b.food == []
    # como no hay posicion objetivo, todos los digitos son "incorrectos"
    assert len(b.wrong_digit_positions) == 5


def test_next_digit_invalido_cae_a_inferencia():
    board_str = make_board_str(['.1...', 'A..2.', '...3.', '4....', '....5'])
    b = Board(board_str, 'A', next_digit='no-es-numero')
    assert b.target_digit == 1  # se ignora el next_digit invalido


def test_locate_digit_con_none_no_rompe():
    board_str = make_board_str(['.1...'])
    b = Board(board_str, 'A')
    assert b._locate_digit(None) is None


def test_side_b_invierte_cabeza_cuerpo_propio_y_rival():
    board_str = make_board_str(['.......', '.aaA...', '.......', '...bB..'])
    b = Board(board_str, 'B')
    assert b.head == (3, 4)
    assert b.opponent_head == (1, 3)


# -- v4: pickups de multiplicador ('X') --------------------------------

def test_detecta_pickups_de_multiplicador():
    board_str = make_board_str([
        '.......',
        '.A..X..',
        '.......',
        '..X....',
    ])
    b = Board(board_str, 'A')
    assert set(b.multiplier_pickups) == {(1, 4), (3, 2)}


def test_pickup_no_se_confunde_con_digito_ni_bloquea():
    # Un 'X' junto a los digitos v3: no debe terminar ni en digit_values
    # ni en wrong_digit_positions, y sigue siendo una celda transitable
    # (no aparece en body_cells ni en opponent_blocked).
    board_str = make_board_str(['.1...', 'A..2.', '.X.3.', '4....', '....5'])
    b = Board(board_str, 'A')
    assert (2, 1) in b.multiplier_pickups
    assert (2, 1) not in b.digit_values
    assert (2, 1) not in b.wrong_digit_positions
    assert (2, 1) not in b.body_cells
    assert (2, 1) not in b.opponent_blocked


def test_sin_pickups_lista_vacia():
    board_str = make_board_str(['.....', '.A*..'])
    b = Board(board_str, 'A')
    assert b.multiplier_pickups == []


# -- v5: muro ('#') ----------------------------------------------------

def test_detecta_celdas_de_muro():
    board_str = make_board_str([
        '.......',
        '.A..#..',
        '.......',
        '..#....',
        '..#....',
    ])
    b = Board(board_str, 'A')
    assert b.wall_cells == {(1, 4), (3, 2), (4, 2)}


def test_muro_no_se_confunde_con_otras_celdas():
    # Una celda de muro junto a digitos v3 y un pickup v4: no debe
    # terminar en digit_values, wrong_digit_positions, multiplier_pickups,
    # body_cells ni opponent_blocked -- sigue siendo transitable a nivel
    # de deteccion (el bloqueo se maneja aparte, en snake_ai).
    board_str = make_board_str(['.1...', 'A..2.', '.#.3.', '4.X..', '....5'])
    b = Board(board_str, 'A')
    assert (2, 1) in b.wall_cells
    assert (2, 1) not in b.digit_values
    assert (2, 1) not in b.wrong_digit_positions
    assert (2, 1) not in b.multiplier_pickups
    assert (2, 1) not in b.body_cells
    assert (2, 1) not in b.opponent_blocked


# -- v6: copias multiples de cada digito ---------------------------------

def test_v6_todas_las_copias_del_objetivo_son_comida():
    board_str = make_board_str([
        '3....4',
        '..A...',
        '5..3..',
        '......',
        '6....3',
        '7..4..',
    ])
    b = Board(board_str, 'A', next_digit=3)
    assert b.target_digit_positions == [(0, 0), (2, 3), (4, 5)]
    assert set(b.food) == {(0, 0), (2, 3), (4, 5)}
    assert b.target_digit_pos == (0, 0)  # compatibilidad: primera en orden de lectura
    # Ninguna copia del objetivo es "equivocada"; todas las de los otros si.
    assert b.wrong_digit_positions == {(0, 5), (2, 0), (4, 0), (5, 0), (5, 3)}


def test_v6_inferencia_del_objetivo_con_copias_repetidas():
    # Sin next_digit: la inferencia usa el conjunto de valores, asi que
    # las copias repetidas no la confunden.
    board_str = make_board_str(['4.5.6.', 'A.4.8.', '5.7.6.', '8.7.4.'])
    b = Board(board_str, 'A')
    assert b.target_digit == 4
    assert len(b.target_digit_positions) == 3


def test_locate_all_digits_con_none_devuelve_lista_vacia():
    b = Board(make_board_str(['.1...']), 'A')
    assert b._locate_all_digits(None) == []


def test_sin_muro_lista_vacia():
    board_str = make_board_str(['.....', '.A*..'])
    b = Board(board_str, 'A')
    assert b.wall_cells == set()
