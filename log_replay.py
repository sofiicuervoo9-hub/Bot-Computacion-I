"""Vuelve a jugar una partida a partir del game_<id>.log que escribe el bot."""

import json

from snake_ai import SnakeStrategy


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
        mine, theirs = ('1', '2') if data['side'] == 'A' else ('2', '1')
        return strategy.choose_direction(
            data['board'],
            data['side'],
            board_size=data.get('board_size'),
            my_score=data.get('score_' + mine),
            opp_score=data.get('score_' + theirs),
            remaining_moves=data.get('remaining_moves'),
            my_multiplier=data.get('multiplier_' + mine),
            opp_multiplier=data.get('multiplier_' + theirs),
        )

    def replay(self, strategy=None):
        """Lista de (datos, direccion del log, direccion que elige hoy la
        estrategia)."""
        strategy = strategy or SnakeStrategy()
        return [
            (data, logged, self._decide(strategy, data))
            for data, logged in self.turns()
        ]
