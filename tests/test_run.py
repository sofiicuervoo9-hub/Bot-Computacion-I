"""Tests unitarios de run.py (GameLogger y SnakeBot), con el websocket
mockeado -- no abren conexion de red real."""

import json
import sys
import time
from datetime import datetime

import pytest
import websockets

from run import GameLogger, SnakeBot


# -- GameLogger --------------------------------------------------------

def test_game_logger_log_event_y_log_action(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = GameLogger()
    logger.log_event('g1', {'event': 'your_turn', 'data': {'x': 1}})
    logger.log_action('g1', {'action': 'move', 'data': {'direction': 'up'}})
    assert len(logger._history['g1']) == 2
    assert logger._history['g1'][0].startswith('< ')
    assert logger._history['g1'][1].startswith('> ')


def test_game_logger_write_crea_archivo_y_limpia_historial(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = GameLogger()
    logger.log_event('g2', {'event': 'game_over', 'data': {}})
    logger.write('g2')
    log_file = tmp_path / 'game_g2.log'
    assert log_file.exists()
    assert 'game_over' in log_file.read_text()
    assert 'g2' not in logger._history


def test_log_event_y_log_action_incluyen_timestamp_parseable():
    logger = GameLogger()
    logger.log_event('g1b', {'event': 'x'})
    logger.log_action('g1b', {'action': 'move', 'data': {'direction': 'up'}})

    for line, marker in zip(logger._history['g1b'], ['< [', '> [']):
        assert line.startswith(marker)
        closing = line.index(']')
        timestamp_str = line[len(marker):closing]  # arranca justo despues del '['
        datetime.fromisoformat(timestamp_str)  # no debe tirar excepcion
        json_part = line[line.index('{'):]
        json.loads(json_part)  # el JSON sigue siendo parseable igual


def test_game_logger_write_sin_historial_previo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = GameLogger()
    # nunca se llamo log_event/log_action para 'g3': igual debe poder
    # escribir un archivo (vacio) sin romperse.
    logger.write('g3')
    assert (tmp_path / 'game_g3.log').exists()


def test_game_logger_write_maneja_oserror(monkeypatch, capsys):
    logger = GameLogger()
    logger.log_event('g4', {'event': 'x'})

    def boom(*args, **kwargs):
        raise OSError('disco lleno')

    monkeypatch.setattr('builtins.open', boom)
    logger.write('g4')  # no debe propagar la excepcion
    out = capsys.readouterr().out
    assert 'could not write game log' in out
    assert 'g4' not in logger._history


# -- SnakeBot: helpers --------------------------------------------------

class FakeStrategy:
    """Estrategia fake para no depender de SnakeStrategy real en estos tests."""

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
    """Estrategia fake que tarda mas de la cuenta, para probar el limite
    de tiempo duro (_choose_direction_con_limite)."""

    def __init__(self, delay_seconds):
        self.delay_seconds = delay_seconds

    def choose_direction(self, *args, **kwargs):
        time.sleep(self.delay_seconds)
        return 'left'


class FakeWebSocket:
    """Simula una conexion websocket: guarda lo enviado y devuelve una
    cola de mensajes predefinida en .recv()."""

    def __init__(self, incoming=None):
        self.sent = []
        self._incoming = list(incoming or [])

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        if not self._incoming:
            raise websockets.ConnectionClosed(None, None)
        return self._incoming.pop(0)


def make_bot(strategy=None):
    return SnakeBot('fake-token', strategy=strategy or FakeStrategy())


# -- SnakeBot.__init__ / _send -------------------------------------------

def test_snake_bot_init_usa_strategy_por_defecto():
    bot = SnakeBot('tok')
    assert bot.auth_token == 'tok'
    assert 'tok' in bot.uri
    assert bot.strategy is not None


@pytest.mark.asyncio
async def test_send_manda_json_por_el_websocket():
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._send(ws, 'move', {'direction': 'up'})
    assert len(ws.sent) == 1
    sent = json.loads(ws.sent[0])
    assert sent == {'action': 'move', 'data': {'direction': 'up'}}


# -- SnakeBot._handle -----------------------------------------------------

@pytest.mark.asyncio
async def test_handle_challenge_acepta():
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._handle(ws, {'event': 'challenge', 'data': {'challenge_id': 'c_1'}})
    sent = json.loads(ws.sent[0])
    assert sent == {'action': 'accept_challenge', 'data': {'challenge_id': 'c_1'}}


@pytest.mark.asyncio
async def test_handle_game_over_escribe_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._handle(ws, {'event': 'game_over', 'data': {'game_id': 'g9'}})
    assert (tmp_path / 'game_g9.log').exists()


@pytest.mark.asyncio
async def test_handle_game_over_sin_game_id_no_rompe():
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._handle(ws, {'event': 'game_over', 'data': {}})  # no explota


@pytest.mark.asyncio
async def test_handle_error_solo_imprime(capsys):
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._handle(ws, {'event': 'error', 'data': {'Error': 'boom'}})
    assert 'server reported an error' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_handle_evento_desconocido_no_hace_nada():
    bot = make_bot()
    ws = FakeWebSocket()
    await bot._handle(ws, {'event': 'list_users', 'data': {'users': []}})  # no explota


@pytest.mark.asyncio
async def test_handle_your_turn_llama_a_process_turn(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    strategy = FakeStrategy(direction='right')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g5', 'turn_token': 't1',
        'score_1': 3, 'score_2': 1, 'remaining_moves': 50,
    }
    await bot._handle(ws, {'event': 'your_turn', 'data': data})
    sent = json.loads(ws.sent[0])
    assert sent['data']['direction'] == 'right'
    assert sent['data']['game_id'] == 'g5'
    assert len(strategy.calls) == 1


# -- SnakeBot._process_turn -------------------------------------------------

@pytest.mark.asyncio
async def test_process_turn_side_a_usa_score_1_como_mio():
    strategy = FakeStrategy(direction='down')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g6', 'turn_token': 't1',
        'score_1': 10, 'score_2': 4, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    (_, kwargs) = strategy.calls[0]
    # llamado posicional: (board_str, side, board_size, next_digit, my_score, opp_score, remaining_moves)
    args = strategy.calls[0][0]
    assert args[4] == 10  # my_score
    assert args[5] == 4   # opp_score


@pytest.mark.asyncio
async def test_process_turn_side_b_usa_score_2_como_mio():
    strategy = FakeStrategy(direction='down')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'B', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g7', 'turn_token': 't1',
        'score_1': 10, 'score_2': 4, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    args = strategy.calls[0][0]
    assert args[4] == 4    # my_score (soy side B -> score_2)
    assert args[5] == 10   # opp_score


@pytest.mark.asyncio
async def test_process_turn_next_digit_se_pasa_a_la_estrategia():
    strategy = FakeStrategy(direction='up')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3', 'next_digit': 7,
        'game_id': 'g8', 'turn_token': 't1',
        'score_1': 0, 'score_2': 0, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    args = strategy.calls[0][0]
    assert args[3] == 7  # next_digit


@pytest.mark.asyncio
async def test_process_turn_side_a_usa_multiplier_1_como_mio():
    strategy = FakeStrategy(direction='down')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g6b', 'turn_token': 't1',
        'score_1': 10, 'score_2': 4, 'remaining_moves': 20,
        'multiplier_1': 3, 'multiplier_2': 1,
    }
    await bot._process_turn(ws, {'data': data})
    args = strategy.calls[0][0]
    assert args[7] == 3  # my_multiplier
    assert args[8] == 1  # opp_multiplier


@pytest.mark.asyncio
async def test_process_turn_side_b_usa_multiplier_2_como_mio():
    strategy = FakeStrategy(direction='down')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'B', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g7b', 'turn_token': 't1',
        'score_1': 10, 'score_2': 4, 'remaining_moves': 20,
        'multiplier_1': 3, 'multiplier_2': 1,
    }
    await bot._process_turn(ws, {'data': data})
    args = strategy.calls[0][0]
    assert args[7] == 1  # my_multiplier (soy side B -> multiplier_2)
    assert args[8] == 3  # opp_multiplier


