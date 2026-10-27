"""Tests unitarios de snake_ai.py (SnakeStrategy y el wrapper
choose_direction)."""

import unittest
import time

from board import STAR, Board, DIRECTIONS
from snake_ai import (
    FALLBACK_DIRECTION,
    FIXED_PENALTY,
    RACE_STALL_BONUS,
    RACE_STALL_MAX,
    TAIL_FOOD_POINTS,
    WAIT_WIN_PROB,
    WRONG_DIGIT_STEP_PENALTY,
    EscapeSearch,
    SnakeStrategy,
    choose_direction,
    safe_direction,
)

TAIL_A, TAIL_B = 'Ⓐ', 'Ⓑ'
BIG, SMALL = '\U0001f4a3', '\U0001f9e8'


def make_board_str(rows):
    return '\n'.join('|' + row + '|' for row in rows)


def make_grid(n_rows, n_cols):
    return [['.' for _ in range(n_cols)] for _ in range(n_rows)]


def grid_to_str(grid):
    return '\n'.join('|' + ''.join(row) + '|' for row in grid)


def bottleneck_grid():
    """Fila de cuerpo rival con una sola abertura, justo arriba de A."""
    grid = make_grid(10, 10)
    grid[1][2] = 'B'
    grid[4][3] = 'A'
    for c in range(10):
        grid[3][c] = 'b'
    grid[3][3] = '.'
    return grid


# -- casos basicos ---------------------------------------------------------


# -- modo cazador ---------------------------------------------------------


# -- v3: digitos en orden ---------------------------------------------------


# -- v4: pickups de multiplicador ('X') --------------------------------


# -- v5: muro ('#') -----------------------------------------------------

WALL_ROWS = ['.....', '.....', '..A#.', '.....', '.....']


# -- v6: copias multiples de cada digito ---------------------------------


# -- v4: decision por puntos --------------------------------------------

V4_ROWS = [
    '............',
    '..XA.9......',
    '............',
    '.1........2.',
    '............',
    '....3...4...',
    '............',
    '...........B',
]
V4_EARLY_ROWS = [
    '............',
    '..XA...1....',
    '............',
    '.5........2.',
    '............',
    '....3...4...',
    '............',
    '...........B',
]


# -- esperar al lado del siguiente digito (partida my_match 5) ------------

TURN_33_M5 = (
    '|               |\n'
    '|               |\n'
    '|#           X  |\n'
    '|#              |\n'
    '|#   4          |\n'
    '|#        3     |\n'
    '|#   6 Aaa      |\n'
    '|#   bB  a      |\n'
    '|#   b          |\n'
    '|#   b     X    |\n'
    '|#              |\n'
    '|#              |\n'
    '|#      7       |\n'
    '| 5             |\n'
)

TURN_57_M5 = (
    '| 8  #######    |\n'
    '|               |\n'
    '|            X  |\n'
    '|               |\n'
    '|    4 Aaaa     |\n'
    '|         a     |\n'
    '|    6          |\n'
    '|               |\n'
    '|               |\n'
    '|               |\n'
    '|               |\n'
    '|          b    |\n'
    '|       7  bbBX |\n'
    '| 5             |\n'
)


# -- partida my_match 6 -----------------------------------------------

TURN_17_M6 = (
    '|                    |\n'
    '|                    |\n'
    '|    aaA   X         |\n'
    '|   2                |\n'
    '|               X    |\n'
    '|                    |\n'
    '| #######            |\n'
    '|                    |\n'
    '|                    |\n'
    '|              Bb    |\n'
    '|       1       b    |\n'
    '|     45         3   |\n'
    '|                    |\n'
    '|                    |\n'
)

TURN_121_M6 = (
    '|                    |\n'
    '|      6             |\n'
    '|        #        7  |\n'
    '| aaa                |\n'
    '|   a                |\n'
    '|   A                |\n'
    '|                    |\n'
    '|              X   8 |\n'
    '|                    |\n'
    '|                    |\n'
    '|                  b |\n'
    '|     45         Bbb |\n'
    '|                    |\n'
    '|     X              |\n'
)


# -- partida my_match 7: multiplicador atrasado --------------------------

TURN_62_M7 = (
    '|            X      |\n'
    '|  2                |\n'
    '|                   |\n'
    '|                   |\n'
    '|                   |\n'
    '|                   |\n'
    '|                   |\n'
    '|     1             |\n'
    '|        Bb         |\n'
    '|7        b         |\n'
    '|         bb        |\n'
    '|                   |\n'
    '|          a        |\n'
    '|          a        |\n'
    '|   8      a        |\n'
    '|       Aaaa    9   |\n'
    '|             X     |\n'
    '|        #########  |\n'
    '|                   |\n'
)


# -- partida my_match 9: el rival no va derecho al objetivo ---------------

TURNS_53_TO_59_M9 = [
    (
        '|                |\n'
        '|       8        |\n'
        '|                |\n'
        '|                |\n'
        '|      #         |\n'
        '|             7  |\n'
        '| 4    A      X  |\n'
        '|      aa        |\n'
        '| 6     a        |\n'
        '|                |\n'
        '|        bbb     |\n'
        '|        b       |\n'
        '|        B  X    |\n'
        '|           5    |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n',
        1022, 1024, 247, 3, 3,
    ),
    (
        '|                |\n'
        '|       8        |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|             7  |\n'
        '| 4    aA     X  |\n'
        '|      aa        |\n'
        '| 6              |\n'
        '|                |\n'
        '|        bb      |\n'
        '| ###    b       |\n'
        '|        bB X    |\n'
        '|           5    |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n',
        1023, 1025, 245, 3, 3,
    ),
    (
        '|                |\n'
        '|       8        |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|             7  |\n'
        '| 4    aa     X  |\n'
        '|      aA        |\n'
        '| 6              |\n'
        '|                |\n'
        '|        b       |\n'
        '|  #     b       |\n'
        '|        bbBX    |\n'
        '|           5    |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n',
        1024, 1026, 243, 3, 3,
    ),
    (
        '|                |\n'
        '|       8        |\n'
        '|                |\n'
        '|                |\n'
        '|                |\n'
        '|             7  |\n'
        '| 4    aa     X  |\n'
        '|       aA       |\n'
        '| 6              |\n'
        '|                |\n'
        '|                |\n'
        '|        b       |\n'
        '|        bbbB    |\n'
        '|           5    |\n'
        '|                |\n'
        '|    #########   |\n'
        '|            X   |\n'
        '|                |\n'
        '|                |\n',
        1074, 1027, 241, 4, 3,
    ),
]


def play_turn(strategy, turn):
    board_str, my_score, opp_score, remaining, my_mult, opp_mult = turn
    return strategy.choose_direction(
        board_str,
        'B',
        board_size='19x16',
        my_score=my_score,
        opp_score=opp_score,
        remaining_moves=remaining,
        my_multiplier=my_mult,
        opp_multiplier=opp_mult,
    )


def race_board(opp_col, digit_col=0):
    row = ['.'] * 12
    row[digit_col] = '1'
    row[opp_col] = 'B'
    return Board(
        make_board_str(['A...........', '............', ''.join(row)]),
        'A',
        '3x12',
    )


def race_step(strategy, board):
    strategy._opp_dist = board.bfs_all_distances(board.opponent_head, set())
    strategy._update_race(board)
    return strategy._race_stall


