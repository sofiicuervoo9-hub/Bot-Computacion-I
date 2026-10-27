"""Vuelve a jugar una partida a partir del game_<id>.log que escribe el bot."""

import json

from board import DIRECTIONS, Board
from snake_ai import SnakeStrategy

# Lo que ya se midio en el servidor (partidas reales).
MOVE_POINTS = 1
X_POINTS = 50
FOOD_POINTS = 100
PENALTY = 500


def my_keys(data):
    """('1', '2') si juego del lado A, ('2', '1') si del lado B."""
    return ('1', '2') if data['side'] == 'A' else ('2', '1')


class GameLogReplay:
    """Lee un log de partida y repite cada turno con una estrategia."""

    def __init__(self, path):
        with open(path, encoding='utf-8') as f:
            self.messages = [
                self.parse_line(line) for line in f if line.strip()
            ]

    @staticmethod
    def parse_line(line):
        """Devuelve (marca, mensaje): '<' recibido o '>' enviado."""
        start = line.index('{')
        return line[0], json.loads(line[start:])

    def turns(self):
        """Pares (datos del turno, direccion que se mando) en orden."""
        pending = None
        for marker, message in self.messages:
            if self._is_turn(marker, message):
                pending = message['data']
            elif self._answers(marker, pending):
                yield pending, message['data']['direction']
                pending = None

    @staticmethod
    def _is_turn(marker, message):
        return marker == '<' and message.get('event') == 'your_turn'

    @staticmethod
    def _answers(marker, pending):
        return marker == '>' and pending is not None

    @staticmethod
    def _decide(strategy, data):
        mine, theirs = my_keys(data)
        return strategy.choose_direction(
            data['board'],
            data['side'],
            board_size=data.get('board_size'),
            my_score=data.get('score_' + mine),
            opp_score=data.get('score_' + theirs),
            remaining_moves=data.get('remaining_moves'),
            my_multiplier=data.get('multiplier_' + mine),
            opp_multiplier=data.get('multiplier_' + theirs),
            invincible=(
                data.get('invincible_' + mine) or 0,
                data.get('invincible_' + theirs) or 0,
            ),
        )

    def replay(self, strategy=None):
        """Lista de (datos, direccion del log, direccion que elige hoy la
        estrategia)."""
        strategy = strategy or SnakeStrategy()
        return [
            (data, logged, self._decide(strategy, data))
            for data, logged in self.turns()
        ]

    def check_scores(self):
        """Turnos donde el puntaje del servidor no es el que predicen las
        reglas: [(remaining_moves, esperado, real)]."""
        checker = ScoreCheck()
        turns = list(self.turns())
        mismatches = []
        for (data, direction), (after, _) in zip(turns, turns[1:]):
            expected = checker.expected(data, direction)
            actual = after.get('score_' + my_keys(after)[0])
            if expected is not None and expected != actual:
                mismatches.append((data['remaining_moves'], expected, actual))
        return mismatches


class ScoreCheck:
    """Predice mi puntaje despues de una jugada; None si no es seguro."""

    def __init__(self):
        self.crashed = False
        # Reusa la memoria del cuerpo de la estrategia: el trazado solo puede
        # equivocarse cuando el cuerpo se toca a si mismo.
        self._tracker = SnakeStrategy()

    def expected(self, data, direction):
        mine = my_keys(data)[0]
        board = Board(data['board'], data['side'], data.get('board_size'))
        self._tracker._track_body(board)
        if data.get('invincible_' + mine):
            return None
        dr, dc = DIRECTIONS[direction]
        return self._predict(
            board,
            (board.head[0] + dr, board.head[1] + dc),
            data.get('score_' + mine) or 0,
            data.get('multiplier_' + mine) or 1,
        )

    def _predict(self, board, pos, score, mult):
        if self._crashes(board, pos):
            return self._after_crash(score)
        if pos in board.bomb_zone:
            return None
        return score + self._cell_points(board, pos, mult)

    @staticmethod
    def _crashes(board, pos):
        own = board.body_cells - {board.tail}
        return (
            not board.inside(pos)
            or pos in board.wall_cells
            or pos in own
            or pos in board.opponent_blocked
        )

    def _after_crash(self, score):
        """El primer choque deja en 0; los demas (o con <= 0) restan 500."""
        first = not self.crashed
        self.crashed = True
        return 0 if first and score > 0 else score - PENALTY

    @staticmethod
    def _cell_points(board, pos, mult):
        target = (board.target_digit or 0) * FOOD_POINTS * mult
        rules = (
            (board.target_digit_positions, target),
            (board.wrong_digit_positions, -PENALTY),
            (board.multiplier_pickups, X_POINTS),
            (board.tail_food + board.bonus_food, FOOD_POINTS * mult),
        )
        return next((pts for cells, pts in rules if pos in cells), MOVE_POINTS)
