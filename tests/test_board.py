"""Tests unitarios de board.py."""

import unittest
from board import STAR, Board, DIRECTIONS


def make_board_str(rows):
    return '\n'.join('|' + row + '|' for row in rows)


# -- parseo y dimensiones -------------------------------------------------


# -- cabeza, cuerpo, comida, rival -----------------------------------------


# -- geometria: vecinos, manhattan, bfs -------------------------------------


# -- v3: comida numerica ----------------------------------------------------


# -- v4: pickups de multiplicador ('X') --------------------------------


# -- v5: muro ('#') ----------------------------------------------------


# -- v6: copias multiples de cada digito ---------------------------------


# -- v7: comida de cola ----------------------------------------------------

TAIL_A, TAIL_B = 'Ⓐ', 'Ⓑ'


# -- v8: bombas de proximidad ------------------------------------

BIG, SMALL = '\U0001f4a3', '\U0001f9e8'


def bomb_in_the_middle(bomb):
    rows = ['.' * 9 for _ in range(9)]
    rows[4] = '....' + bomb + '....'
    return Board(make_board_str(rows), 'A', board_size='9x9').bomb_zone


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


class BoardTest(unittest.TestCase):
    """Tests de Board."""

    def test_parse_dimensions_from_board_size(self):
        board_str = make_board_str(['.....', '.A...', '.....'])
        b = Board(board_str, 'A', board_size='3x5')
        assert (b.n_rows, b.n_cols) == (3, 5)

    def test_parse_dimensions_fallback_without_board_size(self):
        board_str = make_board_str(['.....', '.A...', '.....'])
        b = Board(board_str, 'A')
        assert (b.n_rows, b.n_cols) == (3, 5)

    def test_parse_dimensions_malformed_board_size_uses_fallback(self):
        board_str = make_board_str(['.....', '.A...', '.....'])
        b = Board(board_str, 'A', board_size='no-es-un-tamano')
        assert (b.n_rows, b.n_cols) == (3, 5)

    def test_parse_dimensions_uneven_rows_uses_minimum(self):
        # La fila mas corta marca el limite de columnas.
        board_str = "|.....|\n|.A|\n|.....|"
        b = Board(board_str, 'A')
        assert b.n_cols == 2

    def test_char_at_out_of_range_does_not_break(self):
        # board_size mas grande que las filas reales.
        board_str = make_board_str(['.....', '.A...'])
        b = Board(board_str, 'A', board_size='5x8')
        assert b.n_rows == 5
        assert b.head == (1, 1)

    def test_detects_head_body_food_and_opponent(self):
        board_str = make_board_str(
            [
                '.......',
                '.aaA...',
                '.......',
                '...*...',
                '...bB..',
            ]
        )
        b = Board(board_str, 'A')
        assert (b.head, b.opponent_head) == ((1, 3), (4, 4))
        assert {(1, 1), (1, 2)} <= b.body_cells
        assert {(4, 3), (4, 4)} <= b.opponent_blocked
        assert (3, 3) in b.food

    def test_without_own_head(self):
        board_str = make_board_str(['.....', '.....'])
        b = Board(board_str, 'A')
        assert b.head is None
        assert b.ordered_body == []
        assert b.tail is None

    def test_trace_body_finds_tail(self):
        board_str = make_board_str(
            [
                '.......',
                '.aaaA..',
                '.......',
            ]
        )
        b = Board(board_str, 'A')
        assert b.ordered_body[0] == b.head
        assert b.tail == (1, 1)

    def test_trace_body_disconnected_body_has_no_tail(self):
        board_str = make_board_str(
            [
                'a......',
                '.......',
                '...A...',
            ]
        )
        b = Board(board_str, 'A')
        assert b.tail is None

    def test_neighbors_respects_edges(self):
        board_str = make_board_str(['...', '...', '...'])
        b = Board(board_str, 'A')
        neighbors = dict(b.neighbors((0, 0)))
        assert set(neighbors.keys()) == {'down', 'right'}
        assert neighbors['down'] == (1, 0)
        assert neighbors['right'] == (0, 1)

    def test_neighbors_center_has_four_directions(self):
        board_str = make_board_str(['...', '...', '...'])
        b = Board(board_str, 'A')
        neighbors = dict(b.neighbors((1, 1)))
        assert set(neighbors.keys()) == set(DIRECTIONS.keys())

    def test_manhattan(self):
        assert Board.manhattan((0, 0), (3, 4)) == 7
        assert Board.manhattan((2, 2), (2, 2)) == 0

    def test_bfs_all_distances_basic(self):
        board_str = make_board_str(['.....', '.....', '.....'])
        b = Board(board_str, 'A')
        dist = b.bfs_all_distances((0, 0), blocked=set())
        assert dist[(0, 0)] == 0
        assert dist[(2, 4)] == 6

    def test_bfs_all_distances_start_none_or_blocked(self):
        board_str = make_board_str(['...', '...'])
        b = Board(board_str, 'A')
        assert b.bfs_all_distances(None, set()) == {}
        assert b.bfs_all_distances((0, 0), blocked={(0, 0)}) == {}

    def test_bfs_all_distances_respects_blocked(self):
        board_str = make_board_str(['...', '...', '...'])
        b = Board(board_str, 'A')
        blocked = {(1, 0), (1, 1)}
        dist = b.bfs_all_distances((0, 0), blocked)
        assert (2, 0) in dist
        assert dist[(2, 0)] > 2

    def test_without_digits_is_apple_mode(self):
        board_str = make_board_str(['.....', '.A*..'])
        b = Board(board_str, 'A')
        assert b.target_digit is None
        assert b.target_digit_pos is None
        assert b.wrong_digit_positions == set()
        assert b.food == [(1, 2)]

    def test_target_digit_inferred_without_wraparound(self):
        board_str = make_board_str(
            ['.1...', '..2..', '...3.', 'A..4.', '....5']
        )
        b = Board(board_str, 'A')
        assert b.target_digit == 1
        assert b.target_digit_pos == (0, 1)
        assert b.food == [(0, 1)]
        assert b.wrong_digit_positions == {(1, 2), (2, 3), (3, 3), (4, 4)}

    def test_target_digit_inferred_with_wraparound(self):
        board_str = make_board_str(
            ['.7...', '..8..', '...9.', 'A..1.', '....2']
        )
        b = Board(board_str, 'A')
        assert b.target_digit == 7
        assert b.target_digit_pos == (0, 1)

    def test_server_next_digit_overrides_inference(self):
        board_str = make_board_str(
            ['.7...', '..8..', '...9.', 'A..1.', '....2']
        )
        b = Board(board_str, 'A', next_digit=9)
        assert b.target_digit == 9
        assert b.target_digit_pos == (2, 3)
        assert b.food == [(2, 3)]
        assert (0, 1) in b.wrong_digit_positions

    def test_next_digit_not_on_board(self):
        board_str = make_board_str(
            ['.7...', '..8..', '...9.', 'A..1.', '....2']
        )
        b = Board(board_str, 'A', next_digit=4)
        assert b.target_digit == 4
        assert b.target_digit_pos is None
        assert b.food == []
        assert len(b.wrong_digit_positions) == 5

    def test_invalid_next_digit_falls_back_to_inference(self):
        board_str = make_board_str(
            ['.1...', 'A..2.', '...3.', '4....', '....5']
        )
        b = Board(board_str, 'A', next_digit='no-es-numero')
        assert b.target_digit == 1

    def test_locate_digit_with_none_does_not_break(self):
        board_str = make_board_str(['.1...'])
        b = Board(board_str, 'A')
        assert b._locate_digit(None) is None

    def test_side_b_swaps_own_and_opponent(self):
        board_str = make_board_str(
            ['.......', '.aaA...', '.......', '...bB..']
        )
        b = Board(board_str, 'B')
        assert b.head == (3, 4)
        assert b.opponent_head == (1, 3)

    def test_detects_multiplier_pickups(self):
        board_str = make_board_str(
            [
                '.......',
                '.A..X..',
                '.......',
                '..X....',
            ]
        )
        b = Board(board_str, 'A')
        assert set(b.multiplier_pickups) == {(1, 4), (3, 2)}

    def test_pickup_is_not_a_digit_nor_blocked(self):
        board_str = make_board_str(
            ['.1...', 'A..2.', '.X.3.', '4....', '....5']
        )
        b = Board(board_str, 'A')
        assert (2, 1) in b.multiplier_pickups
        assert (2, 1) not in set(
            b.digit_values
        ) | b.wrong_digit_positions | b.body_cells | b.opponent_blocked

    def test_without_pickups_empty_list(self):
        board_str = make_board_str(['.....', '.A*..'])
        b = Board(board_str, 'A')
        assert b.multiplier_pickups == []

    def test_detects_wall_cells(self):
        board_str = make_board_str(
            [
                '.......',
                '.A..#..',
                '.......',
                '..#....',
                '..#....',
            ]
        )
        b = Board(board_str, 'A')
        assert b.wall_cells == {(1, 4), (3, 2), (4, 2)}

    def test_wall_is_not_confused_with_other_cells(self):
        board_str = make_board_str(
            ['.1...', 'A..2.', '.#.3.', '4.X..', '....5']
        )
        b = Board(board_str, 'A')
        assert (2, 1) in b.wall_cells
        others = (
            set(b.digit_values)
            | b.wrong_digit_positions
            | set(b.multiplier_pickups)
        )
        assert (2, 1) not in others | b.body_cells | b.opponent_blocked

    def test_without_wall_empty_set(self):
        board_str = make_board_str(['.....', '.A*..'])
        b = Board(board_str, 'A')
        assert b.wall_cells == set()

    def test_v6_all_target_copies_are_food(self):
        board_str = make_board_str(
            [
                '3....4',
                '..A...',
                '5..3..',
                '......',
                '6....3',
                '7..4..',
            ]
        )
        b = Board(board_str, 'A', next_digit=3)
        assert b.target_digit_positions == [(0, 0), (2, 3), (4, 5)]
        assert set(b.food) == {(0, 0), (2, 3), (4, 5)}
        assert b.target_digit_pos == (0, 0)
        assert b.wrong_digit_positions == {
            (0, 5),
            (2, 0),
            (4, 0),
            (5, 0),
            (5, 3),
        }

    def test_v6_target_inference_with_repeated_copies(self):
        board_str = make_board_str(['4.5.6.', 'A.4.8.', '5.7.6.', '8.7.4.'])
        b = Board(board_str, 'A')
        assert b.target_digit == 4
        assert len(b.target_digit_positions) == 3

    def test_locate_all_digits_with_none_returns_empty_list(self):
        b = Board(make_board_str(['.1...']), 'A')
        assert b._locate_all_digits(None) == []

    def test_v7_side_a_eats_tail_with_its_letter(self):
        board_str = make_board_str(
            ['..' + TAIL_A + TAIL_A + '..', '.A....', '..' + TAIL_B + '..B']
        )
        b = Board(board_str, 'A')
        assert set(b.tail_food) == {(0, 2), (0, 3)}
        assert b.own_shed_tail == [(2, 2)]

    def test_v7_side_b_sees_tails_the_other_way(self):
        board_str = make_board_str(
            ['..' + TAIL_A + TAIL_A + '..', '.A....', '..' + TAIL_B + '..B']
        )
        b = Board(board_str, 'B')
        assert b.tail_food == [(2, 2)]
        assert set(b.own_shed_tail) == {(0, 2), (0, 3)}

    def test_v7_tail_food_is_not_confused_with_other_cells(self):
        board_str = make_board_str(
            [
                '.1' + TAIL_A + '..',
                'A..2.',
                '.' + TAIL_B + '.3.',
                '4....',
                '....5',
            ]
        )
        b = Board(board_str, 'A')
        others = (
            set(b.digit_values)
            | b.body_cells
            | b.opponent_blocked
            | b.wall_cells
            | b.bomb_zone
        )
        assert not {(0, 2), (2, 1)} & others

    def test_v8_each_bomb_takes_one_column(self):
        board_str = make_board_str([BIG + '......A', SMALL + '.......'])
        b = Board(board_str, 'A', board_size='2x8')
        assert b.head == (0, 7)
        assert set(b.bombs) == {((0, 0), 2), ((1, 0), 1)}

    def test_v8_big_bomb_zone_is_5x5(self):
        zone = bomb_in_the_middle(BIG)
        assert len(zone) == 25
        assert {(2, 2), (6, 6)} <= zone
        assert not {(1, 4), (4, 7)} & zone

    def test_v8_small_bomb_zone_is_3x3(self):
        zone = bomb_in_the_middle(SMALL)
        assert len(zone) == 9
        assert {(3, 3), (5, 5)} <= zone
        assert (2, 4) not in zone

    def test_v8_zone_is_clipped_at_the_edge(self):
        b = Board(
            make_board_str([BIG + '....', '.....', '.....', '....A']),
            'A',
            board_size='4x5',
        )
        assert len(b.bomb_zone) == 9
        assert all(0 <= r < 4 and 0 <= c < 5 for r, c in b.bomb_zone)

    def test_v8_overlapping_zones_do_not_duplicate_cells(self):
        b = Board(
            make_board_str([SMALL + SMALL + '...', '.....', '....A']),
            'A',
            board_size='3x5',
        )
        assert b.bomb_zone == {(r, c) for r in range(2) for c in range(3)}

    def test_v8_without_bombs_empty_zone(self):
        b = Board(make_board_str(['.....', '.A*..']), 'A')
        assert b.bombs == [] and b.bomb_zone == set()

    def test_v8_variation_selector_is_ignored(self):
        b = Board(make_board_str([BIG + '️' + '...A']), 'A', board_size='1x5')
        assert b.head == (0, 4)
        assert b.bombs == [((0, 0), 2)]

    def test_v8_bomb_is_not_a_digit_nor_blocked(self):
        b = Board(
            make_board_str(
                ['.1...', 'A..2.', '...3.', '4.' + BIG + '..', '....5']
            ),
            'A',
        )
        assert (3, 2) not in b.digit_values
        assert (3, 2) not in b.body_cells and (3, 2) not in b.opponent_blocked

    def test_chebyshev(self):
        assert Board.chebyshev((0, 0), (2, 1)) == 2
        assert Board.chebyshev((3, 3), (3, 3)) == 0

    def test_star_is_bonus_food(self):
        cells = {**NORMAL_A, **NORMAL_B, (2, 5): STAR}
        b = Board(v10_board_str(cells), 'A', '10x12')
        assert b.stars == [(2, 5)]
        assert (2, 5) in b.bonus_food

    def test_shot_food_survives_digits(self):
        cells = {**NORMAL_A, **NORMAL_B, (2, 4): '*'}
        b = Board(v10_board_str(cells), 'A', '10x12')
        assert (2, 4) in b.bonus_food
        assert (2, 4) not in b.food

    def test_my_invincible_snake(self):
        b = Board(
            v10_board_str({**INVINCIBLE_A, **NORMAL_B}),
            'A',
            '10x12',
            invincible=(True, False),
        )
        assert b.head == (2, 3)
        assert b.ordered_body == [(2, 3), (2, 2), (2, 1)]

    def test_opponent_invincible_snake(self):
        b = Board(
            v10_board_str({**NORMAL_A, **INVINCIBLE_B}),
            'A',
            '10x12',
            invincible=(False, True),
        )
        assert b.opponent_head == (6, 6)
        assert b.opponent_blocked == {(6, 6), (6, 7), (6, 8)}