# -- v7: choques y comida de cola ---------------------------------------


# -- v8: bombas de proximidad -------------------------------------------


def put(grid, cells, value):
    for r, c in cells:
        grid[r][c] = value


def big_v8_board():
    """Tablero 30x30 con una vibora larga en serpentina, bombas y digitos."""
    g = make_grid(30, 30)
    body = [
        (r, c)
        for r in range(2, 12)
        for c in (range(2, 26) if r % 2 == 0 else range(25, 1, -1))
    ]
    put(g, body[1:], 'a')
    put(g, body[:1], 'A')
    put(g, [(20, 5), (25, 25)], BIG)
    put(g, [(15, 15), (18, 28), (28, 2), (14, 1), (27, 14)], SMALL)
    put(g, [(22, 22)], 'B')
    for cell, value in [
        ((17, 10), '3'),
        ((26, 20), '4'),
        ((13, 27), '5'),
        ((29, 29), '6'),
        ((16, 4), '7'),
    ]:
        put(g, [cell], value)
    put(g, [(19, 19)], 'X')
    return grid_to_str(g)


# -- partida my_match 12: carrera contra cualquier copia ---------------------

TURN_207_M12 = (
    '| 7                  |\n'
    '|       7   1  7     |\n'
    '|        9           |\n'
    '|             2      |\n'
    '|                    |\n'
    '|                    |\n'
    '|                    |\n'
    '|    7             8 |\n'
    '|#  8 9       b      |\n'
    '|#        Bbbbbb    X|\n'
    '|#        bb8bbb     |\n'
    '|            9       |\n'
    '|            2   a   |\n'
    '|               aa   |\n'
    '| X            aa   2|\n'
    '|         1    aaa   |\n'
    '|              1 A   |\n'
    '|       2     8 7    |\n'
    '|                    |\n'
)


# -- partida my_match 13: no encerrar el digito que espero --------------------

TURN_261_M13 = (
    '|                    |\n'
    '|9                   |\n'
    '|                    |\n'
    '| 4                  |\n'
    '|3                   |\n'
    '|                    |\n'
    '|              2     |\n'
    '| 31   2   114       |\n'
    '|X          4        |\n'
    '|                  X |\n'
    '|         2          |\n'
    '|  9              9  |\n'
    '|                    |\n'
    '|  A                 |\n'
    '|  a      #          |\n'
    '|  a         3       |\n'
    '|aaa        4       2|\n'
    '|a            Bbb    |\n'
    '| 2            1b    |\n'
    '|1         3  bbb    |\n'
)


TURN_393_M13 = (
    '|            3  4    |\n'
    '|                    |\n'
    '|                    |\n'
    '|  aaA       X       |\n'
    '|                    |\n'
    '|      1           2 |\n'
    '| 1          3    4  |\n'
    '|       3   3   3    |\n'
    '|            1 #     |\n'
    '|              #     |\n'
    '|              #   4 |\n'
    '|              #    5|\n'
    '|     1        #5    |\n'
    '|                    |\n'
    '|                    |\n'
    '|                    |\n'
    '|   2            2   |\n'
    '|               Bbb  |\n'
    '|         5          |\n'
    '|        X 5         |\n'
)


# -- partida my_match 14: encierro al acercarse / encadenar digitos -------

TURN_285_M14 = (
    '|6    22           |\n'
    '|    3             |\n'
    '| X     5    4     |\n'
    '|                  |\n'
    '|         3        |\n'
    '|   5              |\n'
    '|     5    bbb     |\n'
    '|          b2bb    |\n'
    '|2         B  b    |\n'
    '|             b    |\n'
    '|    aa2           |\n'
    '|3   a3  4         |\n'
    '| 6  aA            |\n'
    '|    aa     6X    4|\n'
    '|       ###########|\n'
    '|3          5      |\n'
)


# -- partida my_match 15: pasillo cuya unica salida es un digito equivocado -

TURN_97_M15 = (
    '|         3  5 |\n'
    '|   6        X |\n'
    '|5 aaaaa     X |\n'
    '| aa       6  #|\n'
    '| aaaaaa      #|\n'
    '| Baaaaa4     #|\n'
    '|5ba  aa7     #|\n'
    '| baaa4A      #|\n'
    '|6baaaaa   7  #|\n'
    '| b           #|\n'
    '| bbb  bb     #|\n'
    '|37 bbbbb4    #|\n'
    '|   7 63b      |\n'
    '|       b   6  |\n'
)


# -- partida my_match 19: el rival corta la salida --------------------------

TURN_133_M19 = (
    '|        8          2 |\n'
    '|                     |\n'
    '|                     |\n'
    '| \U0001f9e8   \U0001f9e8            7  |\n'
    '|                     |\n'
    '|       bb9        \U0001f9e8 \U0001f9e8|\n'
    '|   7    b            |\n'
    '|1       b            |\n'
    '|       2bbbbbb       |\n'
    '|     2 7  9  b       |\n'
    '|        A Bbbb      9|\n'
    '|        aa        7  |\n'
    '|    aaaa a    #      |\n'
    '|       a a    #    8 |\n'
    '|   1   a a    #      |\n'
    '|       aaa    #      |\n'
    '|  8           # 2    |\n'
    '|                  X  |\n'
    '|1            8       |\n'
    '|                 X   |\n'
    '|                     |\n'
    '| \U0001f4a3      \U0001f4a3  1         |\n'
    '|      \U0001f9e8    8         |\n'
)


# -- correccion 19/10: cuerpo con memoria, cola como jugada, camino, ritmo --


def plus_shaped_trap():
    """Zona en forma de cruz: 9 celdas, pero el camino simple mas largo es de
    5."""
    grid = [['#'] * 9 for _ in range(7)]
    for cell in [
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (3, 5),
        (1, 3),
        (2, 3),
        (4, 3),
        (5, 3),
    ]:
        grid[cell[0]][cell[1]] = '.'
    body = [(3, 6), (3, 7), (3, 8), (4, 8), (5, 8), (6, 8), (6, 7)]
    for r, c in body[1:]:
        grid[r][c] = 'a'
    grid[3][6] = 'A'
    return grid_to_str(grid)


# -- v9/v10: comida de disparo, estrella e invencibilidad -----------------

V10_DIGITS = {
    (8, 8): '1',
    (8, 10): '2',
    (0, 0): '3',
    (9, 0): '4',
    (0, 11): '5',
}
NORMAL_A = {(2, 1): 'a', (2, 2): 'a', (2, 3): 'A'}
INVINCIBLE_A = {(2, 1): 'A', (2, 2): 'A', (2, 3): 'a'}
NORMAL_B = {(6, 6): 'B', (6, 7): 'b', (6, 8): 'b'}
INVINCIBLE_B = {(6, 6): 'b', (6, 7): 'B', (6, 8): 'B'}


def v10_board_str(cells, n_rows=10, n_cols=12):
    grid = [[' '] * n_cols for _ in range(n_rows)]
    for (r, c), ch in {**V10_DIGITS, **cells}.items():
        grid[r][c] = ch
    return '\n'.join('|' + ''.join(row) + '|' for row in grid)


