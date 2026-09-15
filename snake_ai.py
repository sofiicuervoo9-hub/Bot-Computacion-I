"""Estrategia de juego: decide que direccion tomar dado un Board."""

from random import choice

from board import Board, DIRECTIONS

ENDGAME_SAFETY_BUFFER = 3

# Margen de puntaje a partir del cual se activa el "modo cazador": con
# una ventaja mayor a esto, en vez de solo posicionarse de forma
# defensiva, se prioriza achicarle el espacio disponible al rival.
# En 0: cualquier ventaja (incluso minima) activa el modo cazador.
AGGRESSIVE_MARGIN = 0


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
                          my_score=None, opp_score=None, remaining_moves=None):
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

        step = self._best_food_move(board, candidates, safety_buffer)
        if step is not None:
            return step

        aggressive = self._is_aggressive(my_score, opp_score)
        return self._best_territory_move(board, candidates, aggressive)

    # -- pasos internos --------------------------------------------------

    def _safety_buffer(self, board, my_score, opp_score, remaining_moves):
        if my_score is not None and opp_score is not None and my_score > opp_score:
            if remaining_moves is not None and remaining_moves <= max(10, len(board.body_cells)):
                return self.safety_buffer_value
        return 0

    def _is_aggressive(self, my_score, opp_score):
        # "Modo cazador": voy ganando por mas del margen configurado, asi
        # que en vez de solo posicionarme defensivamente, priorizo
        # achicarle las opciones al rival.
        if my_score is None or opp_score is None:
            return False
        return my_score > opp_score + self.aggressive_margin

    def _build_candidates(self, board):
        opponent_own_blocked = board.opponent_blocked - {board.opponent_head}
        opponent_static_blocked = board.body_cells | opponent_own_blocked
        self._opp_dist = board.bfs_all_distances(board.opponent_head, opponent_static_blocked)

        food_set = set(board.food)
        candidates = {}
        for dname, pos in board.neighbors(board.head):
            if pos in board.opponent_blocked or pos in board.body_cells:
                continue
            ate = pos in food_set
            if ate:
                new_body_len = len(board.body_cells) + 1
                new_blocked = board.body_cells | board.opponent_blocked
            else:
                new_body_len = len(board.body_cells)
                base = board.body_cells - {board.tail} if board.tail is not None else board.body_cells
                new_blocked = base | board.opponent_blocked
            dist_map = board.bfs_all_distances(pos, new_blocked)
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
                'body_len': new_body_len, 'territory': territory, 'opp_space': opp_space,
                # v3: pisar un digito que no es el objetivo no mata, pero
                # cuesta -500 -- se evita salvo que no haya alternativa.
                'wrong_digit': pos in board.wrong_digit_positions,
            }
        return candidates

    def _best_food_move(self, board, candidates, safety_buffer):
        food_targets = []
        for target in set(board.food):
            best_step, best_key = None, None
            for cand in candidates.values():
                d = cand['dist_map'].get(target)
                if d is None:
                    continue
                total = d + 1
                # A igual distancia, se prefiere el paso que no pisa un
                # digito equivocado en el camino.
                key = (total, cand['wrong_digit'])
                if best_key is None or key < best_key:
                    best_key, best_step = key, cand['dir']
            if best_step is not None:
                food_targets.append((best_key[0], best_step, target))
        food_targets.sort(key=lambda t: t[0])

        for my_d, step, target in food_targets:
            opp_d = self._opp_dist.get(target)
            if opp_d is not None and opp_d < my_d:
                continue
            cand = candidates[step]
            if cand['space'] >= cand['body_len'] + safety_buffer:
                return step
        return None

    def _best_territory_move(self, board, candidates, aggressive=False):
        tail_for_rank = board.tail if board.tail is not None else board.head
        safe = [c for c in candidates.values() if c['space'] >= c['body_len']]
        pool = safe or list(candidates.values())

        def rank(cand):
            dist_to_opp = board.manhattan(cand['pos'], board.opponent_head) if board.opponent_head else 0
            dist_to_tail = board.manhattan(cand['pos'], tail_for_rank)
            # wrong_digit va primero en la tupla: False (0) ordena antes
            # que True (1), asi que se elige de ultima opcion.
            if aggressive:
                # Modo cazador: antes que maximizar mi propio territorio,
                # prefiero el paso que mas le achica el espacio al rival.
                return (cand['wrong_digit'], cand['opp_space'], -cand['territory'], -dist_to_opp, dist_to_tail)
            return (cand['wrong_digit'], -cand['territory'], -dist_to_opp, dist_to_tail)

        best = min(pool, key=rank)
        return best['dir']


# Wrapper funcional para compatibilidad con codigo/tests que todavia
# llaman choose_direction(board, side, ...) directamente.
_default_strategy = SnakeStrategy()


def choose_direction(board, side, my_score=None, opp_score=None, remaining_moves=None,
                      board_size=None, next_digit=None):
    return _default_strategy.choose_direction(
        board, side, board_size, next_digit, my_score, opp_score, remaining_moves
    )