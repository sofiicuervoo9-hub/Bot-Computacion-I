"""Cliente websocket del bot: habla el protocolo del servidor y delega
la decision de movimiento en una estrategia (SnakeStrategy)."""

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


class GameLogger:
    """Guarda el historial (recibido/enviado) de cada partida y lo
    vuelca a game_<id>.log cuando termina.

    Cada linea lleva un timestamp (hora local, con milisegundos) entre
    corchetes despues de la marca '< '/'> ' -- sirve para diferenciar,
    por ejemplo, una partida cortada por un limite de tiempo real del
    torneo de una cortada por otro motivo, cosa que antes no se podia
    ver en el log. El '< '/'> ' se mantiene como los primeros dos
    caracteres de la linea (compatibilidad con quien ya parsea por
    eso); para el JSON en si conviene ubicarlo por la primera '{' de la
    linea en vez de una posicion fija, asi sirve tanto para logs viejos
    (sin timestamp) como para estos."""

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
            with open(f"game_{game_id}.log", "w") as f:
                f.write("\n".join(self._history.get(game_id, [])) + "\n")
            print(f"saved game_{game_id}.log")
        except OSError as e:
            print(f"could not write game log: {e}")
        finally:
            self._history.pop(game_id, None)


class SnakeBot:
    """Cliente del Code Challenge para el juego Snake."""

    # Margen de sobra: benchmarks locales (tableros 12x12 a 20x20, con
    # cuerpos largos) dan ~1-4ms por decision, muy por debajo de esto.
    # Es una red de seguridad, no el tiempo esperado real.
    DECISION_TIMEOUT = 1.0  # segundos

    def __init__(self, auth_token, strategy=None, decision_timeout=None):
        self.auth_token = auth_token
        self.strategy = strategy or SnakeStrategy()
        self.logger = GameLogger()
        self.uri = "wss://server.codechallenge.net.ar/ws?token={}".format(auth_token)
        self.decision_timeout = (
            self.DECISION_TIMEOUT if decision_timeout is None else decision_timeout
        )

    async def run(self):
        while True:
            try:
                print('connection to {}'.format(self.uri))
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
        print(message)
        await websocket.send(message)

    async def _play(self, websocket):
        while True:
            try:
                request = await websocket.recv()
            except websockets.ConnectionClosed as e:
                print(f'connection closed: {e}')
                break

            print(f"< {request}")
            try:
                await self._handle(websocket, json.loads(request))
            except Exception as e:
                print(f'error handling message: {e}')

    async def _handle(self, websocket, request_data):
        event = request_data.get('event')
        if event == 'game_over':
            game_id = request_data['data'].get('game_id')
            if game_id:
                self.logger.log_event(game_id, request_data)
                self.logger.write(game_id)
        elif event == 'challenge':
            await self._send(
                websocket,
                'accept_challenge',
                {'challenge_id': request_data['data']['challenge_id']},
            )
        elif event == 'your_turn':
            self.logger.log_event(request_data['data']['game_id'], request_data)
            await self._process_turn(websocket, request_data)
        elif event == 'error':
            print(f"server reported an error: {request_data.get('data')}")

    async def _process_turn(self, websocket, request_data):
        data = request_data['data']
        side = data['side']
        board_str = data['board']
        # El tamano del tablero varia por partida (y puede variar entre
        # turnos); usamos siempre lo que manda el servidor, nunca un
        # valor fijo.
        board_size = data.get('board_size')
        # v3: el server manda directo cual es el proximo digito correcto
        # a comer -- lo usamos en vez de inferirlo del tablero.
        next_digit = data.get('next_digit')
        game_id = data['game_id']
        turn_token = data['turn_token']

        if side == 'A':
            my_score, opp_score = data.get('score_1'), data.get('score_2')
            my_multiplier, opp_multiplier = data.get('multiplier_1'), data.get('multiplier_2')
        else:
            my_score, opp_score = data.get('score_2'), data.get('score_1')
            my_multiplier, opp_multiplier = data.get('multiplier_2'), data.get('multiplier_1')
        remaining_moves = data.get('remaining_moves')

        print(board_str)
        start = time.perf_counter()
        try:
            direction = self._choose_direction_con_limite(
                board_str, side, board_size, next_digit, my_score, opp_score, remaining_moves,
                my_multiplier, opp_multiplier,
            )
        except Exception:
            # Si hay un bug en la estrategia, elegimos una direccion al azar
            # antes que dejar de responder (y perder el turno por timeout).
            direction = choice(list(DIRECTIONS.keys()))
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"decision: {direction} en {elapsed_ms:.1f} ms")

        move = {'game_id': game_id, 'turn_token': turn_token, 'direction': direction}
        self.logger.log_action(game_id, {'action': 'move', 'data': move})
        await self._send(websocket, 'move', move)

    def _choose_direction_con_limite(self, *args):
        """Corre la estrategia con un limite de tiempo duro: si por algun
        motivo tarda mas de decision_timeout (nunca deberia, la logica es
        toda BFS acotada por el tamano del tablero -- ver benchmark en los
        tests), respondemos con una direccion al azar en vez de arriesgarnos
        a perder el turno por timeout del server. Se corre en un thread
        aparte porque un timeout normal no puede interrumpir codigo
        sincronico de Python a mitad de ejecucion."""
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.strategy.choose_direction, *args)
        try:
            return future.result(timeout=self.decision_timeout)
        except FutureTimeoutError:
            print(f"AVISO: la estrategia tardo mas de {self.decision_timeout}s, uso una direccion al azar")
            return choice(list(DIRECTIONS.keys()))
        finally:
            # wait=False: si de verdad quedo colgado, no bloqueamos el
            # siguiente turno esperando a que termine.
            executor.shutdown(wait=False)


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        bot = SnakeBot(sys.argv[1])
        asyncio.run(bot.run())
    else:
        print('please provide your auth_token')