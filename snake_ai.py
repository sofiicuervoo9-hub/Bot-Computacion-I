from collections import deque
from random import choice


DIRECTIONS = {
    'up': (-1, 0),
    'down': (1, 0),
    'left': (0, -1),
    'right': (0, 1),
}

# When we're already ahead on score and few moves remain, require this much
# extra safety margin (free space beyond our own length) before we'll still
# detour for food — no point risking a crash to pad a lead we already have.
ENDGAME_SAFETY_BUFFER = 3


def parse_board(board, side):
    """Return (grid, n_rows, n_cols, head, food, opponent_blocked, opponent_head, my_body_char)."""
    rows = [line[1:-1] for line in board.split('\n') if line.startswith('|')]
    grid = [list(row) for row in rows]
    n_rows = len(grid)
    # Use the shortest row's length rather than assuming every row is the
    # same width — avoids IndexError if the board is ever ragged.
    n_cols = min((len(row) for row in grid), default=0)

    my_body_char = side.lower()
    opponent = 'B' if side == 'A' else 'A'
    opponent_body = opponent.lower()

    head = None
    food = []
    opponent_head = None
    opponent_blocked = set()
    for r in range(n_rows):
        for c in range(n_cols):
            ch = grid[r][c]
            if ch == '*':
                food.append((r, c))
            elif ch == side:
                head = (r, c)
            elif ch == opponent:
                opponent_head = (r, c)
                opponent_blocked.add((r, c))
            elif ch == opponent_body:
                opponent_blocked.add((r, c))
    return grid, n_rows, n_cols, head, food, opponent_blocked, opponent_head, my_body_char


def trace_body(head, my_body_char, grid, n_rows, n_cols):
    """Walk from the head through connected body cells to get an ordered
    [head, ..., tail] list — needed to know which cell frees up next turn."""
    if head is None:
        return []
    body = [head]
    visited = {head}
    current = head
    while True:
        nxt = None
        for _, npos in neighbors(current, n_rows, n_cols):
            nr, nc = npos
            if npos not in visited and grid[nr][nc] == my_body_char:
                nxt = npos
                break
        if nxt is None:
            break
        body.append(nxt)
        visited.add(nxt)
        current = nxt
    return body


def neighbors(pos, n_rows, n_cols):
    r, c = pos
    for dname, (dr, dc) in DIRECTIONS.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < n_rows and 0 <= nc < n_cols:
            yield dname, (nr, nc)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def bfs_all_distances(start, blocked, n_rows, n_cols):
    """Distance from `start` to every reachable cell, avoiding `blocked`."""
    if start is None or start in blocked:
        return {}
    dist = {start: 0}
    queue = deque([start])
    while queue:
        pos = queue.popleft()
        d = dist[pos]
        for _, npos in neighbors(pos, n_rows, n_cols):
            if npos not in blocked and npos not in dist:
                dist[npos] = d + 1
                queue.append(npos)
    return dist


