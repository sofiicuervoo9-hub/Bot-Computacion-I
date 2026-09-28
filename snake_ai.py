"""Estrategia de juego: decide que direccion tomar dado un Board."""

from random import choice

from board import Board, DIRECTIONS

ENDGAME_SAFETY_BUFFER = 3

# Margen de puntaje a partir del cual se activa el "modo cazador": con
# una ventaja mayor a esto, en vez de solo posicionarse de forma
# defensiva, se prioriza achicarle el espacio disponible al rival.
# En 0: cualquier ventaja (incluso minima) activa el modo cazador.
AGGRESSIVE_MARGIN = 0

# Penalidad artificial que se le suma a la distancia de un candidato
# cuyo primer paso pisa un digito equivocado. No alcanza con usar
# wrong_digit solo como desempate (ver _best_target_move): si el
# objetivo real queda "detras" de un digito equivocado en linea recta,
# ese paso puede tener la MENOR distancia total al objetivo aunque
# cueste -500 apenas se pisa -- y antes se elegia igual porque la
# distancia se comparaba primero. Con este numero (mucho mas grande
# que cualquier distancia real en un tablero de hasta 20x20) un paso
# que pisa un digito equivocado solo se elige cuando de verdad no hay
# otra alternativa segura hacia el objetivo.
WRONG_DIGIT_STEP_PENALTY = 1000


