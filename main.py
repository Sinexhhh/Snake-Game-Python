import random
import sqlite3
import time
from pathlib import Path

import pygame

CELL = 24
GRID_W, GRID_H = 26, 20
WIDTH, HEIGHT = GRID_W * CELL, GRID_H * CELL + 100
DB = Path(__file__).with_name('snake_scores.db')
BG = (13, 19, 30)
BOARD = (22, 32, 45)
TEXT = (230, 240, 245)
GREEN = (67, 225, 128)
RED = (255, 98, 110)
GOLD = (255, 205, 75)
BLUE = (94, 174, 255)
PURPLE = (184, 115, 255)
DIFFICULTIES = {'1': ('Easy', 7), '2': ('Medium', 11), '3': ('Hard', 15)}
POWER_TYPES = ('shield', 'double', 'slow')


def db_connect():
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)')
    con.execute('''CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL,
        score INTEGER NOT NULL, difficulty TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL, played_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(player_id) REFERENCES players(id))''')
    con.commit()
    return con


def save_score(name, score, difficulty, duration):
    with db_connect() as con:
        con.execute('INSERT OR IGNORE INTO players(name) VALUES (?)', (name,))
        player_id = con.execute('SELECT id FROM players WHERE name=?', (name,)).fetchone()[0]
        con.execute('INSERT INTO scores(player_id, score, difficulty, duration_seconds) VALUES (?, ?, ?, ?)',
                    (player_id, score, difficulty, duration))


def top_scores():
    with db_connect() as con:
        return con.execute('''SELECT p.name, s.score, s.difficulty FROM scores s
                              JOIN players p ON p.id=s.player_id
                              ORDER BY s.score DESC, s.duration_seconds ASC LIMIT 5''').fetchall()


