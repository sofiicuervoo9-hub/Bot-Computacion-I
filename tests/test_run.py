"""Tests de run.py (GameLogger y SnakeBot) con el websocket simulado."""

import contextlib
import io
import json
import os
import runpy
import sys
import tempfile
import time
import unittest
from datetime import datetime
from unittest import mock

import websockets

from board import DIRECTIONS
from run import SERVER_URL, GameLogger, SnakeBot, safe_print
from snake_ai import SnakeStrategy

BOARD_V8 = '|A..\U0001f4a3|\n|.Ⓐ.\U0001f9e8|\n|..bB|'


# -- dobles de prueba --------------------------------------------------


class FakeStrategy:
    """Estrategia falsa que devuelve siempre la misma direccion."""

    def __init__(self, direction='up', raise_error=False):
        self.direction = direction
        self.raise_error = raise_error
        self.calls = []

    def choose_direction(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raise_error:
            raise RuntimeError('estrategia rota')
        return self.direction


class SlowStrategy:
    """Estrategia falsa que tarda mas de la cuenta."""

    def __init__(self, delay_seconds):
        self.delay_seconds = delay_seconds

    def choose_direction(self, *args, **kwargs):
        time.sleep(self.delay_seconds)
        return 'left'


class FakeWebSocket:
    """Websocket falso: guarda lo enviado y devuelve mensajes de una cola."""

    def __init__(self, incoming=None):
        self.sent = []
        self._incoming = list(incoming or [])

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        if not self._incoming:
            raise websockets.ConnectionClosed(None, None)
        return self._incoming.pop(0)


def fake_connect(on_enter, on_init=None):
    """Clase que reemplaza websockets.connect; on_enter decide que pasa al
    conectar."""

    class FakeConnect:
        def __init__(self, uri):
            if on_init is not None:
                on_init(uri)

        async def __aenter__(self):
            return on_enter()

        async def __aexit__(self, *exc):
            return False

    return FakeConnect


def interrupt():
    raise KeyboardInterrupt()


async def fake_sleep(_):
    return None


def make_bot(strategy=None):
    return SnakeBot('fake-token', strategy=strategy or FakeStrategy())


def make_turn_data(game_id, side='A', **extra):
    data = {
        'side': side,
        'board': '|...|',
        'board_size': '1x3',
        'game_id': game_id,
        'turn_token': 't1',
        'score_1': 0,
        'score_2': 0,
        'remaining_moves': 20,
    }
    data.update(extra)
    return data


class BotTestCase(unittest.IsolatedAsyncioTestCase):
    """Cada test corre en una carpeta temporal y puede capturar la consola."""

    def setUp(self):
        self._previous_dir = os.getcwd()
        self._folder = tempfile.TemporaryDirectory()
        os.chdir(self._folder.name)

    def tearDown(self):
        os.chdir(self._previous_dir)
        self._folder.cleanup()

    @staticmethod
    def capture():
        """Context manager que junta lo impreso en un StringIO."""
        return contextlib.redirect_stdout(io.StringIO())

    @staticmethod
    def offline(connect_class):
        """Reemplaza la conexion real y la espera entre reintentos."""
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch('run.asyncio.sleep', fake_sleep))
        stack.enter_context(
            mock.patch('run.websockets.connect', connect_class)
        )
        return stack

    @staticmethod
    def windows_console():
        """Reemplaza stdout por uno cp1252, como la consola de Windows."""
        buf = io.BytesIO()
        wrapper = io.TextIOWrapper(buf, encoding='cp1252')
        return buf, mock.patch.object(sys, 'stdout', wrapper)


# -- GameLogger --------------------------------------------------------