class SnakeStrategy:
    """Encapsula la logica de decision (antes era la funcion choose_direction).

    No guarda estado de una partida a la otra: cada llamada a
    choose_direction reconstruye el Board a partir de lo que llego en
    ese turno, asi que funciona igual sin importar el tamano del
    tablero de cada partida.
    """

    def __init__(self, safety_buffer=ENDGAME_SAFETY_BUFFER, aggressive_margin=AGGRESSIVE_MARGIN):
        self.safety_buffer_value = safety_buffer
        self.aggressive_margin = aggressive_margin
        self._opp_dist = {}

    def choose_direction(self, board_str, side, board_size=None, next_digit=None,
                          my_score=None, opp_score=None, remaining_moves=None,
                          my_multiplier=None, opp_multiplier=None):
        try:
            board = Board(board_str, side, board_size, next_digit)
        except Exception:
            return choice(list(DIRECTIONS.keys()))

        if board.head is None:
            return choice(list(DIRECTIONS.keys()))

        candidates = self._build_candidates(board)
        if not candidates:
            # No hay movimiento seguro: vamos a chocar igual, elegimos algo.
            return choice(list(DIRECTIONS.keys()))

        safety_buffer = self._safety_buffer(board, my_score, opp_score, remaining_moves)

        # El digito correcto y un pickup 'X' compiten por distancia, no
        # por una prioridad fija: como casi siempre hay un digito
        # alcanzable (hay 5 en tablero todo el tiempo), darle prioridad
        # fija al digito significa que el bot practicamente nunca se
        # desvia a buscar un 'X' -- y el multiplicador que da es
        # permanente, se acumula sobre TODOS los digitos que comamos
        # despues. Por eso: si el 'X' esta mas cerca (o igual de cerca)
        # que el digito, conviene ir por el primero.
        food_step, food_dist = self._best_target_move(candidates, board.food, safety_buffer)
        mult_step, mult_dist = self._best_target_move(candidates, board.multiplier_pickups, safety_buffer)

        if food_step is not None and mult_step is not None:
            step = mult_step if mult_dist <= food_dist else food_step
            return step
        if food_step is not None:
            return food_step
        if mult_step is not None:
            return mult_step

        aggressive = self._is_aggressive(my_score, opp_score, board)
        return self._best_territory_move(board, candidates, aggressive)

    # -- pasos internos --------------------------------------------------

    def _safety_buffer(self, board, my_score, opp_score, remaining_moves):
        endgame = remaining_moves is not None and remaining_moves <= max(10, len(board.body_cells))
        if my_score is not None and opp_score is not None and my_score > opp_score and endgame:
            return self.safety_buffer_value
        # v5: con un muro activo en el tablero, un calculo justo que
        # termine chocandolo sale carisimo sobre el final de la partida
        # (-500 y un turno entero sin moverse, sin tiempo para
        # recuperarse) -- mas cautela ahi aunque no vayamos ganando.
        if board.wall_cells and endgame:
            return self.safety_buffer_value
        return 0

    def _is_aggressive(self, my_score, opp_score, board=None):
        # "Modo cazador": voy ganando por mas del margen configurado, asi
        # que en vez de solo posicionarme defensivamente, priorizo
        # achicarle las opciones al rival.
        #
        # v5: un muro activo tambien activa el modo cazador, gane o no
        # -- achica el tablero de forma temporal y crea cuellos de
        # botella reales (ver opp_space en _build_candidates, que ya
        # cuenta el muro como obstaculo tanto para mi como para el
        # rival). Es una ventana corta para invadir terreno rival y
        # dejarlo con menos espacio antes de que el muro desaparezca,
        # vale la pena aprovecharla aunque todavia no vaya ganando.
        if board is not None and board.wall_cells:
            return True
        if my_score is None or opp_score is None:
            return False
        return my_score > opp_score + self.aggressive_margin

    def _build_candidates(self, board):
        opponent_own_blocked = board.opponent_blocked - {board.opponent_head}
        # v5: las celdas de muro ('#') nadie las puede pisar este turno
        # (chocar no mueve a la vibora), asi que cuentan como bloqueadas
        # para todo calculo de alcance/territorio -- tanto el mio como
        # el del rival.
        opponent_static_blocked = board.body_cells | opponent_own_blocked | board.wall_cells
        self._opp_dist = board.bfs_all_distances(board.opponent_head, opponent_static_blocked)

        food_set = set(board.food)
        candidates = {}
        for dname, pos in board.neighbors(board.head):
            if pos in board.opponent_blocked or pos in board.body_cells:
                continue
            ate = pos in food_set
            if ate:
                new_body_len = len(board.body_cells) + 1
                new_blocked = board.body_cells | board.opponent_blocked | board.wall_cells
            else:
                new_body_len = len(board.body_cells)
                base = board.body_cells - {board.tail} if board.tail is not None else board.body_cells
                new_blocked = base | board.opponent_blocked | board.wall_cells
            # Si `pos` es una celda de muro, queda adentro de new_blocked:
            # bfs_all_distances la ve como punto de partida bloqueado y
            # devuelve {} (space=0). Eso ya alcanza para que este
            # candidato pierda contra cualquier alternativa real en
            # _best_target_move (exige dist_map.get(target) y el chequeo
            # de espacio minimo) y en _best_territory_move (queda afuera
            # de "safe") sin necesitar una penalidad aparte -- solo se
            # elige si de verdad no queda ninguna otra salida no fatal.
            dist_map = board.bfs_all_distances(pos, new_blocked)
            # v6: con 3-5 copias por digito hay entre 12 y 20 digitos
            # equivocados repartidos por el tablero, asi que es comun
            # que el camino mas corto al objetivo pase por uno de ellos
            # en el 2do, 3er... paso (no solo en el primero). Este
            # segundo mapa de distancias trata a los digitos equivocados
            # como obstaculos, para medir el camino LIMPIO hasta cada
            # objetivo. Si `pos` misma es un digito equivocado se la
            # deja como punto de partida valido (esa penalidad ya la
            # cuenta el flag wrong_digit).
            safe_blocked = new_blocked | (board.wrong_digit_positions - {pos})
            safe_dist_map = board.bfs_all_distances(pos, safe_blocked)
            space = len(dist_map)
            territory = sum(
                1 for cell, d in dist_map.items()
                if self._opp_dist.get(cell) is None or (d + 1) < self._opp_dist[cell]
            )
            # Cuanto espacio le quedaria al rival si yo tomo este paso: mi
            # nuevo cuerpo (incluida esta celda) pasa a bloquearlo a el
            # tambien. Sirve para el modo cazador: preferir movimientos
            # que le achican las opciones, no solo los que me convienen
            # a mi. new_blocked ya incluye a board.opponent_blocked (que
            # trae su propia cabeza adentro) -- hay que sacarla o el BFS
            # arranca "bloqueado" y siempre da 0.
            opp_blocked_after = (opponent_own_blocked | new_blocked | {pos}) - {board.opponent_head}
            opp_space = len(board.bfs_all_distances(board.opponent_head, opp_blocked_after))
            candidates[dname] = {
                'dir': dname, 'pos': pos, 'space': space, 'dist_map': dist_map,
                'safe_dist_map': safe_dist_map,
                'body_len': new_body_len, 'territory': territory, 'opp_space': opp_space,
                # v3: pisar un digito que no es el objetivo no mata, pero
                # cuesta -500 -- se evita salvo que no haya alternativa.
                'wrong_digit': pos in board.wrong_digit_positions,
                # v5: chocar contra el muro tampoco mata, pero cuesta
                # -500 y la vibora no avanza -- mismo criterio que
                # wrong_digit, se evita salvo que no haya alternativa.
                'wall_hit': pos in board.wall_cells,
            }
        return candidates

    def _best_target_move(self, candidates, targets, safety_buffer):
        """Busca el paso mas conveniente hacia el mas cercano de
        `targets` (el digito objetivo, o los pickups 'X', segun con que
        se lo llame). Devuelve (direccion, distancia_total) del mejor
        candidato seguro, o (None, None) si ninguno lo es -- la
        distancia se usa afuera para decidir entre ir por el digito o
        por un 'X' segun cual este mas cerca.

        v6: `targets` puede traer varias copias del digito objetivo;
        se evaluan todas y gana la mas cercana alcanzable (cualquiera
        vale lo mismo, y comer una borra las demas)."""
        ranked = []
        for target in set(targets):
            best_step, best_key = None, None
            for cand in candidates.values():
                d = cand['safe_dist_map'].get(target)
                if d is not None:
                    total = d + 1
                else:
                    # No hay camino limpio: solo se llega pasando por
                    # algun digito equivocado mas adelante (-500 en
                    # algun momento). Se permite, pero penalizado igual
                    # que pisar uno en el primer paso.
                    d = cand['dist_map'].get(target)
                    if d is None:
                        continue
                    total = d + 1 + WRONG_DIGIT_STEP_PENALTY
                if cand['wrong_digit']:
                    # Este primer paso pisa un digito que no es el
                    # objetivo -- cuesta -500 apenas se pisa, sin
                    # importar que tan cerca del objetivo quede
                    # despues. Se penaliza fuerte para que solo se
                    # elija si ninguna otra direccion progresa hacia
                    # el objetivo sin pisarlo.
                    total += WRONG_DIGIT_STEP_PENALTY
                key = (total, cand['wrong_digit'])
                if best_key is None or key < best_key:
                    best_key, best_step = key, cand['dir']
            if best_step is not None:
                ranked.append((best_key[0], best_step, target))
        ranked.sort(key=lambda t: t[0])

        for my_d, step, target in ranked:
            opp_d = self._opp_dist.get(target)
            if opp_d is not None and opp_d < my_d:
                continue
            cand = candidates[step]
            if cand['space'] >= cand['body_len'] + safety_buffer:
                return step, my_d
        return None, None

    def _best_territory_move(self, board, candidates, aggressive=False):
        tail_for_rank = board.tail if board.tail is not None else board.head
        safe = [c for c in candidates.values() if c['space'] >= c['body_len']]
        pool = safe or list(candidates.values())

        def rank(cand):
            dist_to_opp = board.manhattan(cand['pos'], board.opponent_head) if board.opponent_head else 0
            dist_to_tail = board.manhattan(cand['pos'], tail_for_rank)
            # wrong_digit/wall_hit van primero en la tupla: False (0)
            # ordena antes que True (1), asi que un paso que pisa un
            # digito equivocado o choca contra el muro se elige de
            # ultima opcion. .get() por compatibilidad con candidatos
            # armados a mano en los tests, que no siempre traen la
            # clave 'wall_hit'.
            costoso = cand['wrong_digit'] or cand.get('wall_hit', False)
            if aggressive:
                # Modo cazador: antes que maximizar mi propio territorio,
                # prefiero el paso que mas le achica el espacio al rival.
                return (costoso, cand['opp_space'], -cand['territory'], -dist_to_opp, dist_to_tail)
            return (costoso, -cand['territory'], -dist_to_opp, dist_to_tail)

        best = min(pool, key=rank)
        return best['dir']


# Wrapper funcional para compatibilidad con codigo/tests que todavia
# llaman choose_direction(board, side, ...) directamente.
_default_strategy = SnakeStrategy()


def choose_direction(board, side, my_score=None, opp_score=None, remaining_moves=None,
                      board_size=None, next_digit=None, my_multiplier=None, opp_multiplier=None):
    return _default_strategy.choose_direction(
        board, side, board_size, next_digit, my_score, opp_score, remaining_moves,
        my_multiplier, opp_multiplier,
    )
