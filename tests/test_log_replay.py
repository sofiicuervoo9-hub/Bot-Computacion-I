"""Tests de log_replay.py: partidas reales repetidas desde los logs del bot."""

import os
import tempfile
import unittest

from board import DIRECTIONS, Board
from log_replay import GameLogReplay
from run import GameLogger

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
# Partida 6ed989fc (19/10): en remaining_moves=133 el bot entro a un pasillo
# que el rival cerro, y el primer choque le borro 42.767 puntos.
TRAP_GAME = os.path.join(FIXTURES, 'match_6ed989fc.log')


class GameLogReplayTest(unittest.TestCase):
    """Tests de GameLogReplay."""

    def test_parse_line_reads_marker_and_json(self):
        line = '> [2026-10-19 17:00:00.100] {"action": "move"}'
        marker, message = GameLogReplay.parse_line(line)
        assert marker == '>'
        assert message == {'action': 'move'}

    def test_turns_pair_each_board_with_the_move_sent(self):
        turns = list(GameLogReplay(TRAP_GAME).turns())
        assert len(turns) == 21
        data, direction = turns[0]
        assert data['remaining_moves'] == 165 and direction in DIRECTIONS

    def test_replay_of_the_trap_game_no_longer_walks_into_the_trap(self):
        results = GameLogReplay(TRAP_GAME).replay()
        by_turn = {
            data['remaining_moves']: (logged, now)
            for data, logged, now in results
        }
        assert by_turn[133] == ('left', 'down')
        assert all(now in DIRECTIONS for _, _, now in results)

    def test_replay_never_enters_a_bomb_zone_with_a_free_choice(self):
        for data, _, now in GameLogReplay(TRAP_GAME).replay():
            board = Board(data['board'], data['side'], data['board_size'])
            dr, dc = DIRECTIONS[now]
            next_cell = (board.head[0] + dr, board.head[1] + dc)
            assert next_cell not in board.bomb_zone

    def test_logger_output_can_be_replayed(self):
        # Lo que escribe GameLogger es exactamente lo que lee GameLogReplay.
        data = {
            'board': '|A..|\n|..B|',
            'side': 'A',
            'board_size': '2x3',
            'remaining_moves': 10,
            'score_1': 0,
            'score_2': 0,
            'game_id': 'g1',
            'turn_token': 't',
        }
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                logger = GameLogger()
                logger.log_event('g1', {'event': 'your_turn', 'data': data})
                logger.log_action(
                    'g1', {'action': 'move', 'data': {'direction': 'right'}}
                )
                logger.write('g1')
                results = GameLogReplay('game_g1.log').replay()
            finally:
                os.chdir(previous)
        assert len(results) == 1 and results[0][1] == 'right'
