"""Cliente websocket del bot: habla con el servidor y delega la decision en
SnakeStrategy."""

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from random import choice

import websockets

from board import DIRECTIONS
from snake_ai import SnakeStrategy

SERVER_URL = "wss://server.codechallenge.net.ar/ws"


def safe_print(text):
    """print() que no rompe con simbolos no ASCII en la consola de Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode('ascii', 'backslashreplace').decode('ascii'))


class GameLogger:
    """Guarda lo enviado y recibido y lo vuelca a game_<id>.log."""

    def __init__(self):
        self._history = {}

    @staticmethod
    def _timestamp():
        return datetime.now().isoformat(sep=' ', timespec='milliseconds')

    def log_event(self, game_id, message):
        self._history.setdefault(game_id, []).append(
            f"< [{self._timestamp()}] " + json.dumps(message)
        )

    def log_action(self, game_id, message):
        self._history.setdefault(game_id, []).append(
            f"> [{self._timestamp()}] " + json.dumps(message)
        )

    def write(self, game_id):
        try:
            with open(f"game_{game_id}.log", "w", encoding="utf-8") as f:
                f.write("\n".join(self._history.get(game_id, [])) + "\n")
            print(f"saved game_{game_id}.log")
        except OSError as e:
            print(f"could not write game log: {e}")
        finally:
            self._history.pop(game_id, None)


class SnakeBot:
    """Cliente del Code Challenge para el juego Snake."""

    # Tiempo maximo por decision (segundos); es una red de seguridad.
    DECISION_TIMEOUT = 1.0

    def __init__(self, auth_token, strategy=None, decision_timeout=None):
        self.auth_token = auth_token
        # Si se pasa una estrategia se usa en todas las partidas (tests); si
        # no, una por partida.
        self.strategy = strategy
        self._strategies = {}
        self.logger = GameLogger()
        self.uri = "{}?token={}".format(SERVER_URL, auth_token)
        self.decision_timeout = (
            self.DECISION_TIMEOUT
            if decision_timeout is None
            else decision_timeout
        )
        self._handlers = {
            'game_over': self._on_game_over,
            'challenge': self._on_challenge,
            'your_turn': self._on_your_turn,
            'error': self._on_error,
        }

    def strategy_for(self, game_id):
        """Estrategia de una partida: cada partida guarda su propio estado."""
        if self.strategy is not None:
            return self.strategy
        if game_id not in self._strategies:
            self._strategies[game_id] = SnakeStrategy()
        return self._strategies[game_id]

    async def run(self):
        while True:
            try:
                # Sin el token: cualquier captura de la consola permitiria
                # jugar en mi nombre.
                print('connection to {}'.format(SERVER_URL))
                async with websockets.connect(self.uri) as websocket:
                    print('connection READY!')
                    await self._play(websocket)
            except KeyboardInterrupt:
                print('Exiting...')
                break
            except Exception as e:
                print(f'connection error: {e}')
            await asyncio.sleep(3)

    async def _send(self, websocket, action, data):
        message = json.dumps({'action': action, 'data': data})
        safe_print(message)
        await websocket.send(message)

    async def _play(self, websocket):
        while True:
            try:
                request = await websocket.recv()
            except websockets.ConnectionClosed as e:
                print(f'connection closed: {e}')
                break

            safe_print(f"< {request}")
            try:
                await self._handle(websocket, json.loads(request))
            except Exception as e:
                print(f'error handling message: {e}')

    async def _handle(self, websocket, request_data):
        handler = self._handlers.get(request_data.get('event'))
        if handler is not None:
            await handler(websocket, request_data)

    async def _on_game_over(self, websocket, request_data):
        game_id = request_data['data'].get('game_id')
        if game_id:
            self.logger.log_event(game_id, request_data)
            self.logger.write(game_id)
            self._strategies.pop(game_id, None)

    async def _on_challenge(self, websocket, request_data):
        await self._send(
            websocket,
            'accept_challenge',
            {'challenge_id': request_data['data']['challenge_id']},
        )

    async def _on_your_turn(self, websocket, request_data):
        self.logger.log_event(request_data['data']['game_id'], request_data)
        await self._process_turn(websocket, request_data)

    async def _on_error(self, websocket, request_data):
        print(f"server reported an error: {request_data.get('data')}")

    @staticmethod
    def _turn_kwargs(data):
        """Datos del turno vistos desde mi lado (side A usa score_1, side B usa
        score_2)."""
        mine, theirs = ('1', '2') if data['side'] == 'A' else ('2', '1')
        return {
            'board_size': data.get('board_size'),
            'my_score': data.get('score_' + mine),
            'opp_score': data.get('score_' + theirs),
            'remaining_moves': data.get('remaining_moves'),
            'my_multiplier': data.get('multiplier_' + mine),
            'opp_multiplier': data.get('multiplier_' + theirs),
        }

    async def _process_turn(self, websocket, request_data):
        data = request_data['data']
        game_id = data['game_id']
        safe_print(data['board'])
        start = time.perf_counter()
        try:
            direction = self._choose_direction_with_timeout(
                self.strategy_for(game_id),
                data['board'],
                data['side'],
                **self._turn_kwargs(data),
            )
        except Exception:
            # Ante un error en la estrategia, mejor una direccion al azar que
            # no responder.
            direction = choice(list(DIRECTIONS.keys()))
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"decision: {direction} in {elapsed_ms:.1f} ms")

        move = {
            'game_id': game_id,
            'turn_token': data['turn_token'],
            'direction': direction,
        }
        self.logger.log_action(game_id, {'action': 'move', 'data': move})
        await self._send(websocket, 'move', move)

    def _choose_direction_with_timeout(
        self, strategy, board_str, side, **kwargs
    ):
        """Corre la estrategia en un thread; si se pasa del tiempo, direccion
        al azar."""
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            strategy.choose_direction, board_str, side, **kwargs
        )
        try:
            return future.result(timeout=self.decision_timeout)
        except FutureTimeoutError:
            print(
                f"WARNING: strategy took longer than "
                f"{self.decision_timeout}s, using a random direction"
            )
            return choice(list(DIRECTIONS.keys()))
        finally:
            executor.shutdown(wait=False)


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        bot = SnakeBot(sys.argv[1])
        asyncio.run(bot.run())
    else:
        print('please provide your auth_token')
