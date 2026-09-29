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

# v4: parametros para decidir entre el digito y un 'X' (ver _x_primero).
# Turnos propios que se asumen si no llega remaining_moves.
X_DEFAULT_TURNS = 150
# Minimo de pasos que se estiman entre un digito y el siguiente.
X_MIN_STEPS_PER_DIGIT = 5
# Cuantos digitos hacia adelante se prueban para ir a esperar cuando el
# rival gana la carrera por el objetivo actual.
NEXT_DIGITS_AHEAD = 3
# Si mi multiplicador esta por debajo del rival, mientras espero al
# siguiente digito acepto un desvio a un 'X' aunque el calculo diga que
# el rival llega hasta estos pasos antes (el calculo supone que el rival
# va derecho, y casi nunca lo hace). Ver partida my_match 7.
X_CATCHUP_TOLERANCE = 3

# Carrera por el digito objetivo: el calculo supone que el rival va
# derecho, pero muchas veces se desvia (por ejemplo, a juntar 'X'). Por
# cada turno mio en que el rival NO se acerco al objetivo, se le suman
# estos pasos a su distancia (hasta RACE_STALL_MAX turnos). Cuando se
# vuelve a acercar, se descuenta de a un turno. Ver partida my_match 9.
RACE_STALL_BONUS = 2
RACE_STALL_MAX = 10


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
        # Seguimiento de la carrera por el digito objetivo (ver
        # _update_race). Es el unico estado entre turnos: se reinicia
        # solo cuando cambia el objetivo o sus posiciones.
        self._race_key = None
        self._race_last = None
        self._race_stall = 0
        self._food_bonus = 0

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
        self._update_race(board)
        if not candidates:
            # No hay movimiento seguro: vamos a chocar igual, elegimos algo.
            return choice(list(DIRECTIONS.keys()))

        safety_buffer = self._safety_buffer(board, my_score, opp_score, remaining_moves)

        # v4: el digito y el 'X' se comparan por PUNTOS, no por distancia
        # (ver _x_primero). Un digito vale digito x 100 x multiplicador; el
        # 'X' vale +50 y un escalon mas de multiplicador para el resto de
        # la partida, asi que conviene mas cuanto mas partida queda.
        food_step, food_dist = self._best_target_move(candidates, board.food, safety_buffer,
                                                      opp_bonus=self._food_bonus)
        mult_step, mult_dist = self._best_target_move(candidates, board.multiplier_pickups, safety_buffer)

        if food_step is not None and mult_step is not None:
            # Ademas de convenir en puntos, el 'X' tiene que dejarme llegar
            # al digito antes que el rival. Si no, el bot encadena un 'X'
            # tras otro y nunca come (partida my_match 6).
            if (self._x_primero(board, food_dist, mult_dist, my_multiplier, remaining_moves)
                    and self._x_no_me_hace_perder(
                        board, candidates, board.food,
                        self._opp_time_to(board.food, self._food_bonus))):
                return mult_step
            return food_step
        if food_step is not None:
            return food_step

        # El digito objetivo no esta disponible (el rival llega antes, o
        # no hay camino). En vez de ir a juntar 'X' y quedar lejos de
        # todo, conviene esperar al lado del SIGUIENTE digito del orden:
        # cuando el rival se coma el actual, ese pasa a ser el objetivo y
        # quedamos pegados (ver _plan_siguiente_digito).
        next_step = self._plan_siguiente_digito(board, candidates, safety_buffer, mult_step,
                                                my_multiplier, opp_multiplier)
        if next_step is not None:
            return next_step
        if mult_step is not None:
            return mult_step

        aggressive = self._is_aggressive(my_score, opp_score, board)
        return self._best_territory_move(board, candidates, aggressive)

    # -- v4: digito o 'X' --------------------------------------------------

    @staticmethod
    def _my_turns_left(remaining_moves):
        """remaining_moves cuenta los movimientos de LOS DOS jugadores (en
        el log de ejemplo baja de 300 a 298 entre dos turnos mios), asi
        que los turnos propios que quedan, incluido este, son la mitad."""
        if remaining_moves is None:
            return X_DEFAULT_TURNS
        return (remaining_moves + 1) // 2

    def _x_primero(self, board, food_dist, x_dist, my_multiplier, remaining_moves):
        """Compara dos planes y devuelve True si conviene ir primero al 'X':

        A) digito y despues X:  digito x100 x m      + 50 + ingreso(resto)
        B) X y despues digito:  50 + digito x100 x (m+1) + ingreso(resto)

        "ingreso" son los puntos de los digitos que vendrian despues, ya
        con multiplicador m+1 en los dos planes. Solo cuenta lo que se
        alcanza antes de que termine la partida, por eso al final el 'X'
        tiende a valer solo +50.
        """
        m = my_multiplier or 1
        digit = board.target_digit or 1
        turns = self._my_turns_left(remaining_moves)
        # Distancia entre los dos objetivos: cota superior pasando por la
        # cabeza (no sabemos cual copia/cual X eligio _best_target_move).
        between = food_dist + x_dist

        digits = list(board.digit_values.values())
        avg_digit = sum(digits) / len(digits) if digits else 5
        steps_per_digit = max(X_MIN_STEPS_PER_DIGIT, (board.n_rows + board.n_cols) // 4)
        rate = 100 * avg_digit * (m + 1) / steps_per_digit  # puntos por turno

        def plan(first_dist, first_pts, second_pts):
            pts = first_pts if first_dist <= turns else 0
            if first_dist + between <= turns:
                pts += second_pts
            return pts + rate * max(0, turns - first_dist - between)

        plan_a = plan(food_dist, digit * 100 * m, 50)
        plan_b = plan(x_dist, 50, digit * 100 * (m + 1))
        return plan_b > plan_a

    # -- siguiente digito ----------------------------------------------------

    @staticmethod
    def _next_digit_positions(board):
        """Copias del digito que viene DESPUES del objetivo actual. Hoy
        son un digito equivocado (pisarlas cuesta -500), pero pasan a
        ser el objetivo apenas alguien se come el actual."""
        if board.target_digit is None:
            return []
        nxt = 1 if board.target_digit == 9 else board.target_digit + 1
        return [pos for pos, v in board.digit_values.items() if v == nxt]

    @staticmethod
    def _my_dist(candidates, target):
        """Menor cantidad de movimientos mios hasta `target` (o None)."""
        best = None
        for cand in candidates.values():
            d = cand['safe_dist_map'].get(target)
            if d is not None and (best is None or d + 1 < best):
                best = d + 1
        return best

    def _opp_time_to(self, positions, bonus=0):
        """Menor cantidad de movimientos del rival hasta alguna de
        `positions` (mas `bonus`), o None si no tiene camino."""
        dists = [self._opp_dist[p] for p in positions if p in self._opp_dist]
        return min(dists) + bonus if dists else None

    def _update_race(self, board):
        """Actualiza cuantos turnos seguidos lleva el rival sin acercarse
        al digito objetivo, y con eso el bonus que se le suma a su
        distancia en la carrera (self._food_bonus)."""
        current = self._opp_time_to(board.food)
        key = (board.target_digit, tuple(sorted(board.food)))
        if key != self._race_key or current is None or self._race_last is None:
            self._race_stall = 0
        elif current >= self._race_last:
            self._race_stall = min(self._race_stall + 1, RACE_STALL_MAX)
        else:
            self._race_stall = max(self._race_stall - 1, 0)
        self._race_key = key
        self._race_last = current
        self._food_bonus = RACE_STALL_BONUS * self._race_stall

    def _via_x(self, board, candidates, positions):
        """Cuanto tardo en llegar a alguna de `positions` pasando antes
        por el 'X' mas conveniente (o None si no alcanzo ningun 'X')."""
        best = None
        for x in board.multiplier_pickups:
            d_x = self._my_dist(candidates, x)
            if d_x is None:
                continue
            total = d_x + min(board.manhattan(x, p) for p in positions)
            if best is None or total < best:
                best = total
        return best

    def _x_no_me_hace_perder(self, board, candidates, targets, opp_time=None):
        """True si despues de comer un 'X' sigo llegando a `targets` antes
        que el rival (en empate llego yo: muevo antes). Si no se pasa
        opp_time, se usa lo que tarda el rival en llegar a `targets`."""
        if opp_time is None:
            opp_time = self._opp_time_to(targets)
        via_x = self._via_x(board, candidates, targets)
        if via_x is None:
            return False
        return opp_time is None or via_x <= opp_time

    def _plan_siguiente_digito(self, board, candidates, safety_buffer, mult_step,
                               my_multiplier=None, opp_multiplier=None):
        """Devuelve la direccion para ir a esperar al lado de un digito
        que viene despues del objetivo, o None si conviene otra cosa (ir
        por un 'X', o territorio).

        - Prueba el siguiente digito del orden; si el rival igual llega
          antes (por ejemplo, porque esta pegado al objetivo), prueba el
          que viene despues, y asi hasta NEXT_DIGITS_AHEAD digitos.
        - Si puedo agarrar un 'X' y todavia llegar a ese digito antes
          que el rival, voy por el 'X' (devuelvo None). Si mi
          multiplicador esta por debajo del rival, acepto llegar hasta
          X_CATCHUP_TOLERANCE pasos "tarde" segun el calculo.
        - Si no, me acerco a las celdas vecinas del digito (no al digito
          en si: hoy pisarlo cuesta -500).
        """
        # Cuanto tarda el rival: primero tiene que comerse el objetivo
        # actual, despues ir hasta el siguiente, y asi.
        opp_time = self._opp_time_to(board.food, self._food_bonus)
        prev_positions = board.food
        behind = (my_multiplier or 1) < (opp_multiplier or 1)
        tolerance = X_CATCHUP_TOLERANCE if behind else 0
        digit = board.target_digit
        for _ in range(NEXT_DIGITS_AHEAD):
            if digit is None:
                return None
            digit = 1 if digit == 9 else digit + 1
            positions = [pos for pos, v in board.digit_values.items() if v == digit]
            if not positions:
                return None
            if opp_time is not None and prev_positions:
                opp_time += min(board.manhattan(a, b)
                                for a in prev_positions for b in positions)

            # Un 'X' vale la pena solo si despues sigo llegando primero.
            x_deadline = None if opp_time is None else opp_time + tolerance
            if mult_step is not None and self._x_no_me_hace_perder(
                    board, candidates, positions, x_deadline):
                return None

            # Celdas donde esperar: las vecinas de cada copia, sin contar
            # la celda donde ya estoy (asi me muevo entre ellas en vez de
            # alejarme).
            spots = set()
            for pos in positions:
                for _, cell in board.neighbors(pos):
                    if (cell != board.head and cell not in board.digit_values
                            and cell not in board.wall_cells):
                        spots.add(cell)
            step, my_time = self._best_target_move(candidates, spots, safety_buffer)
            # Solo sirve esperar si llego antes que el rival (+1: desde la
            # celda vecina todavia me falta el paso al digito).
            if step is not None and (opp_time is None or my_time + 1 <= opp_time):
                return step
            prev_positions = positions
        return None

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

    def _best_target_move(self, candidates, targets, safety_buffer, opp_bonus=0):
        """Busca el paso mas conveniente hacia el mas cercano de
        `targets` (el digito objetivo, o los pickups 'X', segun con que
        se lo llame). Devuelve (direccion, distancia_total) del mejor
        candidato seguro, o (None, None) si ninguno lo es -- la
        distancia se usa afuera para decidir entre ir por el digito o
        por un 'X' segun cual este mas cerca.

        v6: `targets` puede traer varias copias del digito objetivo;
        se evaluan todas y gana la mas cercana alcanzable (cualquiera
        vale lo mismo, y comer una borra las demas).

        `opp_bonus` se suma a la distancia del rival (ver _update_race)."""
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
            if opp_d is not None and opp_d + opp_bonus < my_d:
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