def free_cell(occupied):
    cells = [(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in occupied]
    return random.choice(cells) if cells else None


def new_game(level):
    snake = [(GRID_W // 2 - i, GRID_H // 2) for i in range(4)]
    occupied = set(snake)
    obstacles = set()
    for _ in range({'Easy': 4, 'Medium': 8, 'Hard': 12}[level]):
        spot = free_cell(occupied | obstacles)
        if spot is not None and abs(spot[0] - snake[0][0]) > 3:
            obstacles.add(spot)
    return dict(snake=snake, direction=(1, 0), pending=(1, 0), food=free_cell(occupied | obstacles),
                obstacles=obstacles, power=None, power_until=0, active=None, active_until=0,
                score=0, started=time.monotonic(), elapsed=0, last_step=time.monotonic(), saved=False)


def label(screen, font, message, x, y, color=TEXT):
    screen.blit(font.render(str(message), True, color), (x, y))


def square(screen, cell, color, inset=2):
    x, y = cell
    pygame.draw.rect(screen, color, (x * CELL + inset, y * CELL + 100 + inset,
                                    CELL - 2 * inset, CELL - 2 * inset), border_radius=5)


def main():
    pygame.init()
    db_connect().close()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Snake: Power-Up Arena')
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('consolas', 21, bold=True)
    small = pygame.font.SysFont('consolas', 16)
    big = pygame.font.SysFont('consolas', 36, bold=True)
    state, name, level, game = 'menu', '', 'Medium', None
    paused_at = 0
    running = True
    while running:
        now = time.monotonic()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if state == 'menu':
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        level = DIFFICULTIES[event.unicode][0]
                    elif event.key == pygame.K_BACKSPACE:
                        name = name[:-1]
                    elif event.key == pygame.K_RETURN:
                        name = name.strip() or 'Player'
                        game = new_game(level)
                        state = 'playing'
                    elif event.unicode.isprintable() and len(name) < 18 and event.key != pygame.K_ESCAPE:
                        name += event.unicode
                elif state in ('playing', 'paused'):
                    if event.key == pygame.K_ESCAPE:
                        state = 'menu'
                    elif event.key == pygame.K_p:
                        if state == 'playing':
                            paused_at = now
                            state = 'paused'
                        else:
                            delta = now - paused_at
                            game['started'] += delta
                            game['last_step'] += delta
                            if game['active']:
                                game['active_until'] += delta
                            if game['power']:
                                game['power_until'] += delta
                            state = 'playing'
                    elif state == 'playing':
                        keys = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
                                pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
                                pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
                                pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}
                        candidate = keys.get(event.key)
                        if candidate and candidate != (-game['direction'][0], -game['direction'][1]):
                            game['pending'] = candidate
                elif state == 'over':
                    if event.key == pygame.K_r:
                        game = new_game(level)
                        state = 'playing'
                    elif event.key == pygame.K_ESCAPE:
                        state = 'menu'
        screen.fill(BG)
        if state == 'menu':
            label(screen, big, 'SNAKE POWER-UP ARENA', 68, 105, GREEN)
            label(screen, font, 'Player name: ' + name + '_', 95, 200)
            label(screen, font, 'Difficulty: ' + level, 95, 250, GOLD)
            label(screen, small, 'Press 1 Easy / 2 Medium / 3 Hard', 95, 290)
            label(screen, small, 'Enter: Start   |   WASD/Arrows: Move', 95, 340)
            label(screen, small, 'P: Pause  |  Esc: Menu', 95, 368)
            label(screen, font, 'TOP SCORES', 95, 430, BLUE)
            for i, (player, score, difficulty) in enumerate(top_scores()):
                label(screen, small, f'{i + 1}. {player[:14]:14} {score:4}  {difficulty}', 95, 466 + i * 25)
        else:
            if state == 'playing':
                if game['active'] and now >= game['active_until']:
                    game['active'] = None
                if game['power'] and now >= game['power_until']:
                    game['power'] = None
                if game['power'] is None and random.random() < 0.004:
                    spot = free_cell(set(game['snake']) | game['obstacles'] | {game['food']})
                    if spot:
                        game['power'] = (spot, random.choice(POWER_TYPES))
                        game['power_until'] = now + 8
                speed = next(v for n, v in DIFFICULTIES.values() if n == level)
                if game['active'] == 'slow':
                    speed = max(4, speed // 2)
                if now - game['last_step'] >= 1 / speed:
                    game['last_step'] = now
                    game['direction'] = game['pending']
                    hx, hy = game['snake'][0]
                    dx, dy = game['direction']
                    head = (hx + dx, hy + dy)
                    eats = head == game['food']
                    body = game['snake'] if eats else game['snake'][:-1]
                    hit = (not 0 <= head[0] < GRID_W or not 0 <= head[1] < GRID_H or
                           head in body or head in game['obstacles'])
                    if hit and game['active'] == 'shield':
                        game['active'] = None
                        hit = False
                        # Shield prevents one collision by leaving the snake in place.
                        game['pending'] = (-dy, dx)
                        game['direction'] = game['pending']
                    elif hit:
                        game['elapsed'] = int(now - game['started'])
                        state = 'over'
                    else:
                        game['snake'].insert(0, head)
                        if eats:
                            game['score'] += 20 if game['active'] == 'double' else 10
                            game['food'] = free_cell(set(game['snake']) | game['obstacles'] |
                                                     ({game['power'][0]} if game['power'] else set()))
                            if game['food'] is None:
                                game['elapsed'] = int(now - game['started'])
                                state = 'over'
                        else:
                            game['snake'].pop()
                        if game['power'] and head == game['power'][0]:
                            game['active'] = game['power'][1]
                            game['active_until'] = now + 7
                            game['power'] = None
            if state == 'over' and not game['saved']:
                save_score(name, game['score'], level, game['elapsed'])
                game['saved'] = True
            label(screen, font, f'{name[:12]}  SCORE: {game["score"]}  {level}', 15, 15, GREEN)
            power_label = game['active'].upper() if game['active'] else 'NONE'
            label(screen, small, f'POWER: {power_label}    P: Pause   Esc: Menu', 15, 53, GOLD)
            pygame.draw.rect(screen, BOARD, (0, 100, GRID_W * CELL, GRID_H * CELL))
            for x in range(0, WIDTH, CELL):
                pygame.draw.line(screen, (29, 42, 54), (x, 100), (x, 100 + GRID_H * CELL))
            for y in range(100, 100 + GRID_H * CELL, CELL):
                pygame.draw.line(screen, (29, 42, 54), (0, y), (WIDTH, y))
            for cell in game['obstacles']:
                square(screen, cell, (100, 113, 130))
            if game['food']:
                square(screen, game['food'], RED, 3)
            if game['power']:
                square(screen, game['power'][0], {'shield': BLUE, 'double': GOLD, 'slow': PURPLE}[game['power'][1]])
            for i, cell in enumerate(game['snake']):
                square(screen, cell, GREEN if i == 0 else (43, 171, 102))
            if state in ('paused', 'over'):
                overlay = pygame.Surface((WIDTH, GRID_H * CELL), pygame.SRCALPHA)
                overlay.fill((5, 8, 15, 195))
                screen.blit(overlay, (0, 100))
                label(screen, big, 'PAUSED' if state == 'paused' else 'GAME OVER', 190, 260, GOLD)
                label(screen, font, 'P: Resume' if state == 'paused' else 'R: Restart   Esc: Menu', 150, 320)
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == '__main__':
    main()