@pytest.mark.asyncio
async def test_process_turn_sin_multiplicador_pasa_none():
    # Partidas anteriores al 16/9/2026 no traen multiplier_1/2 -- no
    # debe romper, simplemente se pasa None.
    strategy = FakeStrategy(direction='down')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g6c', 'turn_token': 't1',
        'score_1': 0, 'score_2': 0, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    args = strategy.calls[0][0]
    assert args[7] is None
    assert args[8] is None


@pytest.mark.asyncio
async def test_process_turn_estrategia_rota_usa_direccion_al_azar():
    strategy = FakeStrategy(raise_error=True)
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g9', 'turn_token': 't1',
        'score_1': 0, 'score_2': 0, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    sent = json.loads(ws.sent[0])
    from board import DIRECTIONS
    assert sent['data']['direction'] in DIRECTIONS


# -- _choose_direction_con_limite (watchdog de timeout) ---------------------

def test_choose_direction_con_limite_camino_normal():
    bot = make_bot(FakeStrategy(direction='right'))
    d = bot._choose_direction_con_limite('|...|', 'A', '1x3', None, 0, 0, 10)
    assert d == 'right'


def test_choose_direction_con_limite_corta_por_timeout(capsys):
    bot = SnakeBot('tok', strategy=SlowStrategy(delay_seconds=0.3), decision_timeout=0.05)
    d = bot._choose_direction_con_limite('|...|', 'A', '1x3', None, 0, 0, 10)
    from board import DIRECTIONS
    assert d in DIRECTIONS
    assert 'AVISO' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_process_turn_imprime_tiempo_de_decision(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    strategy = FakeStrategy(direction='up')
    bot = make_bot(strategy)
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': '|...|', 'board_size': '1x3',
        'game_id': 'g11', 'turn_token': 't1',
        'score_1': 0, 'score_2': 0, 'remaining_moves': 20,
    }
    await bot._process_turn(ws, {'data': data})
    assert 'decision: up en' in capsys.readouterr().out


