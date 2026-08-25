import asyncio
import json
from random import choice
import sys
import websockets

from snake_ai import DIRECTIONS, choose_direction

HISTORY = {}

def log_event(game_id, message): # aca el servidor manda algo
    #game_id dice a que partida pertenece el mensaje  y el mensaje completo parseado en json '<'
    HISTORY.setdefault(game_id, []).append('< ' + json.dumps(message)) 


def log_action(game_id, message): #aca yo le respondo al servidor '>'
    HISTORY.setdefault(game_id, []).append('> ' + json.dumps(message))


def write_game_log(game_id):
    try:
        with open(f"game_{game_id}.log", "w") as f: #abre (o crea, si no existe) un archivo llamado game_<game_id>.log en modo escritura ("w")
            f.write("\n".join(HISTORY.get(game_id, [])) + "\n")
        print(f"saved game_{game_id}.log")
    except OSError as e:
        print(f"could not write game log: {e}")
    finally:
        HISTORY.pop(game_id, None) # se borra la partida apenas se guarda el archivo 


async def send(websocket, action, data):
    message = json.dumps(
        { #arma el JSON {"action": "accept_challenge", "data": {"challenge_id": "c_1a2b"}}
            'action': action,
            'data': data,
        }
    )
    print(message)
    await websocket.send(message)


async def start(auth_token):
    #se arma la URL
    uri = "wss://server.codechallenge.net.ar/ws?token={}".format(auth_token)
    while True:
        try:
            print('connection to {}'.format(uri))
            #conexión con el websocket 
            async with websockets.connect(uri) as websocket: #se abre la conexión;  se queda abierta 
                print('connection READY!')
                await play(websocket)
        except KeyboardInterrupt:
            print('Exiting...')
            break
        except Exception as e:
            print(f'connection error: {e}')
        await asyncio.sleep(3)


async def play(websocket):
    while True:
        try:
            request = await websocket.recv() #espera, sin hacer nada más, hasta que llegue un mensaje 
        except websockets.ConnectionClosed as e: # excepción si es que se corto al conexión con el servidor 
            print(f'connection closed: {e}')
            break

        print(f"< {request}")
        try:
            request_data = json.loads(request)
            event = request_data.get('event')
            if event == 'game_over':
                game_id = request_data['data'].get('game_id')
                if game_id:
                    log_event(game_id, request_data)
                    write_game_log(game_id)
            elif event == 'challenge':
                await send(
                    websocket,
                    'accept_challenge',
                    {
                        'challenge_id': request_data['data']['challenge_id'],
                    },
                )
            elif event == 'your_turn': # este es el evento mas importante
                #es el primer parametro game_id --> esto le dice a log_event en que carpeta de HISTORY guardar la línea y request_data es el segundo parámetro completo 
                log_event(request_data['data']['game_id'], request_data)
                await process_your_turn(websocket, request_data)
            elif event == 'error':
                print(f"server reported an error: {request_data.get('data')}")
        except Exception as e:
            print(f'error handling message: {e}') #error de procesamiento de un mensaje puntual (el bot sigue jugando)


async def process_your_turn(websocket, request_data):
    await process_move(websocket, request_data)


async def process_move(websocket, request_data):
    data = request_data['data']
    side = data['side'] #mi lado en la partida: si es A o B
    board = data['board'] #string del tablero completo 
    game_id = data['game_id'] #id de la partida
    turn_token = data['turn_token'] #codigo del servidor para el turno en específico 
    #se resuelve una ambiguedad: por convención del servidor, el lado "A" corresponde siempre a player_1/score_1, y "B" a player_2/score_2
    if side == 'A':
        my_score, opp_score = data.get('score_1'), data.get('score_2')
    else:
        my_score, opp_score = data.get('score_2'), data.get('score_1')
    remaining_moves = data.get('remaining_moves') #cuántos movimientos quedan antes de que termine la partida por límite de tiempo 

    print(board)
    try:
        direction = choose_direction(board, side, my_score, opp_score, remaining_moves)
    except Exception as e:
        #si hay un bug se elige una dirección al azar
        direction = choice(list(DIRECTIONS.keys()))

    move = { #armo el diccionario que que se espera por protocolo 
        'game_id': game_id,
        'turn_token': turn_token,
        'direction': direction,
    }
    log_action(move['game_id'], {'action': 'move', 'data': move}) #dirección elegida
    await send(websocket, 'move', move)

#arranca el programa: se ejecuta si se corre 
if __name__ == '__main__':
    #sys.argv es la lista de argumentos pasados por parámetros 
    #sys.argv[0] es el run.py y el siguiente sys.argv[1] seria el primer argumento extra que se convierte en auth_token 
    if len(sys.argv) >= 2:
        auth_token = sys.argv[1]
        #start abre la conexión con el servidor
        asyncio.run(start(auth_token))
    else:
        print('please provide your auth_token')
