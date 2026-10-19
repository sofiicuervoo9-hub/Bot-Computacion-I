"""Estrategia de juego: decide que direccion tomar dado un Board."""

from board import Board

# Direccion fija cuando no hay nada que evaluar (nunca se elige al azar).
FALLBACK_DIRECTION = 'up'
# Cautela extra (en celdas) sobre el final de la partida.
ENDGAME_SAFETY_BUFFER = 3
# Ventaja de puntaje a partir de la cual se juega a encerrar al rival.
AGGRESSIVE_MARGIN = 0
# Penalidad (en pasos) para caminos que pisan un digito equivocado.
WRONG_DIGIT_STEP_PENALTY = 1000
# Turnos propios que se asumen si no llega remaining_moves.
DEFAULT_TURNS = 200
# Minimo de pasos estimados entre un digito y el siguiente.
MIN_STEPS_PER_DIGIT = 5
# Cuantos digitos hacia adelante se prueban para ir a esperar.
NEXT_DIGITS_AHEAD = 3
# Pasos de tolerancia para desviarse a un 'X' si voy atrasada en multiplicador.
X_CATCHUP_TOLERANCE = 3
# Pasos que se suman al rival por cada turno que no se acerca al objetivo.
RACE_STALL_BONUS = 2
RACE_STALL_MAX = 10
# Probabilidad estimada de ganar el digito que se espera (medida: 0,57 a 0,66).
WAIT_WIN_PROB = 0.6
# Fraccion estimada de los digitos que vienen que voy a comer yo (ritmo
# inicial).
X_DIGIT_SHARE = 1.0
# Peso (en turnos) del ritmo inicial frente al ritmo medido en la partida.
PACE_PRIOR_TURNS = 20
# Desvio maximo (en pasos) para elegir la copia que queda cerca del siguiente
# digito.
CHAIN_SLACK = 3
# Espacio minimo exigido, como multiplo del largo del cuerpo.
SAFE_SPACE_FACTOR = 1.0
# Exigir celdas a las que llego antes que el rival (evita que me encierre).
TERRITORY_SAFE = True
TERRITORY_MIN_CELLS = 5
# Nodos maximos de la busqueda de camino; si se agota, se asume que hay salida.
PATH_SEARCH_BUDGET = 2000
# Costo de un digito equivocado, de un choque repetido o de una bomba con
# puntaje <= 0.
FIXED_PENALTY = 500
# Puntos base de cada celda de comida de cola.
TAIL_FOOD_POINTS = 100
# Celdas que conserva la vibora despues de chocar.
CRASH_KEEP_CELLS = 3


class Turn:
    """Datos de un turno que comparten los pasos de la decision."""

    def __init__(
        self,
        board,
        candidates,
        safety_buffer,
        scores,
        multipliers,
        remaining_moves,
    ):
        self.board = board
        self.candidates = candidates
        self.safety_buffer = safety_buffer
        self.my_score, self.opp_score = scores
        self.my_multiplier, self.opp_multiplier = multipliers
        self.remaining_moves = remaining_moves
        self.food_step = self.food_dist = None
        self.mult_step = self.mult_dist = None


class EscapeSearch:
    """Busca un camino simple tan largo como el cuerpo, con la cola liberando
    celdas."""

    def __init__(self, board, body):
        self.board = board
        self.need = len(body)
        # La celda i del cuerpo (0 = cabeza) queda libre en len(body) - i
        # jugadas.
        self.free_at = {cell: len(body) - i for i, cell in enumerate(body)}
        self.static = (
            board.opponent_blocked | board.wall_cells | board.bomb_zone
        )
        self.start = body[0]
        self.visited = {self.start}
        self.budget = PATH_SEARCH_BUDGET

    def run(self):
        return self._extend(self.start, 0)

    def _extend(self, pos, depth):
        if depth >= self.need or self.budget <= 0:
            return True
        self.budget -= 1
        return any(
            self._try(cell, depth + 1)
            for cell in self._next_cells(pos, depth + 1)
        )

    def _try(self, cell, depth):
        self.visited.add(cell)
        found = self._extend(cell, depth)
        self.visited.discard(cell)
        return found

    def _next_cells(self, pos, step):
        cells = [
            c for _, c in self.board.neighbors(pos) if self._enterable(c, step)
        ]
        return sorted(cells, key=lambda c: self._onward(c, step))

    def _enterable(self, cell, step):
        if cell in self.static or cell in self.visited:
            return False
        return self.free_at.get(cell, 0) <= step

    def _onward(self, cell, step):
        """Salidas libres de una celda (primero las mas encerradas)."""
        return sum(
            1
            for _, c in self.board.neighbors(cell)
            if self._enterable(c, step + 1)
        )


