"""Modelo del tablero de Snake.

El tamano del tablero varia entre partidas y el servidor ahora informa
las dimensiones reales en cada turno (campo ``board_size``, formato
"filas x columnas", agregado el 2/9/2026). La clase Board usa ese dato
como fuente de verdad cuando esta disponible y, si no llega (partidas
viejas / testing local), lo deriva del propio string recibido -- en
ningun lado del codigo se asume un ancho o alto fijo.

Desde el 9/9/2026 (v3) la comida deja de ser '*' y pasa a ser cinco
digitos (1-9, sin el 0) siempre presentes en tablero, formando una
racha ascendente ciclica (por ej. 7,8,9,1,2). Hay que comerlos en ese
orden. El servidor manda el digito correcto directo en el campo
``next_digit`` de turn_data -- esa es la fuente de verdad. Si no
llega (partidas viejas, testing local), se infiere del propio tablero:
es el unico digito cuyo predecesor ciclico NO esta en tablero (eso
marca el inicio de la racha). Comer el digito correcto sale digito x
100 puntos; comer cualquier otro sale -500 (no mata, pero conviene
evitarlo).
"""

from collections import deque

DIRECTIONS = {
    'up':    (-1, 0),   # fila -1, columna igual  -> subis una fila
    'down':  (1, 0),    # fila +1, columna igual  -> bajas una fila
    'left':  (0, -1),   # fila igual, columna -1  -> vas una columna a la izquierda
    'right': (0, 1),    # fila igual, columna +1  -> vas una columna a la derecha
}


class Board:
    """Parsea y representa el estado del tablero en un turno dado.

    Se reconstruye desde cero en cada turno (no guarda estado entre
    turnos), por eso soporta sin problema que el tablero cambie de
    tamano de una partida a otra, o incluso de un turno a otro.
    """

    def __init__(self, board_str, side, board_size=None, next_digit=None):
        self.side = side
        self.my_body_char = side.lower()
        self.opponent = 'B' if side == 'A' else 'A'
        self.opponent_body = self.opponent.lower()

        self.grid = self._parse_grid(board_str)
        self.n_rows, self.n_cols = self._resolve_dimensions(board_size)

        self.head = None
        self.opponent_head = None
        self.food = []
        self.digit_values = {}
        self.opponent_blocked = set()
        self.body_cells = set()
        self._scan_cells()

        # v3: si hay digitos en tablero, el unico objetivo valido es el
        # digito "correcto" (el resto son trampas de -500, no comida).
        # Preferimos el next_digit que manda el servidor; si no vino,
        # lo inferimos del tablero como respaldo.
        self.target_digit = None
        self.target_digit_pos = None
        self.wrong_digit_positions = set()
        if self.digit_values:
            if next_digit is not None:
                try:
                    self.target_digit = int(next_digit)
                except (TypeError, ValueError):
                    self.target_digit = None
            if self.target_digit is None:
                self.target_digit = self._infer_target_digit()
            self.target_digit_pos = self._locate_digit(self.target_digit)
            if self.target_digit_pos is not None:
                self.food = [self.target_digit_pos]
            self.wrong_digit_positions = set(self.digit_values) - (
                {self.target_digit_pos} if self.target_digit_pos is not None else set()
            )

        self.ordered_body = self._trace_body()
        self.tail = (
            self.ordered_body[-1]
            if self.ordered_body and len(self.ordered_body) == len(self.body_cells)
            else None
        )

    # -- construccion --------------------------------------------------

    @staticmethod
    def _parse_grid(board_str):
        rows = [line[1:-1] for line in board_str.split('\n') if line.startswith('|')]
        return [list(row) for row in rows]

    def _resolve_dimensions(self, board_size):
        # Fuente de verdad: el board_size que manda el servidor ("RxC").
        if board_size:
            try:
                rows_str, cols_str = str(board_size).lower().split('x')
                return int(rows_str), int(cols_str)
            except (ValueError, AttributeError):
                pass
        # Fallback: lo derivamos del string (compatibilidad si algun
        # turno no trae board_size). min() evita asumir filas parejas.
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
                if ch is None:
                    continue
                if ch == '*':
                    self.food.append((r, c))
                elif ch.isdigit() and ch != '0':
                    self.digit_values[(r, c)] = int(ch)
                elif ch == self.side:
                    self.head = (r, c)
                    self.body_cells.add((r, c))
                elif ch == self.my_body_char:
                    self.body_cells.add((r, c))
                elif ch == self.opponent:
                    self.opponent_head = (r, c)
                    self.opponent_blocked.add((r, c))
                elif ch == self.opponent_body:
                    self.opponent_blocked.add((r, c))

    @staticmethod
    def _cyclic_prev(digit):
        # Orden ciclico 1..9 sin el 0: el predecesor de 1 es 9.
        return 9 if digit == 1 else digit - 1

    def _infer_target_digit(self):
        # Respaldo si no llego next_digit: el digito correcto es el que
        # arranca la racha, el unico cuyo predecesor ciclico no esta
        # entre los digitos en tablero.
        present = set(self.digit_values.values())
        return next(
            (d for d in present if self._cyclic_prev(d) not in present),
            min(present) if present else None,  # fallback defensivo
        )

    def _locate_digit(self, value):
        if value is None:
            return None
        for pos, v in self.digit_values.items():
            if v == value:
                return pos
        return None

    def _trace_body(self):
        # Recorre el cuerpo desde la cabeza para saber cual celda es la
        # cola (la que se libera el proximo turno si no comemos).
        if self.head is None:
            return []
        body = [self.head]
        visited = {self.head}
        current = self.head
        while True:
            nxt = None
            for _, npos in self.neighbors(current):
                if npos not in visited and self._char_at(npos) == self.my_body_char:
                    nxt = npos
                    break
            if nxt is None:
                break
            body.append(nxt)
            visited.add(nxt)
            current = nxt
        return body

    # -- consultas geometricas -------------------------------------------

    def neighbors(self, pos):
        """Vecinos validos (dentro del tablero actual) de una celda."""
        r, c = pos
        for dname, (dr, dc) in DIRECTIONS.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.n_rows and 0 <= nc < self.n_cols:
                yield dname, (nr, nc)

    @staticmethod
    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def bfs_all_distances(self, start, blocked):
        """Distancia minima desde start a cada celda alcanzable, evitando blocked."""
        if start is None or start in blocked:
            return {}
        dist = {start: 0}
        queue = deque([start])
        while queue:
            pos = queue.popleft()
            d = dist[pos]
            for _, npos in self.neighbors(pos):
                if npos not in blocked and npos not in dist:
                    dist[npos] = d + 1
                    queue.append(npos)
        return dist