def v10_choose(cells, invincible=(0, 0)):
    return SnakeStrategy().choose_direction(
        v10_board_str(cells),
        'A',
        board_size='10x12',
        my_score=500,
        opp_score=300,
        remaining_moves=300,
        my_multiplier=1,
        opp_multiplier=1,
        invincible=invincible,
    )


# -- partida my_match 20: desvio a un 'X' que hace perder el 9 ---------------

MATCH20_ROWS = [
    '    2        3 1          ',
    ' ' + SMALL + '            #####       ',
    '                    4     ',
    '                       9  ',
    '      aa                  ',
    '     aaaaA                ',
    '  1               4       ',
    '        1     ' + SMALL + '  9   3    ',
    '           X4    1      3 ',
    '           Bbbbbbb        ',
    '                          ',
    '                       ' + BIG + BIG + ' ',
    '          2       4       ',
    '            3   3  X      ',
    '                          ',
    '                          ',
    SMALL + SMALL + '       9      ' + SMALL + '         ',
    '                          ',
    '             9            ',
    '        2            9    ',
    '                          ',
]


class SnakeStrategyTest(unittest.TestCase):
    """Tests de SnakeStrategy."""

    def test_without_head_returns_random_direction(self):
        d = SnakeStrategy().choose_direction(
            make_board_str(['.....', '.....']), 'A'
        )
        assert d in DIRECTIONS

    def test_invalid_board_does_not_break(self):
        d = SnakeStrategy().choose_direction(
            'esto no es un tablero valido', 'A'
        )
        assert d in DIRECTIONS

    def test_goes_straight_to_nearest_safe_food(self):
        board_str = make_board_str(
            [
                '.........',
                '.........',
                '..A......',
                '..*......',
                '.........',
            ]
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
        )
        assert d == 'down'

    def test_food_reached_first_by_opponent_does_not_break(self):
        board_str = make_board_str(
            [
                'A........',
                '.........',
                '.........',
                '.........',
                '........B',
                '.......*.',
            ]
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
        )
        assert d in DIRECTIONS

    def test_without_food_uses_territory_mode(self):
        board_str = make_board_str(['.........', '..A......', '.........'])
        assert SnakeStrategy().choose_direction(board_str, 'A') in DIRECTIONS

    def test_avoids_crashing_into_own_body(self):
        board_str = make_board_str(
            [
                '.......',
                '.aaa...',
                '.aAa...',
                '.......',
            ]
        )
        assert SnakeStrategy().choose_direction(board_str, 'A') == 'down'

    def test_without_legal_move_picks_a_fixed_direction_not_random(self):
        board_str = make_board_str(
            [
                '.......',
                '.BBB...',
                '.BAB...',
                '.BBB...',
            ]
        )
        picks = {
            SnakeStrategy().choose_direction(board_str, 'A') for _ in range(10)
        }
        assert picks == {'up'}

    def test_without_head_returns_fallback_direction(self):
        assert (
            SnakeStrategy().choose_direction(make_board_str(['...']), 'A')
            == FALLBACK_DIRECTION
        )

    def test_safety_buffer_when_winning_near_the_end(self):
        board_str = make_board_str(
            ['.........', '..A......', '..*......', '.........']
        )
        d = SnakeStrategy(safety_buffer=3).choose_direction(
            board_str, 'A', my_score=50, opp_score=10, remaining_moves=5
        )
        assert d in DIRECTIONS

    def test_no_safety_buffer_when_losing(self):
        board_str = make_board_str(
            ['.........', '..A......', '..*......', '.........']
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=1, opp_score=50, remaining_moves=5
        )
        assert d in DIRECTIONS

    def test_is_aggressive_only_when_winning_by_more_than_margin(self):
        strategy = SnakeStrategy(aggressive_margin=10)
        scores = [(50, 30), (35, 30), (20, 30), (None, 30), (50, None)]
        assert [strategy._is_aggressive(*pair) for pair in scores] == [
            True,
            False,
            False,
            False,
            False,
        ]

    def test_build_candidates_computes_opp_space_at_bottleneck(self):
        # Tapar la abertura ('up') deja al rival con mucho menos espacio.
        board = Board(grid_to_str(bottleneck_grid()), 'A', '10x10')
        candidates = SnakeStrategy()._build_candidates(board)
        assert candidates['up']['opp_space'] < candidates['down']['opp_space']
        assert candidates['up']['opp_space'] < candidates['left']['opp_space']
        assert candidates['up']['opp_space'] < candidates['right']['opp_space']

    def test_aggressive_mode_prefers_shrinking_opponent_over_territory(self):
        board = Board(make_board_str(['.....', '..A..', '.....']), 'A')
        candidates = {
            'up': {
                'dir': 'up',
                'pos': (0, 2),
                'space': 10,
                'body_len': 1,
                'territory': 5,
                'opp_space': 2,
                'wrong_digit': False,
            },
            'down': {
                'dir': 'down',
                'pos': (2, 2),
                'space': 10,
                'body_len': 1,
                'territory': 9,
                'opp_space': 20,
                'wrong_digit': False,
            },
        }
        strategy = SnakeStrategy()
        assert (
            strategy._best_territory_move(board, candidates, aggressive=False)
            == 'down'
        )
        assert (
            strategy._best_territory_move(board, candidates, aggressive=True)
            == 'up'
        )

    def test_aggressive_mode_end_to_end_closes_the_gap(self):
        d = SnakeStrategy().choose_direction(
            grid_to_str(bottleneck_grid()),
            'A',
            board_size='10x10',
            my_score=100,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'up'

    def test_prefers_step_without_wrong_digit_on_tie(self):
        grid = make_grid(10, 10)
        grid[2][2] = 'A'
        grid[2][3] = '7'
        grid[5][5] = '5'
        grid[0][0] = '6'
        grid[0][9] = '8'
        grid[9][0] = '9'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'down'

    def test_avoids_wrong_digit_even_on_shortest_path(self):
        # El objetivo (1) esta detras de un 6 pegado a la cabeza.
        grid = make_grid(10, 10)
        grid[5][1] = '1'
        grid[5][4] = '6'
        grid[5][5] = 'A'
        grid[0][0] = '2'
        grid[0][9] = '3'
        grid[9][9] = '4'
        board_str = grid_to_str(grid)
        strategy = SnakeStrategy()
        b = Board(board_str, 'A', '10x10', next_digit=1)
        candidates = strategy._build_candidates(b)
        assert candidates['left']['wrong_digit'] is True
        step, dist = strategy._best_target_move(candidates, b.food, 0)
        assert step != 'left'
        assert dist < WRONG_DIGIT_STEP_PENALTY
        d = strategy.choose_direction(
            board_str,
            'A',
            board_size='10x10',
            next_digit=1,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d != 'left'

    def test_server_next_digit_drives_the_strategy(self):
        grid = make_grid(10, 10)
        grid[2][2] = 'A'
        grid[2][3] = '7'
        grid[5][5] = '5'
        grid[0][0] = '6'
        grid[0][9] = '8'
        grid[9][0] = '9'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            next_digit=7,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'right'

    def test_board_construction_exception_returns_random_direction(self):
        # side=None rompe Board.__init__; choose_direction lo ataja.
        assert (
            SnakeStrategy().choose_direction(
                make_board_str(['...', '...']), None
            )
            in DIRECTIONS
        )

    def test_candidate_that_cannot_reach_food_is_skipped(self):
        # 'left' es un bolsillo sin salida.
        board_str = make_board_str(
            [
                '......',
                '.b....',
                'b.Aa..',
                '.b....',
                '...*..',
            ]
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
        )
        assert d in DIRECTIONS
        assert d != 'left'

    def test_wrapper_choose_direction_compatibility(self):
        board_str = make_board_str(
            ['.........', '..A......', '..*......', '.........']
        )
        assert (
            choose_direction(
                board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
            )
            == 'down'
        )

    def test_goes_to_multiplier_pickup_without_food(self):
        board_str = make_board_str(
            [
                '.........',
                '.........',
                '..A......',
                '..X......',
                '.........',
            ]
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
        )
        assert d == 'down'

    def test_early_far_x_beats_small_adjacent_digit(self):
        # El 2 vale 200; el 'X' lejano, con 100 turnos por delante, ~7000.
        grid = make_grid(10, 10)
        grid[2][2] = 'A'
        grid[2][3] = '2'
        grid[8][8] = 'X'
        grid[0][0] = '3'
        grid[0][9] = '4'
        grid[9][0] = '5'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            next_digit=2,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'down'

    def test_goes_for_pickup_when_closer_than_digit(self):
        grid = make_grid(10, 10)
        grid[2][2] = 'A'
        grid[2][3] = 'X'
        grid[8][8] = '2'
        grid[0][0] = '3'
        grid[0][9] = '4'
        grid[9][0] = '5'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            next_digit=2,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'right'

    def test_same_distance_prefers_multiplier_pickup(self):
        grid = make_grid(10, 10)
        grid[2][2] = 'A'
        grid[2][3] = 'X'
        grid[1][2] = '2'
        grid[0][0] = '3'
        grid[0][9] = '4'
        grid[9][0] = '5'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            next_digit=2,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'right'

    def test_multiplier_pickup_does_not_grow_the_snake(self):
        strategy = SnakeStrategy()
        plain = strategy._build_candidates(
            Board(make_board_str(['.......', '.aaA...', '.......']), 'A')
        )
        with_pickup = strategy._build_candidates(
            Board(make_board_str(['.......', '.aaA...', '..X....']), 'A')
        )
        assert plain['down']['body_len'] == with_pickup['down']['body_len']

    def test_pickup_reached_first_by_opponent_does_not_break(self):
        board_str = make_board_str(
            [
                'A........',
                '.........',
                '.........',
                '.........',
                '........B',
                '.......X.',
            ]
        )
        d = SnakeStrategy().choose_direction(
            board_str, 'A', my_score=0, opp_score=0, remaining_moves=100
        )
        assert d in DIRECTIONS

    def test_choose_direction_accepts_multipliers(self):
        board_str = make_board_str(
            ['.........', '..A......', '..*......', '.........']
        )
        d = SnakeStrategy().choose_direction(
            board_str,
            'A',
            my_score=0,
            opp_score=0,
            remaining_moves=100,
            my_multiplier=3,
            opp_multiplier=1,
        )
        assert d == 'down'

    def test_build_candidates_marks_wall_hit_with_no_space(self):
        candidates = SnakeStrategy()._build_candidates(
            Board(make_board_str(WALL_ROWS), 'A')
        )
        assert candidates['right']['wall_hit'] is True
        assert candidates['right']['space'] == 0
        assert candidates['up']['wall_hit'] is False

    def test_avoids_wall_when_there_is_a_safe_alternative(self):
        assert (
            SnakeStrategy().choose_direction(make_board_str(WALL_ROWS), 'A')
            != 'right'
        )

    def test_picks_wall_as_last_resort(self):
        # Las otras tres salidas son cuerpo rival.
        board_str = make_board_str(['.b.', 'bA#', '.b.'])
        assert SnakeStrategy().choose_direction(board_str, 'A') == 'right'

    def test_does_not_step_into_wall_to_reach_food(self):
        grid = make_grid(10, 10)
        grid[5][5] = 'A'
        grid[5][4] = '#'
        grid[5][2] = '*'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d != 'left'

    def test_wall_does_not_turn_on_aggressive_mode(self):
        # Siempre hay un muro: no puede ser lo que activa el modo cazador.
        strategy = SnakeStrategy()
        assert strategy._is_aggressive(0, 0) is False
        assert strategy._is_aggressive(0, 50) is False
        assert strategy._is_aggressive(50, 0) is True

    def test_safety_buffer_only_when_winning_near_the_end(self):
        strategy = SnakeStrategy(safety_buffer=3)
        with_wall = Board(make_board_str(['.....', '..A..', '..#..']), 'A')
        assert (
            strategy._safety_buffer(
                with_wall, my_score=0, opp_score=50, remaining_moves=5
            )
            == 0
        )
        assert (
            strategy._safety_buffer(
                with_wall, my_score=50, opp_score=0, remaining_moves=5
            )
            == 3
        )
        assert (
            strategy._safety_buffer(
                with_wall, my_score=50, opp_score=0, remaining_moves=200
            )
            == 0
        )

    def test_v6_goes_to_nearest_target_copy(self):
        grid = make_grid(10, 10)
        grid[5][5] = 'A'
        grid[0][0] = '2'
        grid[9][0] = '2'
        grid[5][7] = '2'
        grid[0][9] = '3'
        grid[9][9] = '4'
        d = SnakeStrategy().choose_direction(
            grid_to_str(grid),
            'A',
            board_size='10x10',
            next_digit=2,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d == 'right'

    def test_v6_measures_clean_path_past_wrong_digit(self):
        # El camino recto al 1 pisa un 6 en el segundo paso: se mide el rodeo
        # (6).
        grid = make_grid(10, 10)
        grid[5][5] = 'A'
        grid[5][3] = '6'
        grid[5][1] = '1'
        grid[6][9] = 'X'
        grid[0][0] = '2'
        grid[0][9] = '3'
        grid[9][0] = '4'
        board_str = grid_to_str(grid)
        strategy = SnakeStrategy()
        b = Board(board_str, 'A', '10x10', next_digit=1)
        _, food_dist = strategy._best_target_move(
            strategy._build_candidates(b), b.food, 0
        )
        assert food_dist == 6
        d = strategy.choose_direction(
            board_str,
            'A',
            board_size='10x10',
            next_digit=1,
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d in ('right', 'down')

    def test_v6_reachable_only_through_wrong_digit_is_penalized(self):
        board_str = make_board_str(
            [
                '.......',
                '.A.....',
                '.......',
                '....5..',
                '...515.',
                '....5..',
            ]
        )
        strategy = SnakeStrategy()
        b = Board(board_str, 'A', next_digit=1)
        _, dist = strategy._best_target_move(
            strategy._build_candidates(b), b.food, 0
        )
        assert dist >= WRONG_DIGIT_STEP_PENALTY

    def test_wrapper_choose_direction_with_next_digit(self):
        grid = make_grid(6, 6)
        grid[0][0] = 'A'
        for r, v in enumerate('34567'):
            grid[r][1] = v
        assert (
            choose_direction(
                grid_to_str(grid), 'A', board_size='6x6', next_digit=3
            )
            == 'right'
        )

    def test_v4_end_of_game_prefers_multiplied_9_over_x(self):
        # X a 1 paso (+50), 9 a 2 pasos (2700); quedan 2 turnos.
        d = SnakeStrategy().choose_direction(
            make_board_str(V4_ROWS),
            'A',
            board_size='8x12',
            my_score=0,
            opp_score=0,
            remaining_moves=4,
            my_multiplier=3,
            opp_multiplier=1,
        )
        assert d == 'right'

    def test_v4_last_turn_takes_x_if_digit_is_out_of_reach(self):
        d = SnakeStrategy().choose_direction(
            make_board_str(V4_ROWS),
            'A',
            board_size='8x12',
            my_score=0,
            opp_score=0,
            remaining_moves=2,
            my_multiplier=3,
            opp_multiplier=1,
        )
        assert d == 'left'

    def test_v4_early_game_prefers_nearby_x(self):
        d = SnakeStrategy().choose_direction(
            make_board_str(V4_EARLY_ROWS),
            'A',
            board_size='8x12',
            my_score=0,
            opp_score=0,
            remaining_moves=300,
            my_multiplier=1,
            opp_multiplier=1,
        )
        assert d == 'left'

    def test_v4_without_remaining_moves_assumes_long_game(self):
        d = SnakeStrategy().choose_direction(
            make_board_str(V4_EARLY_ROWS), 'A', board_size='8x12'
        )
        assert d == 'left'

    def test_v4_own_turns_are_half_of_remaining_moves(self):
        assert SnakeStrategy._my_turns_left(300) == 150
        assert SnakeStrategy._my_turns_left(3) == 2

    def test_opponent_wins_the_3_with_long_game_left_goes_for_x(self):
        # Con 133 turnos por delante el 'X' (~9600) rinde mas que esperar el 4.
        d = SnakeStrategy().choose_direction(
            TURN_33_M5,
            'B',
            board_size='14x15',
            my_score=713,
            opp_score=712,
            remaining_moves=267,
            my_multiplier=3,
            opp_multiplier=5,
        )
        assert d == 'down'

    def test_takes_adjacent_x_if_still_first_to_next_digit(self):
        d = SnakeStrategy().choose_direction(
            TURN_57_M5,
            'B',
            board_size='14x15',
            my_score=823,
            opp_score=2223,
            remaining_moves=243,
            my_multiplier=5,
            opp_multiplier=5,
        )
        assert d == 'right'

    def test_next_digit_wraps_from_9_to_1(self):
        board = Board(
            make_board_str(['9....', '.A...', '...1B', '6.7.8']), 'A', '4x5'
        )
        assert board.target_digit == 6
        assert SnakeStrategy._next_digit_positions(board) == [(3, 2)]
        board = Board(
            make_board_str(['9....', '.A...', '...1B', '..2.3']), 'A', '4x5'
        )
        assert board.target_digit == 9
        assert SnakeStrategy._next_digit_positions(board) == [(2, 3)]

    def test_without_digits_there_is_no_next(self):
        board = Board(make_board_str(['.....', '.A...', '....B']), 'A', '3x5')
        assert SnakeStrategy._next_digit_positions(board) == []
        s = SnakeStrategy()
        assert (
            s._plan_next_digit(board, s._build_candidates(board), 0, None)
            is None
        )

    def test_waits_next_to_the_next_digit_without_stepping_on_it(self):
        rows = [
            '..........',
            '.2A.......',
            '..........',
            '..........',
            '.......1B.',
            '..........',
        ]
        d = SnakeStrategy().choose_direction(
            make_board_str(rows),
            'A',
            board_size='6x10',
            my_score=0,
            opp_score=0,
            remaining_moves=200,
        )
        assert d in ('up', 'down')

    def test_unreachable_x_does_not_count_for_the_plan(self):
        rows = [
            '........#X',
            '.2A.....##',
            '..........',
            '..........',
            '.......1B.',
            '..........',
        ]
        board = Board(make_board_str(rows), 'A', '6x10')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert s._my_dist(cands, (0, 9)) is None
        assert s._plan_next_digit(board, cands, 0, 'left') in ('up', 'down')

    def test_opponent_without_path_to_target_lets_me_take_x(self):
        rows = [
            '..X.......',
            '.2A.......',
            '..........',
            '######....',
            '1....#..B.',
            '.....#....',
        ]
        board = Board(make_board_str(rows), 'A', '6x10')
        s = SnakeStrategy()
        assert (
            s._plan_next_digit(board, s._build_candidates(board), 0, 'up')
            is None
        )

    def test_early_x_is_worth_more_than_a_1(self):
        # El 1 vale 300 (x3); el 'X', con 141 turnos por delante, ~5400.
        d = SnakeStrategy().choose_direction(
            TURN_17_M6,
            'B',
            board_size='14x20',
            my_score=106,
            opp_score=58,
            remaining_moves=283,
            my_multiplier=3,
            opp_multiplier=2,
        )
        assert d == 'up'

    def test_does_not_wait_for_5_next_to_opponents_4(self):
        # El rival se come el 4 y el 5 seguidos.
        d = SnakeStrategy().choose_direction(
            TURN_121_M6,
            'B',
            board_size='14x20',
            my_score=3151,
            opp_score=1853,
            remaining_moves=179,
            my_multiplier=9,
            opp_multiplier=7,
        )
        assert d != 'left'

    def test_no_plan_if_next_digit_is_missing(self):
        rows = ['A...........', '............', '.........1B.', '.........2..']
        board = Board(make_board_str(rows), 'A', '4x12')
        s = SnakeStrategy()
        assert (
            s._plan_next_digit(board, s._build_candidates(board), 0, None)
            is None
        )

    def test_no_plan_if_opponent_wins_every_race(self):
        rows = [
            'A..........5',
            '............',
            '............',
            '............',
            '............',
            '.........B1.',
            '..........23',
            '..........4.',
        ]
        board = Board(make_board_str(rows), 'A', '8x12')
        s = SnakeStrategy()
        assert (
            s._plan_next_digit(board, s._build_candidates(board), 0, None)
            is None
        )

    def test_behind_on_multiplier_takes_x_before_waiting(self):
        d = SnakeStrategy().choose_direction(
            TURN_62_M7,
            'A',
            board_size='19x19',
            my_score=1627,
            opp_score=1227,
            remaining_moves=238,
            my_multiplier=1,
            opp_multiplier=3,
        )
        assert d == 'down'

    def test_even_multiplier_x_beats_waiting_by_value(self):
        # Esperar el 8 vale 0,6 x 2400; el 'X' con 119 turnos por delante rinde
        # mas.
        board = Board(TURN_62_M7, 'A', '19x19')
        s = SnakeStrategy()
        assert s._x_gain(board, 238) > WAIT_WIN_PROB * 8 * 100 * 3
        d = s.choose_direction(
            TURN_62_M7,
            'A',
            board_size='19x19',
            my_score=1627,
            opp_score=1227,
            remaining_moves=238,
            my_multiplier=3,
            opp_multiplier=3,
        )
        assert d == 'down'

    def test_race_bonus_lets_me_contest_when_opponent_drifts_away(self):
        # El rival se aleja del 4 tres turnos seguidos: el bonus habilita
        # disputarlo.
        strategy = SnakeStrategy()
        stalls = []
        for turn in TURNS_53_TO_59_M9:
            play_turn(strategy, turn)
            stalls.append(strategy._race_stall)
        assert stalls[-2:] == [2, 3]
        board = Board(TURNS_53_TO_59_M9[-1][0], 'B', '19x16')
        cands = strategy._build_candidates(board)
        with_bonus = strategy._best_target_move(
            cands, board.food, 0, opp_bonus=strategy._food_bonus, shared=True
        )
        without_bonus = strategy._best_target_move(
            cands, board.food, 0, shared=True
        )
        assert without_bonus == (None, None)
        assert with_bonus[0] == 'up'

    def test_without_history_closer_opponent_wins_the_race(self):
        assert play_turn(SnakeStrategy(), TURNS_53_TO_59_M9[-1]) == 'right'

    def test_update_race_goes_up_and_down(self):
        # Sin historial, se aleja, no se acerca, se acerca.
        s = SnakeStrategy()
        assert [race_step(s, race_board(col)) for col in (5, 6, 6, 5)] == [
            0,
            1,
            2,
            1,
        ]

    def test_update_race_caps_and_resets_when_target_moves(self):
        s = SnakeStrategy()
        stalls = [
            race_step(s, race_board(11)) for _ in range(RACE_STALL_MAX + 5)
        ]
        assert (stalls[-1], s._food_bonus) == (
            RACE_STALL_MAX,
            RACE_STALL_MAX * RACE_STALL_BONUS,
        )
        assert race_step(s, race_board(11, digit_col=3)) == 0

    def test_v7_goes_to_tail_food_without_digits(self):
        g = make_grid(8, 8)
        g[4][4] = 'A'
        g[4][5] = TAIL_A
        g[4][6] = TAIL_A
        g[0][0] = 'B'
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='8x8',
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'right'

    def test_v7_side_b_eats_its_own_letter(self):
        g = make_grid(8, 8)
        g[4][4] = 'B'
        g[3][4] = TAIL_B
        g[5][4] = TAIL_A
        g[0][0] = 'A'
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'B',
            board_size='8x8',
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'up'

    def test_v7_tail_food_grows_the_snake(self):
        board = Board(
            make_board_str(['.......', '.aaA' + TAIL_A + '..', '.......']), 'A'
        )
        cands = SnakeStrategy()._build_candidates(board)
        assert cands['right']['body_len'] == len(board.body_cells) + 1
        assert cands['up']['body_len'] == len(board.body_cells)

    def test_v7_adjacent_digit_beats_far_tail(self):
        g = make_grid(10, 10)
        g[5][5] = 'A'
        g[5][6] = '5'
        g[5][3] = TAIL_A
        for (r, c), v in [
            ((0, 0), '6'),
            ((0, 9), '7'),
            ((9, 0), '8'),
            ((9, 9), '9'),
        ]:
            g[r][c] = v
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='10x10',
            next_digit=5,
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'right'

    def test_v7_adjacent_tail_beats_far_digit(self):
        g = make_grid(10, 10)
        g[5][5] = 'A'
        g[4][5] = TAIL_A
        g[5][0] = '1'
        for (r, c), v in [
            ((0, 0), '2'),
            ((0, 9), '3'),
            ((9, 0), '4'),
            ((9, 9), '5'),
        ]:
            g[r][c] = v
        g[9][5] = 'B'
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='10x10',
            next_digit=1,
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'up'

    def test_v7_skips_tail_if_it_loses_the_digit_race(self):
        g = make_grid(10, 10)
        g[5][5] = 'A'
        g[4][5] = TAIL_A
        g[5][7] = '9'
        g[5][9] = 'B'
        for (r, c), v in [
            ((0, 0), '1'),
            ((9, 0), '2'),
            ((9, 9), '3'),
            ((0, 9), '4'),
        ]:
            g[r][c] = v
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='10x10',
            next_digit=9,
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'right'

    def test_v7_steps_on_own_shed_tail_to_deny_it(self):
        g = make_grid(8, 8)
        g[4][4] = 'A'
        g[4][3] = TAIL_B
        g[0][7] = 'B'
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='8x8',
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'left'

    def test_v7_crash_cost(self):
        board = Board(make_board_str(['aaaaaA..', '........']), 'A')
        assert (
            SnakeStrategy._crash_cost(board, 1200, 2)
            == 1200 + 3 * TAIL_FOOD_POINTS * 2
        )
        assert (
            SnakeStrategy._crash_cost(board, 100, 1)
            == FIXED_PENALTY + 3 * TAIL_FOOD_POINTS
        )
        small = Board(make_board_str(['aaA.....']), 'A')
        assert SnakeStrategy._crash_cost(small, None, None) == FIXED_PENALTY

    def test_v8_does_not_enter_bomb_zone(self):
        g = make_grid(9, 12)
        g[4][2] = BIG
        g[4][5] = 'A'
        d = SnakeStrategy().choose_direction(
            grid_to_str(g),
            'A',
            board_size='9x12',
            my_score=3000,
            opp_score=0,
            remaining_moves=300,
        )
        assert d != 'left'

    def test_v8_candidate_in_zone_is_marked_with_no_space(self):
        g = make_grid(7, 7)
        g[3][1] = SMALL
        g[3][3] = 'A'
        cands = SnakeStrategy()._build_candidates(
            Board(grid_to_str(g), 'A', '7x7'), my_score=800
        )
        assert cands['left']['bomb_hit'] is True
        assert cands['left']['space'] == 0
        assert cands['left']['penalty'] == 800
        assert (
            cands['right']['bomb_hit'] is False
            and cands['right']['penalty'] == 0
        )

    def test_v8_goes_around_the_bomb_to_reach_food(self):
        g = make_grid(9, 9)
        g[4][1] = 'A'
        g[4][4] = SMALL
        g[4][7] = '*'
        s = SnakeStrategy()
        board_str = grid_to_str(g)
        for _ in range(20):
            b = Board(board_str, 'A', '9x9')
            d = s.choose_direction(
                board_str,
                'A',
                board_size='9x9',
                my_score=500,
                opp_score=0,
                remaining_moves=300,
            )
            dr, dc = DIRECTIONS[d]
            nxt = (b.head[0] + dr, b.head[1] + dc)
            assert nxt not in b.bomb_zone
            if nxt == (4, 7):
                break
            g[b.head[0]][b.head[1]] = '.'
            g[nxt[0]][nxt[1]] = 'A'
            board_str = grid_to_str(g)
        else:
            raise AssertionError('no llego a la comida')

    def test_v8_last_resort_prefers_bomb_over_wall_crash(self):
        # Con poco puntaje, explotar sale mas barato que chocar y regalar la
        # cola.
        rows = ['......', '.bbb..', '#Aaaa.', '..' + SMALL + '...', '......']
        board_str = make_board_str(rows)
        assert (3, 1) in Board(board_str, 'A', '5x6').bomb_zone
        d = SnakeStrategy().choose_direction(
            board_str,
            'A',
            board_size='5x6',
            my_score=100,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'down'

    def test_v8_does_not_wait_for_next_digit_inside_a_zone(self):
        rows = [
            SMALL + '.........',
            '......A...',
            '2.' + SMALL + '.......',
            '..........',
            SMALL + '......1B.',
            '..........',
        ]
        board = Board(make_board_str(rows), 'A', '6x10')
        assert (2, 0) not in board.bomb_zone
        assert {(1, 0), (3, 0), (2, 1)} <= board.bomb_zone
        s = SnakeStrategy()
        assert (
            s._plan_next_digit(board, s._build_candidates(board), 0, None)
            is None
        )

    def test_v8_bomb_cost(self):
        assert SnakeStrategy._bomb_cost(2500) == 2500
        assert SnakeStrategy._bomb_cost(0) == FIXED_PENALTY
        assert SnakeStrategy._bomb_cost(-300) == FIXED_PENALTY
        assert SnakeStrategy._bomb_cost(None) == FIXED_PENALTY

    def test_v8_30x30_board_with_bombs_decides_fast(self):
        start = time.perf_counter()
        d = SnakeStrategy().choose_direction(
            big_v8_board(),
            'A',
            board_size='30x30',
            next_digit=3,
            my_score=1000,
            opp_score=500,
            remaining_moves=350,
            my_multiplier=2,
            opp_multiplier=2,
        )
        assert d in DIRECTIONS
        assert time.perf_counter() - start < 0.5

    def test_race_is_against_opponents_nearest_copy(self):
        # El rival esta a 2 de una copia del 7: la carrera esta perdida.
        board = Board(TURN_207_M12, 'B', '19x20')
        assert board.target_digit == 7 and len(board.food) == 5
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert s._best_target_move(cands, board.food, 0) != (None, None)
        assert s._best_target_move(cands, board.food, 0, shared=True) == (
            None,
            None,
        )

    def test_does_not_trap_the_awaited_digit_with_own_body(self):
        board = Board(TURN_261_M13, 'B', '20x20')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        next_positions = s._next_digit_positions(board)
        assert (
            s._digit_stays_open(board, cands['down']['pos'], next_positions)
            is False
        )
        assert (
            s._digit_stays_open(board, cands['left']['pos'], next_positions)
            is True
        )
        d = s.choose_direction(
            TURN_261_M13,
            'B',
            board_size='20x20',
            my_score=1965,
            opp_score=6711,
            remaining_moves=261,
            my_multiplier=1,
            opp_multiplier=6,
        )
        assert d != 'down'

    def test_early_game_goes_for_x_instead_of_waiting_small_digit(self):
        board = Board(TURN_393_M13, 'B', '20x20')
        s = SnakeStrategy()
        assert s._x_gain(board, 393) >= 5 * 200
        d = s.choose_direction(
            TURN_393_M13,
            'B',
            board_size='20x20',
            my_score=3,
            opp_score=4,
            remaining_moves=393,
            my_multiplier=1,
            opp_multiplier=1,
        )
        assert d == 'left'

    def test_does_not_trap_the_target_when_approaching(self):
        board = Board(TURN_285_M14, 'B', '16x18')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert (
            s._digit_stays_open(board, cands['right']['pos'], board.food)
            is False
        )
        d = s.choose_direction(
            TURN_285_M14,
            'B',
            board_size='16x18',
            my_score=8898,
            opp_score=7999,
            remaining_moves=285,
            my_multiplier=4,
            opp_multiplier=6,
        )
        assert d != 'right'

    def test_picks_copy_next_to_the_following_digit(self):
        # El 3 de la derecha esta 2 pasos mas lejos pero con el 4 pegado.
        rows = [
            '..............',
            '..............',
            '...3..A....34.',
            '..............',
            '..............',
            '5............B',
            '6.....7.......',
        ]
        d = SnakeStrategy().choose_direction(
            make_board_str(rows),
            'A',
            board_size='7x14',
            next_digit=3,
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'right'

    def test_chaining_does_not_detour_more_than_chain_slack(self):
        rows = [
            '..................',
            '....3.A.........34',
            '..................',
            '5................B',
            '6.......7.........',
        ]
        d = SnakeStrategy().choose_direction(
            make_board_str(rows),
            'A',
            board_size='5x18',
            next_digit=3,
            my_score=0,
            opp_score=0,
            remaining_moves=300,
        )
        assert d == 'left'

    def test_clean_space_detects_dead_end_corridor(self):
        # 138 celdas libres, pero solo 3 sin pisar digitos equivocados.
        board = Board(TURN_97_M15, 'B', '14x14')
        s = SnakeStrategy()
        left = s._build_candidates(board)['left']
        assert left['space'] > 100 and left['clean_space'] <= 3
        assert s._is_safe(left) is False

    def test_is_safe_without_clean_space_uses_total_space(self):
        s = SnakeStrategy()
        assert s._is_safe({'space': 10, 'body_len': 5}) is True
        assert s._is_safe({'space': 4, 'body_len': 5}) is False
        assert (
            s._is_safe({'space': 10, 'clean_space': 2, 'body_len': 5}) is False
        )

    def test_does_not_enter_where_opponent_can_cut_me_off(self):
        # Hacia la izquierda hay 378 celdas libres pero solo 1 propia.
        board = Board(TURN_133_M19, 'B', '23x21')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert cands['left']['territory'] < 5 and cands['left']['space'] > 300
        assert s._is_safe(cands['left']) is False
        assert s._is_safe(cands['down']) is True
        d = s.choose_direction(
            TURN_133_M19,
            'B',
            board_size='23x21',
            my_score=42764,
            opp_score=38712,
            remaining_moves=133,
            my_multiplier=8,
            opp_multiplier=9,
        )
        assert d != 'left'

    def test_tracking_fixes_ambiguous_body_order(self):
        # El cuerpo se toca a si mismo: recorrerlo desde la cabeza da una cola
        # equivocada.
        board_str = make_board_str(['aaa.', 'Aaa.', '....'])
        assert Board(board_str, 'A').tail != (0, 0)
        s = SnakeStrategy()
        s._last_body = [(1, 1), (1, 2), (0, 2), (0, 1), (0, 0), (1, 0)]
        board = Board(board_str, 'A')
        s._track_body(board)
        assert board.ordered_body == [
            (1, 0),
            (1, 1),
            (1, 2),
            (0, 2),
            (0, 1),
            (0, 0),
        ]
        assert board.tail == (0, 0)

    def test_tracking_follows_growth_and_crash(self):
        s = SnakeStrategy()
        prev = [(1, 2), (1, 3), (1, 4)]
        guesses = s._body_guesses(prev, (1, 1))
        assert [(1, 1), (1, 2), (1, 3)] in guesses
        assert [(1, 1), (1, 2), (1, 3), (1, 4)] in guesses
        assert prev in guesses

    def test_tracking_without_history_keeps_traced_body(self):
        s = SnakeStrategy()
        board = Board(make_board_str(['.aaA.']), 'A')
        s._track_body(board)
        assert board.tail == (0, 1)
        assert s._last_body == [(0, 3), (0, 2), (0, 1)]

    def test_own_tail_is_a_legal_move(self):
        board = Board(make_board_str(['Aa..', 'aa..', '....']), 'A')
        board.set_body([(0, 0), (0, 1), (1, 1), (1, 0)])
        moves = dict(SnakeStrategy()._legal_moves(board))
        assert moves == {'down': (1, 0)}

    def test_neck_is_not_a_legal_move(self):
        board = Board(make_board_str(['Aa..']), 'A')
        assert 'right' not in dict(SnakeStrategy()._legal_moves(board))

    def test_wrong_digit_also_grows_the_snake(self):
        board = Board(
            make_board_str(['.......', '.aaA7..', '1......']),
            'A',
            next_digit=1,
        )
        cands = SnakeStrategy()._build_candidates(board)
        assert cands['right']['body_len'] == len(board.body_cells) + 1

    def test_escape_path_rejects_area_without_long_enough_path(self):
        board = Board(plus_shaped_trap(), 'A', '7x9')
        cand = SnakeStrategy()._build_candidates(board, my_score=5000)['left']
        assert cand['space'] >= len(board.body_cells)
        assert cand['path_ok'] is False
        assert cand['penalty'] >= 5000
        assert SnakeStrategy()._is_safe(cand) is False

    def test_escape_path_counts_cells_freed_by_own_tail(self):
        # Cuerpo en U en un tablero cerrado: solo se sale siguiendo la propia
        # cola.
        rows = ['aaaa', 'A..a', 'aaaa']
        board = Board(make_board_str(rows), 'A', '3x4')
        body = [
            (1, 0),
            (0, 0),
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 3),
            (2, 3),
            (2, 2),
            (2, 1),
            (2, 0),
        ]
        board.set_body(body)
        assert EscapeSearch(board, [(1, 1)] + body[:-1]).run() is True

    def test_escape_search_budget_assumes_there_is_a_way_out(self):
        board = Board(plus_shaped_trap(), 'A', '7x9')
        search = EscapeSearch(
            board,
            [(3, 5)] + Board(plus_shaped_trap(), 'A', '7x9').ordered_body[:-1],
        )
        search.budget = 0
        assert search.run() is True

    def test_pace_counts_score_jumps_as_food(self):
        s = SnakeStrategy()
        for score in (0, 1, 201, 251, 252):
            s._track_pace(score)
        assert s._turns_played == 5
        assert s._food_eaten == 1

    def test_measured_pace_lowers_x_value_when_not_eating(self):
        board = Board(make_board_str(['1.2.3', 'A....', '4.5.B']), 'A', '3x5')
        fresh, starving = SnakeStrategy(), SnakeStrategy()
        for _ in range(100):
            starving._track_pace(0)
        assert starving._x_gain(board, 200) < fresh._x_gain(board, 200)

    def test_x_beats_waiting_needs_a_reachable_x(self):
        rows = ['........#X', '.2A.....##', '..........', '.......1B.']
        board = Board(make_board_str(rows), 'A', '4x10')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert s._x_beats_waiting(board, cands, [(1, 1)], 1, 300) is False

    def test_goes_for_star_it_wins(self):
        cells = {**NORMAL_A, **NORMAL_B, (2, 5): STAR}
        assert v10_choose(cells) == 'right'

    def test_long_invincibility_skips_star_step(self):
        s = SnakeStrategy()
        s.choose_direction(
            v10_board_str({**INVINCIBLE_A, **NORMAL_B, (2, 5): STAR}),
            'A',
            board_size='10x12',
            invincible=(40, 0),
        )
        assert s._my_invincible == 40

    def test_invincible_moves_from_real_head(self):
        cells = {**INVINCIBLE_A, **NORMAL_B}
        assert v10_choose(cells, invincible=(30, 0)) != 'left'

    def test_invincible_costs_nothing(self):
        s = SnakeStrategy()
        s._my_invincible = 5
        board = Board(v10_board_str({**NORMAL_A, **NORMAL_B}), 'A', '10x12')
        assert s._move_costs(board, 900, 1) == (0, 0, 0)

    def test_match20_keeps_the_nine_instead_of_x(self):
        move = SnakeStrategy().choose_direction(
            make_board_str(MATCH20_ROWS),
            'B',
            board_size='21x26',
            my_score=18055,
            opp_score=8589,
            remaining_moves=167,
            my_multiplier=8,
            opp_multiplier=7,
        )
        assert move == 'down'

    def test_real_gap_goes_around_a_bomb(self):
        board = Board(make_board_str(MATCH20_ROWS), 'B', '21x26')
        gap = SnakeStrategy._real_gap(board, (8, 11), [(7, 17)])
        assert gap > Board.manhattan((8, 11), (7, 17))

    def test_real_gap_unreachable_is_none(self):
        rows = ['A#.', '##.', '..1']
        board = Board(make_board_str(rows), 'A', '3x3')
        assert SnakeStrategy._real_gap(board, (0, 0), [(2, 2)]) is None

    def test_tracking_follows_a_shot_cut(self):
        # Me dispararon (v9): de 8 celdas a 3, con la cabeza un paso mas alla.
        s = SnakeStrategy()
        prev = [(1, 7 - i) for i in range(8)]
        guesses = s._body_guesses(prev, (1, 8))
        assert [(1, 8), (1, 7), (1, 6)] in guesses

    def test_tracking_keeps_the_tail_after_a_shot_cut(self):
        s = SnakeStrategy()
        s._last_body = [(1, 7 - i) for i in range(8)]
        board = Board(make_board_str(['  ****  aaA ']), 'A', '1x12')
        s._track_body(board)
        assert board.tail == (0, 8)

    def test_x_beats_waiting_counts_the_steps(self):
        # El 'X' rinde mas en total, pero esta mucho mas lejos que la espera.
        rows = [
            'X...........',
            '............',
            '............',
            '............',
            '.........aA.',
            '..........5B',
        ]
        board = Board(make_board_str(rows), 'A', '6x12')
        s = SnakeStrategy()
        cands = s._build_candidates(board)
        assert s._x_gain(board, 40) > WAIT_WIN_PROB * 5 * 100
        assert s._x_beats_waiting(board, cands, [(5, 10)], 1, 40) is False

    def test_safe_direction_avoids_bodies_and_bombs(self):
        rows = ['......', '.aaA..', '..' + SMALL + '...', '......']
        assert safe_direction(make_board_str(rows), 'A', '4x6') == 'up'

    def test_safe_direction_avoids_walls(self):
        rows = ['.#.', 'aA#', '...']
        assert safe_direction(make_board_str(rows), 'A', '3x3') == 'down'

    def test_safe_direction_without_head_or_board(self):
        assert safe_direction('|...|', 'A', '1x3') == FALLBACK_DIRECTION
        assert safe_direction(None, 'A') == FALLBACK_DIRECTION

    def test_low_score_prefers_bomb_over_wrong_digit(self):
        # Partida e32a246e (santinovitale), turno 23: con 11 puntos explotar
        # cuesta 11 y el digito equivocado 500.
        rows = [
            '.........',
            '....6....',
            '..' + SMALL + '.A.' + SMALL + '..',
            '....a....',
            '....a....',
            '.........',
            '1........',
        ]
        d = SnakeStrategy().choose_direction(
            make_board_str(rows),
            'A',
            board_size='7x9',
            my_score=11,
            opp_score=0,
            remaining_moves=380,
        )
        assert d in ('left', 'right')

    def test_high_score_still_takes_the_wrong_digit(self):
        rows = [
            '.........',
            '....6....',
            '..' + SMALL + '.A.' + SMALL + '..',
            '....a....',
            '....a....',
            '.........',
            '1........',
        ]
        d = SnakeStrategy().choose_direction(
            make_board_str(rows),
            'A',
            board_size='7x9',
            my_score=3000,
            opp_score=0,
            remaining_moves=380,
        )
        assert d == 'up'
