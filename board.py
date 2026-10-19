"""Modelo del tablero de Snake: parsea el string del servidor en cada turno."""

from collections import deque

DIRECTIONS = {
    'up': (-1, 0),
    'down': (1, 0),
    'left': (0, -1),
    'right': (0, 1),
}

# v7: comida de cola; cada letra solo la puede comer esa vibora.
TAIL_FOOD = {'A': 'Ⓐ', 'B': 'Ⓑ'}

# v8: bombas de proximidad y su radio de explosion (distancia de Chebyshev).
BIG_BOMB = '\U0001f4a3'
SMALL_BOMB = '\U0001f9e8'
BOMB_RADIUS = {BIG_BOMB: 2, SMALL_BOMB: 1}

# Selector de variacion de emoji: no ocupa una celda propia.
_VARIATION_SELECTOR = '️'

# Simbolos que no dependen del lado que juego.
_FIXED_KINDS = {
    '*': 'food',
    'X': 'pickup',
    '#': 'wall',
    BIG_BOMB: 'bomb',
    SMALL_BOMB: 'bomb',
}


class Board:
    """Estado del tablero en un turno; se reconstruye desde cero cada turno."""

    def __init__(self, board_str, side, board_size=None, next_digit=None):
        self.side = side
        self.my_body_char = side.lower()
        self.opponent = 'B' if side == 'A' else 'A'
        self.opponent_body = self.opponent.lower()
        self._kinds = self._build_kinds()

        self.grid = self._parse_grid(board_str)
        self.n_rows, self.n_cols = self._resolve_dimensions(board_size)

        self.head = None
        self.opponent_head = None
        self.food = []
        self.digit_values = {}
        self.multiplier_pickups = []
        self.wall_cells = set()
        self.opponent_blocked = set()
        self.body_cells = set()
        self.tail_food = []  # comida de cola que puedo comer yo
        self.own_shed_tail = []  # mi cola perdida (la come el rival)
        self.bombs = []  # [(pos, radio)]
        self._scan_cells()
        self.bomb_zone = self._compute_bomb_zone()

        self.target_digit = None
        self.target_digit_pos = None
        self.target_digit_positions = []
        self.wrong_digit_positions = set()
        if self.digit_values:
            self._resolve_target_digit(next_digit)

        self.ordered_body = []
        self.tail = None
        self.set_body(self._trace_body())

    # -- construccion --------------------------------------------------

    def _build_kinds(self):
        """Que es cada simbolo del tablero visto desde mi lado."""
        kinds = dict(_FIXED_KINDS)
        kinds.update(
            {
                self.side: 'head',
                self.my_body_char: 'body',
                self.opponent: 'opp_head',
                self.opponent_body: 'opp_body',
                TAIL_FOOD.get(self.side): 'tail_food',
                TAIL_FOOD.get(self.opponent): 'shed_tail',
            }
        )
        return kinds

    @staticmethod
    def _parse_grid(board_str):
        board_str = board_str.replace(_VARIATION_SELECTOR, '')
        rows = [
            line[1:-1]
            for line in board_str.split('\n')
            if line.startswith('|')
        ]
        return [list(row) for row in rows]

    def _resolve_dimensions(self, board_size):
        """Usa board_size ("RxC") si es valido; si no, mide el tablero."""
        if board_size:
            try:
                rows_str, cols_str = str(board_size).lower().split('x')
                return int(rows_str), int(cols_str)
            except (ValueError, AttributeError):
                pass
        n_rows = len(self.grid)
        n_cols = min((len(row) for row in self.grid), default=0)
        return n_rows, n_cols

    def _char_at(self, pos):
        r, c = pos
        if r >= len(self.grid):
            return None
        row = self.grid[r]
        return row[c] if c < len(row) else None

    def _scan_cells(self):
        for r in range(self.n_rows):
            for c in range(self.n_cols):
                ch = self._char_at((r, c))
                if ch is not None:
                    self._register_cell((r, c), ch)

    def _register_cell(self, pos, ch):
        if ch.isdigit() and ch != '0':
            self.digit_values[pos] = int(ch)
            return
        kind = self._kinds.get(ch)
        if kind is not None:
            getattr(self, '_add_' + kind)(pos, ch)

    def _add_food(self, pos, ch):
        self.food.append(pos)

    def _add_pickup(self, pos, ch):
        self.multiplier_pickups.append(pos)

    def _add_wall(self, pos, ch):
        self.wall_cells.add(pos)

    def _add_bomb(self, pos, ch):
        self.bombs.append((pos, BOMB_RADIUS[ch]))

    def _add_head(self, pos, ch):
        self.head = pos
        self.body_cells.add(pos)

    def _add_body(self, pos, ch):
        self.body_cells.add(pos)

    def _add_opp_head(self, pos, ch):
        self.opponent_head = pos
        self.opponent_blocked.add(pos)

    def _add_opp_body(self, pos, ch):
        self.opponent_blocked.add(pos)

    def _add_tail_food(self, pos, ch):
        self.tail_food.append(pos)

    def _add_shed_tail(self, pos, ch):
        self.own_shed_tail.append(pos)

    def _compute_bomb_zone(self):
        """Celdas donde terminar con la cabeza hace explotar una bomba."""
        zone = set()
        for (br, bc), radius in self.bombs:
            zone |= self._square(br, bc, radius)
        return zone

    def _square(self, row, col, radius):
        """Cuadrado de lado 2*radio+1 alrededor de (row, col), recortado al
        tablero."""
        rows = range(max(0, row - radius), min(self.n_rows, row + radius + 1))
        cols = range(max(0, col - radius), min(self.n_cols, col + radius + 1))
        return {(r, c) for r in rows for c in cols}

    def _resolve_target_digit(self, next_digit):
        """Fija el digito objetivo (inferido, o next_digit en los tests) y sus
        copias."""
        self.target_digit = self._parse_digit(next_digit)
        if self.target_digit is None:
            self.target_digit = self._infer_target_digit()
        self.target_digit_positions = self._locate_all_digits(
            self.target_digit
        )
        self.target_digit_pos = self._locate_digit(self.target_digit)
        self.food = list(self.target_digit_positions)
        self.wrong_digit_positions = set(self.digit_values) - set(
            self.target_digit_positions
        )

    @staticmethod
    def _parse_digit(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cyclic_prev(digit):
        return 9 if digit == 1 else digit - 1

    def _infer_target_digit(self):
        """El objetivo es el unico digito cuyo predecesor ciclico no esta en
        tablero."""
        present = set(self.digit_values.values())
        return next(
            (d for d in present if self._cyclic_prev(d) not in present),
            min(present) if present else None,
        )

    def _locate_digit(self, value):
        """Primera copia de `value`."""
        positions = self._locate_all_digits(value)
        return positions[0] if positions else None

    def _locate_all_digits(self, value):
        """Todas las copias de `value`, en orden de lectura."""
        if value is None:
            return []
        return [pos for pos, v in self.digit_values.items() if v == value]

    # -- cuerpo --------------------------------------------------------

    def set_body(self, body):
        """Fija el cuerpo ordenado (cabeza primero); la cola solo si esta
        completo."""
        self.ordered_body = list(body)
        complete = bool(body) and len(body) == len(self.body_cells)
        self.tail = body[-1] if complete else None

    def _trace_body(self):
        """Recorre el cuerpo desde la cabeza hasta la cola."""
        if self.head is None:
            return []
        body = [self.head]
        nxt = self._next_body_cell(self.head, set(body))
        while nxt is not None:
            body.append(nxt)
            nxt = self._next_body_cell(nxt, set(body))
        return body

    def _next_body_cell(self, pos, visited):
        for _, npos in self.neighbors(pos):
            if (
                npos not in visited
                and self._char_at(npos) == self.my_body_char
            ):
                return npos
        return None

    # -- consultas geometricas -------------------------------------------

    def neighbors(self, pos):
        """Vecinos de una celda dentro del tablero."""
        r, c = pos
        for dname, (dr, dc) in DIRECTIONS.items():
            if self.inside((r + dr, c + dc)):
                yield dname, (r + dr, c + dc)

    def inside(self, pos):
        return 0 <= pos[0] < self.n_rows and 0 <= pos[1] < self.n_cols

    @staticmethod
    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def chebyshev(a, b):
        """Distancia con diagonal = 1 (la que usan las bombas)."""
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def bfs_all_distances(self, start, blocked):
        """Distancia minima desde start a cada celda alcanzable, evitando
        blocked."""
        if start is None or start in blocked:
            return {}
        dist = {start: 0}
        queue = deque([start])
        while queue:
            pos = queue.popleft()
            for npos in self._unseen_neighbors(pos, blocked, dist):
                dist[npos] = dist[pos] + 1
                queue.append(npos)
        return dist

    def _unseen_neighbors(self, pos, blocked, seen):
        return [
            npos
            for _, npos in self.neighbors(pos)
            if npos not in blocked and npos not in seen
        ]