class GameLoggerTest(BotTestCase):
    """Tests de GameLogger."""

    def test_log_event_and_log_action(self):
        logger = GameLogger()
        logger.log_event('g1', {'event': 'your_turn', 'data': {'x': 1}})
        logger.log_action(
            'g1', {'action': 'move', 'data': {'direction': 'up'}}
        )
        history = logger._history['g1']
        assert len(history) == 2
        assert history[0].startswith('< ') and history[1].startswith('> ')

    def test_write_creates_file_and_clears_history(self):
        logger = GameLogger()
        logger.log_event('g2', {'event': 'game_over', 'data': {}})
        logger.write('g2')
        with open('game_g2.log', encoding='utf-8') as f:
            assert 'game_over' in f.read()
        assert 'g2' not in logger._history

    def test_log_lines_include_parseable_timestamp(self):
        logger = GameLogger()
        logger.log_event('g1b', {'event': 'x'})
        logger.log_action(
            'g1b', {'action': 'move', 'data': {'direction': 'up'}}
        )
        for line, marker in zip(logger._history['g1b'], ['< [', '> [']):
            assert line.startswith(marker)
            stamp_end, json_start = line.index(']'), line.index('{')
            datetime.fromisoformat(line[len(marker):stamp_end])
            json.loads(line[json_start:])

    def test_write_without_history(self):
        GameLogger().write('g3')
        assert os.path.exists('game_g3.log')

    def test_write_handles_oserror(self):
        logger = GameLogger()
        logger.log_event('g4', {'event': 'x'})
        with mock.patch('builtins.open', side_effect=OSError('disco lleno')):
            with self.capture() as out:
                logger.write('g4')
        assert 'could not write game log' in out.getvalue()
        assert 'g4' not in logger._history

    def test_writes_utf8(self):
        logger = GameLogger()
        logger.log_event(
            'g14', {'event': 'your_turn', 'data': {'board': BOARD_V8}}
        )
        logger.write('g14')
        with open('game_g14.log', encoding='utf-8') as f:
            line = f.read().strip()
        json_start = line.index('{')
        assert json.loads(line[json_start:])['data']['board'] == BOARD_V8


# -- SnakeBot: estrategias, envio y eventos -----------------------------


class SnakeBotTest(BotTestCase):
    """Tests de SnakeBot sin conexion real."""

    def test_init_keeps_token_in_uri(self):
        bot = SnakeBot('tok')
        assert bot.auth_token == 'tok'
        assert 'tok' in bot.uri

    def test_without_strategy_uses_one_per_game(self):
        bot = SnakeBot('tok')
        first = bot.strategy_for('g1')
        assert isinstance(first, SnakeStrategy)
        assert bot.strategy_for('g1') is first
        assert bot.strategy_for('g2') is not first

    def test_fixed_strategy_is_shared_by_all_games(self):
        strategy = FakeStrategy()
        bot = make_bot(strategy)
        assert bot.strategy_for('g1') is strategy
        assert bot.strategy_for('g2') is strategy

    async def test_game_over_discards_that_games_strategy(self):
        bot = SnakeBot('tok')
        first = bot.strategy_for('g1')
        await bot._handle(
            FakeWebSocket(), {'event': 'game_over', 'data': {'game_id': 'g1'}}
        )
        assert bot.strategy_for('g1') is not first

    async def test_send_writes_json_to_websocket(self):
        ws = FakeWebSocket()
        with self.capture():
            await make_bot()._send(ws, 'move', {'direction': 'up'})
        assert len(ws.sent) == 1
        expected = {'action': 'move', 'data': {'direction': 'up'}}
        assert json.loads(ws.sent[0]) == expected

    async def test_handle_challenge_accepts(self):
        ws = FakeWebSocket()
        event = {'event': 'challenge', 'data': {'challenge_id': 'c_1'}}
        with self.capture():
            await make_bot()._handle(ws, event)
        expected = {
            'action': 'accept_challenge',
            'data': {'challenge_id': 'c_1'},
        }
        assert json.loads(ws.sent[0]) == expected

    async def test_handle_game_over_writes_log(self):
        event = {'event': 'game_over', 'data': {'game_id': 'g9'}}
        with self.capture():
            await make_bot()._handle(FakeWebSocket(), event)
        assert os.path.exists('game_g9.log')

    async def test_handle_game_over_without_game_id_does_not_break(self):
        event = {'event': 'game_over', 'data': {}}
        await make_bot()._handle(FakeWebSocket(), event)

    async def test_handle_error_only_prints(self):
        event = {'event': 'error', 'data': {'Error': 'boom'}}
        with self.capture() as out:
            await make_bot()._handle(FakeWebSocket(), event)
        assert 'server reported an error' in out.getvalue()

    async def test_handle_unknown_event_does_nothing(self):
        event = {'event': 'list_users', 'data': {'users': []}}
        await make_bot()._handle(FakeWebSocket(), event)

    async def test_handle_your_turn_calls_process_turn(self):
        strategy = FakeStrategy(direction='right')
        ws = FakeWebSocket()
        data = make_turn_data('g5', score_1=3, score_2=1, remaining_moves=50)
        with self.capture():
            await make_bot(strategy)._handle(
                ws, {'event': 'your_turn', 'data': data}
            )
        sent = json.loads(ws.sent[0])
        assert sent['data']['direction'] == 'right'
        assert sent['data']['game_id'] == 'g5'
        assert len(strategy.calls) == 1