def choose_direction(board, side, my_score=None, opp_score=None, remaining_moves=None):
    grid, n_rows, n_cols, head, food, opponent_blocked, opponent_head, my_body_char = \
        parse_board(board, side)
    if head is None:
        return choice(list(DIRECTIONS.keys()))

    # Every cell currently occupied by our own snake, found by direct scan —
    # NOT by walking the body from the head. That walk can miss cells: if the
    # head sits next to both the real next segment AND a short dead-end
    # branch of its own body (a coiled snake), it can wander off down the
    # wrong branch and never visit the other one, silently leaving real body
    # cells out of the blocked set. A direct scan can't have that gap.
    body_cells = {
        (r, c)
        for r in range(n_rows) for c in range(n_cols)
        if grid[r][c] == side or grid[r][c] == my_body_char
    }
    body_len = len(body_cells)

    # Best-effort ordered walk, used only to guess which cell is the tail
    # (the one that vacates next turn if we don't eat). Only trust it when
    # it actually accounted for every body cell — otherwise we don't know
    # the true tail, so play it safe and don't free up anything.
    ordered_body = trace_body(head, my_body_char, grid, n_rows, n_cols)
    tail = ordered_body[-1] if len(ordered_body) == body_len else None

    food_set = set(food)

    # The opponent's reach doesn't depend on which way we move, so compute it
    # once: distance (in *their* move count) from their head to every cell
    # they could reach, treating their own body and ours as walls.
    opponent_static_blocked = body_cells | (opponent_blocked - {opponent_head})
    opp_dist = bfs_all_distances(opponent_head, opponent_static_blocked, n_rows, n_cols)

    candidates = {}
    for dname, pos in neighbors(head, n_rows, n_cols):
        if pos in opponent_blocked or pos in body_cells:
            continue
        ate = pos in food_set
        # Simulate the move: the head advances, and unless we ate, the tail
        # cell is vacated this same turn — so it should NOT count as blocked
        # when judging how much room we'll have afterwards (only if we
        # actually know which cell the tail is). If we ate, the snake is now
        # one segment LONGER (tail stays put), so the safety margin must be
        # measured against that grown length.
        if ate:
            new_body_len = body_len + 1
            new_blocked = body_cells | opponent_blocked
        else:
            new_body_len = body_len
            new_blocked = (body_cells - {tail} if tail is not None else body_cells) | opponent_blocked
        # Every cell reachable from this candidate position, in *our* move
        # count from right now (the candidate move itself is move #1, hence
        # the +1 below when comparing against the opponent's move count).
        # This one BFS per direction is reused below both for the safety
        # check and for food targeting, instead of running extra full-board
        # searches for each.
        dist_map = bfs_all_distances(pos, new_blocked, n_rows, n_cols)
        space = len(dist_map)
        # Territory: how many reachable cells we'd get to strictly before
        # the opponent could — this is what lets the bot actively cut the
        # opponent off / claim ground instead of just avoiding self-traps.
        territory = sum(
            1 for cell, d in dist_map.items()
            if opp_dist.get(cell) is None or (d + 1) < opp_dist[cell]
        )
        candidates[dname] = {
            'dir': dname, 'pos': pos, 'space': space, 'dist_map': dist_map,
            'body_len': new_body_len, 'territory': territory,
        }

    if not candidates:
        # No safe move: we're going to crash regardless, just pick something.
        return choice(list(DIRECTIONS.keys()))

    # If we're already ahead on score and the match is close to ending,
    # require extra breathing room before detouring for more food — a crash
    # now would flip a win into a loss for no real upside.
    safety_buffer = 0
    if my_score is not None and opp_score is not None and my_score > opp_score:
        if remaining_moves is not None and remaining_moves <= max(10, body_len):
            safety_buffer = ENDGAME_SAFETY_BUFFER

    # For each food, find the best first move toward it by checking which
    # candidate's own BFS gets there in the fewest total moves — reusing the
    # searches above instead of running a fresh one per food item.
    food_targets = []
    for target in food_set:
        best_step, best_dist = None, None
        for cand in candidates.values():
            d = cand['dist_map'].get(target)
            if d is None:
                continue
            total = d + 1
            if best_dist is None or total < best_dist:
                best_dist, best_step = total, cand['dir']
        if best_step is not None:
            food_targets.append((best_dist, best_step, target))
    food_targets.sort(key=lambda t: t[0])

    # Try every reachable food, nearest first. Skip food the opponent is
    # clearly closer to (not worth the detour) and any move that wouldn't
    # leave us enough room to keep moving afterwards.
    for my_d, step, target in food_targets:
        opp_d = opp_dist.get(target)
        if opp_d is not None and opp_d < my_d:
            continue
        cand = candidates[step]
        if cand['space'] >= cand['body_len'] + safety_buffer:
            return step

    # No food worth going for right now: play for position. Prefer moves
    # that don't shrink us into a pocket smaller than our own body when an
    # alternative exists, then rank by territory (offense: claim/contest as
    # much of the board as possible), then by distance from the opponent's
    # head, then by staying close to our own tail (safe to loop forever).
    tail_for_rank = tail if tail is not None else head
    safe = [c for c in candidates.values() if c['space'] >= c['body_len']]
    pool = safe or list(candidates.values())

    def rank(cand):
        dist_to_opp = manhattan(cand['pos'], opponent_head) if opponent_head else 0
        dist_to_tail = manhattan(cand['pos'], tail_for_rank)
        return (-cand['territory'], -dist_to_opp, dist_to_tail)

    best = min(pool, key=rank)
    return best['dir']