class SnakeStrategy:
    """Decide el movimiento de cada turno; guarda el estado de una partida."""

    def __init__(
        self,
        safety_buffer=ENDGAME_SAFETY_BUFFER,
        aggressive_margin=AGGRESSIVE_MARGIN,
    ):
        self.safety_buffer_value = safety_buffer
        self.aggressive_margin = aggressive_margin
        self._opp_dist = {}
        self._race_key = None
        self._race_last = None
        self._race_stall = 0
        self._food_bonus = 0
        self._max_clean_space = float('inf')
        self._last_body = None
        self._last_score = None
        self._turns_played = 0
        self._food_eaten = 0

    def choose_direction(
        self,
        board_str,
        side,
        board_size=None,
        next_digit=None,
        my_score=None,
        opp_score=None,
        remaining_moves=None,
        my_multiplier=None,
        opp_multiplier=None,
    ):
        board = self._parse_board(board_str, side, board_size, next_digit)
        if board is None or board.head is None:
            return FALLBACK_DIRECTION
        self._track_body(board)
        self._track_pace(my_score)
        candidates = self._build_candidates(board, my_score, opp_multiplier)
        self._update_race(board)
        if not candidates:
            return self._least_bad_direction(board)
        turn = Turn(
            board,
            candidates,
            self._safety_buffer(board, my_score, opp_score, remaining_moves),
            (my_score, opp_score),
            (my_multiplier, opp_multiplier),
            remaining_moves,
        )
        self._find_targets(turn)
        return self._decide(turn)

    @staticmethod
    def _parse_board(board_str, side, board_size, next_digit):
        try:
            return Board(board_str, side, board_size, next_digit)
        except Exception:
            return None

    @staticmethod
    def _least_bad_direction(board):
        """Sin movimientos posibles todo choque cuesta lo mismo: uno fijo, no
        al azar."""
        return next(
            (d for d, _ in board.neighbors(board.head)), FALLBACK_DIRECTION
        )

    def _find_targets(self, turn):
        """Mejores pasos hacia el digito objetivo y hacia un 'X'."""
        board = turn.board
        food_cands = (
            self._open_candidates(board, turn.candidates, board.food)
            or turn.candidates
        )
        turn.food_step, turn.food_dist = self._best_target_move(
            food_cands,
            board.food,
            turn.safety_buffer,
            opp_bonus=self._food_bonus,
            shared=True,
            next_positions=self._next_digit_positions(board),
        )
        turn.mult_step, turn.mult_dist = self._best_target_move(
            turn.candidates, board.multiplier_pickups, turn.safety_buffer
        )

    def _decide(self, turn):
        """Prueba cada plan en orden de prioridad; si ninguno aplica, busca
        territorio."""
        for plan in (
            self._tail_step,
            self._target_step,
            self._wait_step,
            self._x_step,
            self._deny_step,
        ):
            step = plan(turn)
            if step is not None:
                return step
        aggressive = self._is_aggressive(turn.my_score, turn.opp_score)
        return self._best_territory_move(
            turn.board, turn.candidates, aggressive
        )

    def _tail_step(self, turn):
        step, dist = self._best_target_move(
            turn.candidates, turn.board.tail_food, turn.safety_buffer
        )
        if step is not None and self._tail_first(
            turn.board, turn.candidates, turn.food_step, turn.food_dist, dist
        ):
            return step
        return None

    def _target_step(self, turn):
        if turn.food_step is None or turn.mult_step is None:
            return turn.food_step
        return self._digit_or_x_by_value(
            turn.board,
            turn.candidates,
            turn.food_step,
            turn.food_dist,
            turn.mult_step,
            turn.mult_dist,
            turn.my_multiplier,
            turn.remaining_moves,
        )

    def _wait_step(self, turn):
        return self._plan_next_digit(
            turn.board,
            turn.candidates,
            turn.safety_buffer,
            turn.mult_step,
            turn.my_multiplier,
            turn.opp_multiplier,
            turn.remaining_moves,
        )

    @staticmethod
    def _x_step(turn):
        return turn.mult_step

    def _deny_step(self, turn):
        step, _ = self._best_target_move(
            turn.candidates, turn.board.own_shed_tail, turn.safety_buffer
        )
        return step

    # -- memoria de la partida -------------------------------------------

    def _track_body(self, board):
        """Ordena el cuerpo a partir del turno anterior (el tablero solo no
        alcanza)."""
        expected = self._expected_body(board)
        if expected is not None:
            board.set_body(expected)
        self._last_body = (
            list(board.ordered_body) if board.tail is not None else None
        )

    def _expected_body(self, board):
        prev = self._last_body
        if not prev:
            return None
        return next(
            (
                body
                for body in self._body_guesses(prev, board.head)
                if self._matches(body, board.body_cells)
            ),
            None,
        )

    @staticmethod
    def _body_guesses(prev, head):
        """Cuerpos posibles: avanzo, avanzo y crezco, no me muevo, o choco."""
        return [
            [head] + prev[:-1],
            [head] + prev,
            prev,
            prev[:CRASH_KEEP_CELLS],
        ]

    @staticmethod
    def _matches(body, cells):
        return len(body) == len(cells) and set(body) == cells

    def _track_pace(self, my_score):
        """Cuenta los turnos jugados y las veces que comi (subida de puntaje >=
        100)."""
        self._turns_played += 1
        if self._ate_since_last_turn(my_score):
            self._food_eaten += 1
        self._last_score = my_score

    def _ate_since_last_turn(self, my_score):
        if self._last_score is None or my_score is None:
            return False
        return my_score - self._last_score >= TAIL_FOOD_POINTS

    def _my_pace(self, board):
        """Digitos que como por turno: ritmo inicial mezclado con el medido."""
        prior = X_DIGIT_SHARE / self._steps_per_digit(board)
        return (self._food_eaten + PACE_PRIOR_TURNS * prior) / (
            self._turns_played + PACE_PRIOR_TURNS
        )

    # -- digito o 'X' ----------------------------------------------------

    @staticmethod
    def _my_turns_left(remaining_moves):
        """Turnos propios que quedan (remaining_moves cuenta a los dos
        jugadores)."""
        if remaining_moves is None:
            return DEFAULT_TURNS
        return (remaining_moves + 1) // 2

    @staticmethod
    def _steps_per_digit(board):
        return max(MIN_STEPS_PER_DIGIT, (board.n_rows + board.n_cols) // 4)

    @staticmethod
    def _avg_digit(board):
        digits = list(board.digit_values.values())
        return sum(digits) / len(digits) if digits else 5

    def _x_gain(self, board, remaining_moves):
        """Puntos estimados de un 'X': +50 y un escalon de multiplicador hasta
        el final."""
        turns = self._my_turns_left(remaining_moves)
        return 50 + 100 * self._avg_digit(board) * turns * self._my_pace(board)

    @staticmethod
    def _digit_value(digit, my_multiplier):
        return (digit or 1) * 100 * (my_multiplier or 1)

    @staticmethod
    def _reachable_value(value, dist, turns):
        return value if dist <= turns else 0

    def _digit_or_x_by_value(
        self,
        board,
        candidates,
        food_step,
        food_dist,
        mult_step,
        mult_dist,
        my_multiplier,
        remaining_moves,
    ):
        """Digito o 'X': primero el 'X' si igual gano el digito; si no, mas
        puntos por paso."""
        turns = self._my_turns_left(remaining_moves)
        x_value = self._reachable_value(
            self._x_gain(board, remaining_moves), mult_dist, turns
        )
        if self._take_x_first(
            board, candidates, x_value, mult_dist, food_dist, turns
        ):
            return mult_step
        digit_value = self._reachable_value(
            self._digit_value(board.target_digit, my_multiplier),
            food_dist,
            turns,
        )
        if x_value / max(1, mult_dist) > digit_value / max(1, food_dist):
            return mult_step
        return food_step

    def _take_x_first(
        self, board, candidates, x_value, mult_dist, food_dist, turns
    ):
        if x_value <= 0 or mult_dist > food_dist:
            return False
        via_x = self._via_x(board, candidates, board.food)
        if via_x is None or via_x > turns:
            return False
        return self._x_keeps_race(
            board,
            candidates,
            board.food,
            self._opp_time_to(board.food, self._food_bonus),
        )

    # -- comida de cola ----------------------------------------------------

    def _tail_first(self, board, candidates, food_step, food_dist, tail_dist):
        """True si conviene comer la cola del rival antes que el digito."""
        if food_step is None:
            return True
        if tail_dist * (board.target_digit or 1) > food_dist:
            return False
        via_tail = self._via(board, candidates, board.tail_food, board.food)
        return self._arrives_first(
            via_tail, self._opp_time_to(board.food, self._food_bonus)
        )

    # -- carrera y siguiente digito ----------------------------------------

    @staticmethod
    def _arrives_first(my_time, opp_time):
        """True si llego a tiempo (en empate llego yo: muevo antes)."""
        return my_time is not None and (
            opp_time is None or my_time <= opp_time
        )

    @staticmethod
    def _following(digit):
        return 1 if digit == 9 else digit + 1

    @staticmethod
    def _positions_of(board, digit):
        return [pos for pos, v in board.digit_values.items() if v == digit]

    @staticmethod
    def _next_digit_positions(board):
        """Copias del digito que viene despues del objetivo."""
        if board.target_digit is None:
            return []
        return SnakeStrategy._positions_of(
            board, SnakeStrategy._following(board.target_digit)
        )

    @staticmethod
    def _my_dist(candidates, target):
        """Menor cantidad de movimientos mios hasta `target` (o None)."""
        dists = [
            c['safe_dist_map'][target]
            for c in candidates.values()
            if target in c['safe_dist_map']
        ]
        return min(dists) + 1 if dists else None

    def _opp_time_to(self, positions, bonus=0):
        """Movimientos del rival hasta la mas cercana de `positions` (mas
        `bonus`)."""
        dists = [self._opp_dist[p] for p in positions if p in self._opp_dist]
        return min(dists) + bonus if dists else None

    def _update_race(self, board):
        """Cuenta los turnos que el rival no se acerca al objetivo y actualiza
        su bonus."""
        current = self._opp_time_to(board.food)
        key = (board.target_digit, tuple(sorted(board.food)))
        if key != self._race_key or current is None or self._race_last is None:
            self._race_stall = 0
        else:
            self._race_stall = self._next_stall(current)
        self._race_key = key
        self._race_last = current
        self._food_bonus = RACE_STALL_BONUS * self._race_stall

    def _next_stall(self, current):
        if current >= self._race_last:
            return min(self._race_stall + 1, RACE_STALL_MAX)
        return max(self._race_stall - 1, 0)

    def _via_x(self, board, candidates, positions):
        """Pasos hasta `positions` pasando antes por el 'X' mas conveniente."""
        return self._via(
            board, candidates, board.multiplier_pickups, positions
        )

    def _via(self, board, candidates, stops, positions):
        """Pasos hasta `positions` pasando antes por la mejor de `stops` (o
        None)."""
        if not positions:
            return None
        totals = [
            d + self._closest_gap(stop, positions)
            for stop, d in self._stop_distances(candidates, stops)
        ]
        return min(totals) if totals else None

    def _stop_distances(self, candidates, stops):
        for stop in stops:
            d = self._my_dist(candidates, stop)
            if d is not None:
                yield stop, d

    @staticmethod
    def _closest_gap(cell, positions):
        return min(Board.manhattan(cell, p) for p in positions)

    def _x_keeps_race(self, board, candidates, targets, opp_time=None):
        """True si despues de comer un 'X' sigo llegando a `targets` antes que
        el rival."""
        if opp_time is None:
            opp_time = self._opp_time_to(targets)
        return self._arrives_first(
            self._via_x(board, candidates, targets), opp_time
        )

    def _digit_stays_open(self, board, pos, digit_positions):
        """True si tras mover a `pos` la copia mas cercana se puede comer sin
        encerrarme."""
        if board.tail is None or pos in digit_positions or not digit_positions:
            return True
        new_body = [pos] + board.ordered_body[:-1]
        blocked = (
            set(new_body)
            | board.opponent_blocked
            | board.wall_cells
            | board.bomb_zone
        )
        nearest = min(digit_positions, key=lambda p: board.manhattan(pos, p))
        if nearest in blocked:
            return False
        return (
            len(board.bfs_all_distances(nearest, blocked)) >= len(new_body) + 1
        )

    def _open_candidates(self, board, candidates, positions):
        return {
            k: c
            for k, c in candidates.items()
            if self._digit_stays_open(board, c['pos'], positions)
        }

    def _upcoming_digits(self, board):
        """Copias de los digitos que siguen y cuanto tarda el rival en llegar a
        cada uno."""
        if board.target_digit is None:
            return
        opp_time = self._opp_time_to(board.food, self._food_bonus)
        prev, digit = board.food, board.target_digit
        for _ in range(NEXT_DIGITS_AHEAD):
            digit = self._following(digit)
            positions = self._positions_of(board, digit)
            if not positions:
                return
            opp_time = self._add_gap(opp_time, prev, positions)
            yield positions, opp_time
            prev = positions

    @staticmethod
    def _add_gap(opp_time, prev, positions):
        """El rival primero come el digito anterior y despues va hasta este."""
        if opp_time is None or not prev:
            return opp_time
        return opp_time + min(
            Board.manhattan(a, b) for a in prev for b in positions
        )

    def _plan_next_digit(
        self,
        board,
        candidates,
        safety_buffer,
        mult_step,
        my_multiplier=None,
        opp_multiplier=None,
        remaining_moves=None,
    ):
        """Paso para esperar al lado de un digito siguiente, o None si conviene
        otra cosa."""
        tolerance = (
            X_CATCHUP_TOLERANCE
            if self._behind(my_multiplier, opp_multiplier)
            else 0
        )
        for positions, opp_time in self._upcoming_digits(board):
            if self._prefer_x(
                board,
                candidates,
                mult_step,
                positions,
                (opp_time, tolerance),
                my_multiplier,
                remaining_moves,
            ):
                return None
            step = self._wait_next_to(
                board, candidates, positions, opp_time, safety_buffer
            )
            if step is not None:
                return step
        return None

    @staticmethod
    def _behind(my_multiplier, opp_multiplier):
        return (my_multiplier or 1) < (opp_multiplier or 1)

    def _prefer_x(
        self,
        board,
        candidates,
        mult_step,
        positions,
        race,
        my_multiplier,
        remaining_moves,
    ):
        """Mejor un 'X' si despues sigo llegando primero o si rinde mas que
        esperar."""
        if mult_step is None:
            return False
        opp_time, tolerance = race
        x_deadline = None if opp_time is None else opp_time + tolerance
        if self._x_keeps_race(board, candidates, positions, x_deadline):
            return True
        return self._x_beats_waiting(
            board, candidates, positions, my_multiplier, remaining_moves
        )

    def _x_beats_waiting(
        self, board, candidates, positions, my_multiplier, remaining_moves
    ):
        """Compara lo que rinde el 'X' con lo que rinde esperar (valor x
        probabilidad)."""
        if not any(
            self._my_dist(candidates, x) for x in board.multiplier_pickups
        ):
            return False
        wait_value = WAIT_WIN_PROB * self._digit_value(
            board.digit_values[positions[0]], my_multiplier
        )
        return self._x_gain(board, remaining_moves) >= wait_value

    def _wait_next_to(
        self, board, candidates, positions, opp_time, safety_buffer
    ):
        """Paso hacia una vecina del digito si llego antes que el rival."""
        open_cands = (
            self._open_candidates(board, candidates, positions) or candidates
        )
        step, my_time = self._best_target_move(
            open_cands, self._wait_spots(board, positions), safety_buffer
        )
        # +1: desde la vecina todavia falta el paso al digito.
        wait_time = None if step is None else my_time + 1
        return step if self._arrives_first(wait_time, opp_time) else None

    @staticmethod
    def _wait_spots(board, positions):
        blocked = (
            set(board.digit_values)
            | board.wall_cells
            | board.bomb_zone
            | {board.head}
        )
        return {
            cell
            for pos in positions
            for _, cell in board.neighbors(pos)
            if cell not in blocked
        }

    # -- seguridad y candidatos ----------------------------------------------

    @staticmethod
    def _is_winning(my_score, opp_score, margin=0):
        return (
            my_score is not None
            and opp_score is not None
            and my_score > opp_score + margin
        )

    def _safety_buffer(self, board, my_score, opp_score, remaining_moves):
        """Celdas extra exigidas sobre el final si voy ganando."""
        endgame = remaining_moves is not None and remaining_moves <= max(
            10, len(board.body_cells)
        )
        if endgame and self._is_winning(my_score, opp_score):
            return self.safety_buffer_value
        return 0

    def _is_aggressive(self, my_score, opp_score):
        """Modo cazador: voy ganando por mas del margen."""
        return self._is_winning(my_score, opp_score, self.aggressive_margin)

    @staticmethod
    def _crash_cost(board, my_score, opp_multiplier):
        """Costo de chocar: lo peor entre perder el puntaje y -500, mas la cola
        regalada."""
        score = my_score if my_score is not None else 0
        lost = max(0, len(board.body_cells) - CRASH_KEEP_CELLS)
        return max(score, FIXED_PENALTY) + lost * TAIL_FOOD_POINTS * (
            opp_multiplier or 1
        )

    @staticmethod
    def _bomb_cost(my_score):
        """Costo de explotar: el puntaje actual, o -500 si ya era <= 0."""
        score = my_score if my_score is not None else 0
        return score if score > 0 else FIXED_PENALTY

    def _build_candidates(self, board, my_score=None, opp_multiplier=None):
        """Evalua cada movimiento posible (espacio, territorio, camino,
        distancias, costos)."""
        self._opp_dist = board.bfs_all_distances(
            board.opponent_head, self._opponent_static_blocked(board)
        )
        costs = (
            self._crash_cost(board, my_score, opp_multiplier),
            self._bomb_cost(my_score),
        )
        candidates = {
            dname: self._evaluate_move(board, dname, pos, costs)
            for dname, pos in self._legal_moves(board)
        }
        self._max_clean_space = max(
            (c['clean_space'] for c in candidates.values()),
            default=float('inf'),
        )
        return candidates

    @staticmethod
    def _opponent_static_blocked(board):
        return (
            board.body_cells
            | (board.opponent_blocked - {board.opponent_head})
            | board.wall_cells
        )

    def _legal_moves(self, board):
        """Vecinos de la cabeza sin cuerpos; mi cola vale porque se corre al
        mismo tiempo."""
        for dname, pos in board.neighbors(board.head):
            if pos not in board.opponent_blocked and self._free_for_me(
                board, pos
            ):
                yield dname, pos

    @staticmethod
    def _free_for_me(board, pos):
        # Con 2 celdas la cola es el cuello: ir ahi seria darse vuelta.
        return pos not in board.body_cells or (
            pos == board.tail and len(board.body_cells) > 2
        )

    @staticmethod
    def _growing_cells(board):
        """Celdas que me hacen crecer: el objetivo, la comida de cola y los
        digitos equivocados."""
        return (
            set(board.food)
            | set(board.tail_food)
            | board.wrong_digit_positions
        )

    @staticmethod
    def _blocked_after_move(board, grows):
        body = (
            board.body_cells
            if grows or board.tail is None
            else board.body_cells - {board.tail}
        )
        return body | board.opponent_blocked | board.wall_cells

    def _evaluate_move(self, board, dname, pos, costs):
        grows = pos in self._growing_cells(board)
        static_blocked = self._blocked_after_move(board, grows)
        new_blocked = static_blocked | board.bomb_zone
        dist_map = board.bfs_all_distances(pos, new_blocked)
        # Camino limpio: sin pisar digitos equivocados.
        safe_dist_map = board.bfs_all_distances(
            pos, new_blocked | (board.wrong_digit_positions - {pos})
        )
        cand = {
            'dir': dname,
            'pos': pos,
            'space': len(dist_map),
            'dist_map': dist_map,
            'clean_space': len(safe_dist_map),
            'safe_dist_map': safe_dist_map,
            'body_len': len(board.body_cells) + int(grows),
            'territory': self._territory(dist_map),
            'opp_space': self._opp_space(board, static_blocked, pos),
            'wrong_digit': pos in board.wrong_digit_positions,
            'wall_hit': pos in board.wall_cells,
            'bomb_hit': pos in board.bomb_zone,
            'path_ok': pos in new_blocked
            or self._has_escape_path(board, pos, grows),
        }
        cand['penalty'] = self._penalty(cand, costs)
        return cand

    def _territory(self, dist_map):
        """Celdas a las que llego antes que el rival."""
        return sum(
            1
            for cell, d in dist_map.items()
            if self._opp_dist.get(cell) is None or d + 1 < self._opp_dist[cell]
        )

    @staticmethod
    def _opp_space(board, static_blocked, pos):
        """Espacio que le queda al rival si tomo este paso."""
        own = board.opponent_blocked - {board.opponent_head}
        blocked = (own | static_blocked | {pos}) - {board.opponent_head}
        return len(board.bfs_all_distances(board.opponent_head, blocked))

    @staticmethod
    def _has_escape_path(board, pos, grows):
        """True si desde `pos` hay un camino tan largo como el cuerpo (o no se
        puede saber)."""
        if board.tail is None:
            return True
        body = [pos] + (
            board.ordered_body if grows else board.ordered_body[:-1]
        )
        return EscapeSearch(board, body).run()

    @staticmethod
    def _penalty(cand, costs):
        """Costo estimado del paso; sin camino de salida equivale a chocar."""
        crash_cost, bomb_cost = costs
        return (
            FIXED_PENALTY * cand['wrong_digit']
            + crash_cost * cand['wall_hit']
            + bomb_cost * cand['bomb_hit']
            + crash_cost * (not cand['path_ok'])
        )

    def _is_safe(self, cand, safety_buffer=0):
        """True si el paso deja camino de salida y espacio total, limpio y
        propio suficiente."""
        comfy = min(
            int(SAFE_SPACE_FACTOR * cand['body_len']), self._max_clean_space
        )
        need = max(cand['body_len'] + safety_buffer, comfy)
        own = (
            cand.get('territory', cand['space'])
            if TERRITORY_SAFE
            else cand['space']
        )
        enough_own = own >= min(cand['body_len'], TERRITORY_MIN_CELLS)
        roomy = (
            cand['space'] >= need
            and cand.get('clean_space', cand['space']) >= need
        )
        return roomy and enough_own and cand.get('path_ok', True)

    # -- elegir objetivo -------------------------------------------------

    def _best_target_move(
        self,
        candidates,
        targets,
        safety_buffer,
        opp_bonus=0,
        shared=False,
        next_positions=None,
    ):
        """Mejor (direccion, distancia) hacia el objetivo mas cercano que gano.

        Devuelve (None, None) si no hay ninguno. Con shared=True (copias del
        digito) el rival gana si llega a cualquier copia.
        """
        ranked = self._rank_targets(candidates, targets)
        opp_any = self._opp_time_to(targets) if shared else None
        if shared and next_positions:
            ranked = self._chain_order(
                ranked, opp_any, opp_bonus, next_positions
            )
        return self._first_winnable(
            candidates, ranked, opp_any, opp_bonus, shared, safety_buffer
        )

    def _rank_targets(self, candidates, targets):
        """(distancia, paso, objetivo) para cada objetivo alcanzable, del mas
        cercano al mas lejano."""
        ranked = []
        for target in set(targets):
            best = self._best_candidate_for(candidates, target)
            if best is not None:
                ranked.append((best[0], best[1], target))
        ranked.sort(key=lambda item: item[0])
        return ranked

    def _best_candidate_for(self, candidates, target):
        options = [
            ((self._path_cost(c, target), c['wrong_digit']), c['dir'])
            for c in candidates.values()
        ]
        options = [opt for opt in options if opt[0][0] is not None]
        if not options:
            return None
        (total, _), step = min(options, key=lambda opt: opt[0])
        return total, step

    @staticmethod
    def _path_cost(cand, target):
        """Pasos hasta `target`; pisar digitos equivocados suma una penalidad
        grande."""
        d = cand['safe_dist_map'].get(target)
        total = (
            d + 1 if d is not None else SnakeStrategy._dirty_cost(cand, target)
        )
        if total is None:
            return None
        return total + WRONG_DIGIT_STEP_PENALTY * cand['wrong_digit']

    @staticmethod
    def _dirty_cost(cand, target):
        d = cand['dist_map'].get(target)
        return None if d is None else d + 1 + WRONG_DIGIT_STEP_PENALTY

    @staticmethod
    def _wins_race(my_d, opp_d, opp_bonus):
        return opp_d is None or opp_d + opp_bonus >= my_d

    def _chain_order(self, ranked, opp_any, opp_bonus, next_positions):
        """Entre las copias que gano, primero la que queda cerca del siguiente
        digito."""
        nearby = self._within_slack(self._winnable(ranked, opp_any, opp_bonus))
        nearby.sort(key=lambda item: self._chain_cost(item, next_positions))
        return nearby + [item for item in ranked if item not in nearby]

    def _winnable(self, ranked, opp_any, opp_bonus):
        return [
            item
            for item in ranked
            if self._wins_race(item[0], opp_any, opp_bonus)
        ]

    @staticmethod
    def _within_slack(items):
        if not items:
            return []
        limit = items[0][0] + CHAIN_SLACK
        return [item for item in items if item[0] <= limit]

    def _chain_cost(self, item, next_positions):
        gap = self._closest_gap(item[2], next_positions)
        return (item[0] + gap, item[0])

    def _first_winnable(
        self, candidates, ranked, opp_any, opp_bonus, shared, safety_buffer
    ):
        for my_d, step, target in ranked:
            opp_d = opp_any if shared else self._opp_dist.get(target)
            if self._wins_race(my_d, opp_d, opp_bonus) and self._is_safe(
                candidates[step], safety_buffer
            ):
                return step, my_d
        return None, None

    # -- sin objetivo ----------------------------------------------------

    def _best_territory_move(self, board, candidates, aggressive=False):
        """El paso de menor costo con mas territorio (o que mas achica al
        rival)."""
        pool = (
            self._safe_moves(candidates)
            or self._roomy_moves(candidates)
            or list(candidates.values())
        )
        return min(
            pool, key=lambda c: self._territory_rank(board, c, aggressive)
        )['dir']

    def _safe_moves(self, candidates):
        return [c for c in candidates.values() if self._is_safe(c)]

    @staticmethod
    def _roomy_moves(candidates):
        return [c for c in candidates.values() if c['space'] >= c['body_len']]

    def _territory_rank(self, board, cand, aggressive):
        tail = board.tail if board.tail is not None else board.head
        dist_to_opp = (
            board.manhattan(cand['pos'], board.opponent_head)
            if board.opponent_head
            else 0
        )
        dist_to_tail = board.manhattan(cand['pos'], tail)
        cost = self._move_cost(cand)
        if aggressive:
            return (
                cost,
                cand['opp_space'],
                -cand['territory'],
                -dist_to_opp,
                dist_to_tail,
            )
        return (cost, -cand['territory'], -dist_to_opp, dist_to_tail)

    @staticmethod
    def _move_cost(cand):
        costly = (
            cand['wrong_digit']
            or cand.get('wall_hit', False)
            or cand.get('bomb_hit', False)
        )
        return cand.get('penalty', FIXED_PENALTY if costly else 0)


# Wrapper funcional para el codigo que llama choose_direction(board, side,
# ...).
_default_strategy = SnakeStrategy()


def choose_direction(
    board,
    side,
    my_score=None,
    opp_score=None,
    remaining_moves=None,
    board_size=None,
    next_digit=None,
    my_multiplier=None,
    opp_multiplier=None,
):
    return _default_strategy.choose_direction(
        board,
        side,
        board_size,
        next_digit,
        my_score,
        opp_score,
        remaining_moves,
        my_multiplier,
        opp_multiplier,
    )