# -- SnakeBot._process_turn -------------------------------------------------


class ProcessTurnTest(BotTestCase):
    """Que datos le llegan a la estrategia en cada turno."""

    async def strategy_kwargs(self, data):
        """Corre un turno con una estrategia falsa y devuelve sus kwargs."""
        strategy = FakeStrategy(direction='down')
        with self.capture():
            await make_bot(strategy)._process_turn(
                FakeWebSocket(), {'data': data}
            )
        return strategy.calls[0][1]

    async def test_side_a_uses_score_1_as_mine(self):
        kwargs = await self.strategy_kwargs(
            make_turn_data('g6', score_1=10, score_2=4)
        )
        assert (kwargs['my_score'], kwargs['opp_score']) == (10, 4)

    async def test_side_b_uses_score_2_as_mine(self):
        kwargs = await self.strategy_kwargs(
            make_turn_data('g7', side='B', score_1=10, score_2=4)
        )
        assert (kwargs['my_score'], kwargs['opp_score']) == (4, 10)

    async def test_does_not_use_next_digit(self):
        # El servidor no manda next_digit: el objetivo sale del tablero.
        kwargs = await self.strategy_kwargs(make_turn_data('g8', next_digit=7))
        assert 'next_digit' not in kwargs

    async def test_side_a_uses_multiplier_1_as_mine(self):
        kwargs = await self.strategy_kwargs(
            make_turn_data('g6b', multiplier_1=3, multiplier_2=1)
        )
        mults = (kwargs['my_multiplier'], kwargs['opp_multiplier'])
        assert mults == (3, 1)

    async def test_side_b_uses_multiplier_2_as_mine(self):
        kwargs = await self.strategy_kwargs(
            make_turn_data('g7b', side='B', multiplier_1=3, multiplier_2=1)
        )
        mults = (kwargs['my_multiplier'], kwargs['opp_multiplier'])
        assert mults == (1, 3)

    async def test_without_multiplier_passes_none(self):
        kwargs = await self.strategy_kwargs(make_turn_data('g6c'))
        mults = (kwargs['my_multiplier'], kwargs['opp_multiplier'])
        assert mults == (None, None)

    async def test_broken_strategy_uses_random_direction(self):
        ws = FakeWebSocket()
        with self.capture():
            await make_bot(FakeStrategy(raise_error=True))._process_turn(
                ws, {'data': make_turn_data('g9')}
            )
        assert json.loads(ws.sent[0])['data']['direction'] in DIRECTIONS

    async def test_prints_decision_time(self):
        with self.capture() as out:
            await make_bot(FakeStrategy(direction='up'))._process_turn(
                FakeWebSocket(), {'data': make_turn_data('g11')}
            )
        assert 'decision: up in' in out.getvalue()

    async def test_with_bombs_in_windows_console_still_answers(self):
        ws = FakeWebSocket()
        data = make_turn_data(
            'g12', board=BOARD_V8, board_size='3x4', remaining_moves=400
        )
        _, console = self.windows_console()
        with console:
            await make_bot(FakeStrategy(direction='down'))._process_turn(
                ws, {'data': data}
            )
        assert json.loads(ws.sent[0])['data']['direction'] == 'down'


# -- limite de tiempo -----------------------------------------------------