# -- SnakeBot._play ----------------------------------------------------

@pytest.mark.asyncio
async def test_play_procesa_mensajes_hasta_conexion_cerrada(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    strategy = FakeStrategy(direction='left')
    bot = make_bot(strategy)
    your_turn_msg = json.dumps({
        'event': 'your_turn',
        'data': {
            'side': 'A', 'board': '|...|', 'board_size': '1x3',
            'game_id': 'g10', 'turn_token': 't1',
            'score_1': 0, 'score_2': 0, 'remaining_moves': 20,
        },
    })
    ws = FakeWebSocket(incoming=[your_turn_msg])
    await bot._play(ws)  # deberia consumir el mensaje y salir al agotarse
    assert len(ws.sent) == 1


@pytest.mark.asyncio
async def test_play_mensaje_invalido_no_rompe_el_loop(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bot = make_bot()
    ws = FakeWebSocket(incoming=['esto no es json'])
    await bot._play(ws)
    assert 'error handling message' in capsys.readouterr().out


# -- SnakeBot.run --------------------------------------------------------

@pytest.mark.asyncio
async def test_run_sale_del_loop_con_keyboard_interrupt(monkeypatch):
    bot = make_bot()

    async def fake_sleep(_):
        return None

    class FakeConnect:
        def __init__(self, uri):
            pass

        async def __aenter__(self):
            raise KeyboardInterrupt()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr('run.asyncio.sleep', fake_sleep)
    monkeypatch.setattr('run.websockets.connect', FakeConnect)
    await bot.run()  # no debe colgarse ni propagar la excepcion


@pytest.mark.asyncio
async def test_run_conecta_exitosamente_y_juega(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = make_bot()
    ws = FakeWebSocket(incoming=[])  # recv() cierra la conexion al toque
    attempts = {'n': 0}

    async def fake_sleep(_):
        return None

    class FakeConnect:
        def __init__(self, uri):
            attempts['n'] += 1

        async def __aenter__(self):
            if attempts['n'] == 1:
                return ws  # primera vuelta: conecta y juega (linea 53-54)
            raise KeyboardInterrupt()  # segunda vuelta: cortamos el loop

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr('run.asyncio.sleep', fake_sleep)
    monkeypatch.setattr('run.websockets.connect', FakeConnect)
    await bot.run()
    assert attempts['n'] == 2


@pytest.mark.asyncio
async def test_run_reintenta_tras_error_de_conexion(monkeypatch):
    bot = make_bot()
    attempts = []

    async def fake_sleep(_):
        return None

    class FakeConnect:
        def __init__(self, uri):
            attempts.append(uri)

        async def __aenter__(self):
            if len(attempts) < 2:
                raise RuntimeError('no se pudo conectar')
            raise KeyboardInterrupt()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr('run.asyncio.sleep', fake_sleep)
    monkeypatch.setattr('run.websockets.connect', FakeConnect)
    await bot.run()
    assert len(attempts) == 2  # fallo una vez, reintento, despues corto con KeyboardInterrupt


# -- main / entrypoint ----------------------------------------------------

def test_main_sin_token_imprime_ayuda(capsys, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['run.py'])
    import runpy
    runpy.run_module('run', run_name='__main__')
    assert 'please provide your auth_token' in capsys.readouterr().out


def test_main_con_token_arranca_el_bot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run.py', 'mi-token-de-prueba'])

    async def fake_sleep(_):
        return None

    class FakeConnect:
        def __init__(self, uri):
            pass

        async def __aenter__(self):
            raise KeyboardInterrupt()  # corta el loop en la primera vuelta

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr('run.asyncio.sleep', fake_sleep)
    monkeypatch.setattr('run.websockets.connect', FakeConnect)

    import runpy
    runpy.run_module('run', run_name='__main__')  # ejecuta SnakeBot(...) + asyncio.run(bot.run())


# -- v7/v8: simbolos no ASCII en la consola de Windows ---------------------

import io  # noqa: E402

from run import safe_print  # noqa: E402

TABLERO_V8 = '|A..\U0001F4A3|\n|.Ⓐ.\U0001F9E8|\n|..bB|'


def _consola_windows(monkeypatch):
    """stdout con encoding cp1252, como la consola de Windows."""
    buf = io.BytesIO()
    monkeypatch.setattr(sys, 'stdout', io.TextIOWrapper(buf, encoding='cp1252'))
    return buf


def test_safe_print_no_rompe_con_emojis_en_cp1252(monkeypatch):
    buf = _consola_windows(monkeypatch)
    safe_print(TABLERO_V8)  # un print() comun tiraria UnicodeEncodeError
    sys.stdout.flush()
    assert b'\\U0001f4a3' in buf.getvalue()


@pytest.mark.asyncio
async def test_process_turn_con_bombas_en_consola_windows_igual_responde(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _consola_windows(monkeypatch)
    bot = make_bot(FakeStrategy(direction='down'))
    ws = FakeWebSocket()
    data = {
        'side': 'A', 'board': TABLERO_V8, 'board_size': '3x4',
        'game_id': 'g12', 'turn_token': 't1',
        'score_1': 0, 'score_2': 0, 'remaining_moves': 400,
    }
    await bot._process_turn(ws, {'data': data})
    assert json.loads(ws.sent[0])['data']['direction'] == 'down'


@pytest.mark.asyncio
async def test_play_mensaje_con_surrogates_llega_entero_a_la_estrategia(tmp_path, monkeypatch):
    # El server manda las bombas como "💣": json.loads las junta
    # en un solo caracter, y el tablero llega con una celda por bomba.
    monkeypatch.chdir(tmp_path)
    _consola_windows(monkeypatch)
    strategy = FakeStrategy(direction='up')
    bot = make_bot(strategy)
    raw = ('{"event": "your_turn", "data": {"side": "A", '
           '"board": "|A..\\ud83d\\udca3|\\n|.\\u24b6.\\ud83e\\udde8|\\n|..bB|", '
           '"board_size": "3x4", "game_id": "g13", "turn_token": "t1", '
           '"score_1": 0, "score_2": 0, "remaining_moves": 400}}')
    await bot._play(FakeWebSocket(incoming=[raw]))
    board_str = strategy.calls[0][0][0]
    assert board_str == TABLERO_V8
    assert all(len(row) == 6 for row in board_str.split('\n'))   # 4 celdas + 2 '|'


def test_game_logger_escribe_en_utf8(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = GameLogger()
    logger.log_event('g14', {'event': 'your_turn', 'data': {'board': TABLERO_V8}})
    logger.write('g14')
    contenido = (tmp_path / 'game_g14.log').read_text(encoding='utf-8')
    linea = contenido.strip()
    assert json.loads(linea[linea.index('{'):])['data']['board'] == TABLERO_V8