class TimeoutTest(BotTestCase):
    """Tests de _choose_direction_with_timeout."""

    def test_normal_path(self):
        bot = make_bot(FakeStrategy(direction='right'))
        d = bot._choose_direction_with_timeout(
            bot.strategy, '|...|', 'A', board_size='1x3'
        )
        assert d == 'right'

    def test_cuts_on_timeout(self):
        bot = SnakeBot(
            'tok',
            strategy=SlowStrategy(delay_seconds=0.3),
            decision_timeout=0.05,
        )
        with self.capture() as out:
            d = bot._choose_direction_with_timeout(
                bot.strategy, '|...|', 'A', board_size='1x3'
            )
        assert d in DIRECTIONS
        assert 'WARNING' in out.getvalue()


# -- SnakeBot._play y run --------------------------------------------------


class ConnectionTest(BotTestCase):
    """Tests del loop de mensajes y de la conexion."""

    async def test_play_handles_messages_until_connection_closes(self):
        message = json.dumps(
            {'event': 'your_turn', 'data': make_turn_data('g10')}
        )
        ws = FakeWebSocket(incoming=[message])
        with self.capture():
            await make_bot(FakeStrategy(direction='left'))._play(ws)
        assert len(ws.sent) == 1

    async def test_play_invalid_message_does_not_break_loop(self):
        with self.capture() as out:
            await make_bot()._play(FakeWebSocket(incoming=['no es json']))
        assert 'error handling message' in out.getvalue()

    async def test_play_message_with_surrogates_reaches_strategy_whole(self):
        # json.loads junta cada par de surrogates en un solo caracter.
        strategy = FakeStrategy(direction='up')
        raw = (
            '{"event": "your_turn", "data": {"side": "A", '
            '"board": "|A..\\ud83d\\udca3|\\n|.\\u24b6.\\ud83e\\udde8|'
            '\\n|..bB|", "board_size": "3x4", "game_id": "g13", '
            '"turn_token": "t1", "score_1": 0, "score_2": 0, '
            '"remaining_moves": 400}}'
        )
        _, console = self.windows_console()
        with console:
            await make_bot(strategy)._play(FakeWebSocket(incoming=[raw]))
        board_str = strategy.calls[0][0][0]
        assert board_str == BOARD_V8
        assert all(len(row) == 6 for row in board_str.split('\n'))

    async def test_run_does_not_print_the_token(self):
        def check_uri(uri):
            assert 'token-secreto' in uri

        bot = SnakeBot('token-secreto', strategy=FakeStrategy())
        with self.offline(fake_connect(interrupt, check_uri)):
            with self.capture() as out:
                await bot.run()
        assert SERVER_URL in out.getvalue()
        assert 'token-secreto' not in out.getvalue()

    async def test_run_exits_loop_on_keyboard_interrupt(self):
        with self.offline(fake_connect(interrupt)), self.capture():
            await make_bot().run()

    async def test_run_connects_and_plays(self):
        ws = FakeWebSocket(incoming=[])
        attempts = []

        def enter():
            if len(attempts) == 1:
                return ws
            raise KeyboardInterrupt()

        with self.offline(fake_connect(enter, attempts.append)):
            with self.capture():
                await make_bot().run()
        assert len(attempts) == 2

    async def test_run_retries_after_connection_error(self):
        attempts = []

        def enter():
            if len(attempts) < 2:
                raise RuntimeError('no se pudo conectar')
            raise KeyboardInterrupt()

        with self.offline(fake_connect(enter, attempts.append)):
            with self.capture():
                await make_bot().run()
        assert len(attempts) == 2


# -- consola y main ---------------------------------------------------


class ConsoleAndMainTest(BotTestCase):
    """safe_print y el punto de entrada de run.py."""

    def test_safe_print_does_not_break_with_emojis_in_cp1252(self):
        buf, console = self.windows_console()
        with console:
            safe_print(BOARD_V8)
            sys.stdout.flush()
        assert b'\\U0001f4a3' in buf.getvalue()

    def test_main_without_token_prints_help(self):
        with mock.patch.object(sys, 'argv', ['run.py']):
            with self.capture() as out:
                runpy.run_module('run', run_name='__main__')
        assert 'please provide your auth_token' in out.getvalue()

    def test_main_with_token_starts_bot(self):
        argv = ['run.py', 'mi-token-de-prueba']
        with mock.patch.object(sys, 'argv', argv):
            with self.offline(fake_connect(interrupt)), self.capture():
                runpy.run_module('run', run_name='__main__')
