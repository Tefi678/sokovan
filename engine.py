import pygame
import time
from constants import *
from levels import LEVEL_DATA


class SokobanEngine:
    def __init__(self):
        self.current_level_idx = 1
        self.font = pygame.font.SysFont("Verdana", 22, bold=True)
        self.big_font = pygame.font.SysFont("Verdana", 50, bold=True)
        self.history = []
        self.hole_open_until = {}
        self.load_level(self.current_level_idx)

    def load_level(self, idx):
        layout = LEVEL_DATA.get(idx, LEVEL_DATA[1])
        self.grid = [list(row) for row in layout]
        self.rows = len(self.grid)
        self.cols = len(self.grid[0])

        self.player_pos = []
        self.boxes = []
        self.targets = []
        self.points_coords = []
        self.points_collected = []

        for r in range(self.rows):
            for c in range(self.cols):
                char = self.grid[r][c]
                if char == 'P':
                    self.player_pos = [r, c]
                    self.grid[r][c] = '.'
                elif char == 'B':
                    self.boxes.append([r, c])
                    self.grid[r][c] = '.'
                elif char == 'T':
                    self.targets.append([r, c])
                elif char == 'S':
                    self.points_coords.append([r, c])
                    self.grid[r][c] = '.'

        self.start_time = time.time()
        self.stuck_time = 0
        self.is_dead = False
        self.level_won = False
        self.history = []
        self.moves_count = 0
        self.hole_open_until = {}

    def save_state(self):
        state = {
            'p': list(self.player_pos),
            'b': [list(box) for box in self.boxes],
            'g': [list(row) for row in self.grid],
            'dead': self.is_dead,
            'stuck': self.stuck_time,
            'points': [list(p) for p in self.points_collected],
            'holes': dict(self.hole_open_until)
        }
        self.history.append(state)

    def undo(self):
        if self.history:
            state = self.history.pop()
            self.player_pos = state['p']
            self.boxes = state['b']
            self.grid = state['g']
            self.is_dead = state['dead']
            self.stuck_time = state['stuck']
            self.points_collected = state.get('points', [])
            self.hole_open_until = state.get('holes', {})
            self.level_won = False
            self.moves_count = max(0, self.moves_count - 1)

    def move(self, dr, dc):
        if self.level_won or self.is_dead or time.time() < self.stuck_time:
            return

        self.save_state()
        nr, nc = self.player_pos[0] + dr, self.player_pos[1] + dc

        if not (0 <= nr < self.rows and 0 <= nc < self.cols):
            self.history.pop()
            return

        target_tile = self.grid[nr][nc]
        if target_tile == 'W':
            self.history.pop()
            return

        if [nr, nc] in self.boxes:
            box_idx = self.boxes.index([nr, nc])
            br, bc = nr + dr, nc + dc

            if not (0 <= br < self.rows and 0 <= bc < self.cols):
                self.history.pop()
                return

            if self.grid[br][bc] != 'W' and [br, bc] not in self.boxes:
                self.boxes[box_idx] = [br, bc]
                self.player_pos = [nr, nc]
                self.moves_count += 1

                if self.grid[br][bc] == 'I':
                    self.slide_entity(self.boxes[box_idx], dr, dc, is_box=True, idx=box_idx)

                if box_idx < len(self.boxes) and self.grid[self.boxes[box_idx][0]][self.boxes[box_idx][1]] == 'H':
                    hole_pos = tuple(self.boxes[box_idx])
                    self.boxes.pop(box_idx)
                    self.hole_open_until[hole_pos] = time.time() + 1.0
            else:
                self.history.pop()
                return
        else:
            self.player_pos = [nr, nc]
            self.moves_count += 1

            if self.grid[self.player_pos[0]][self.player_pos[1]] == 'I':
                self.slide_entity(self.player_pos, dr, dc, is_box=False)

        if self.player_pos in self.points_coords and self.player_pos not in self.points_collected:
            self.points_collected.append(list(self.player_pos))

        r, c = self.player_pos
        current_tile = self.grid[r][c]

        if current_tile == 'M':
            self.stuck_time = time.time() + 5
        elif current_tile == 'L':
            self.is_dead = True

        if len(self.targets) > 0 and all(t in self.boxes for t in self.targets):
            self.level_won = True

    def slide_entity(self, pos, dr, dc, is_box=False, idx=None):
        while True:
            nr, nc = pos[0] + dr, pos[1] + dc

            if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                break

            if self.grid[nr][nc] == 'W' or [nr, nc] in self.boxes:
                break

            if is_box:
                if idx is None or idx >= len(self.boxes):
                    break
                self.boxes[idx] = [nr, nc]
                pos = self.boxes[idx]
            else:
                self.player_pos = [nr, nc]
                pos = self.player_pos

            if is_box and self.grid[nr][nc] == 'H':
                hole_pos = tuple([nr, nc])
                if idx < len(self.boxes):
                    self.boxes.pop(idx)
                self.hole_open_until[hole_pos] = time.time() + 1.0
                return

            if self.grid[nr][nc] != 'I':
                break

    def draw(self, screen):
        tile_size = min(SCREEN_HEIGHT // (self.rows + 2), 60)
        ox = (SCREEN_WIDTH - self.cols * tile_size) // 2
        oy = (SCREEN_HEIGHT - self.rows * tile_size) // 2
        now = time.time()

        for r in range(self.rows):
            for c in range(self.cols):
                rect = (ox + c * tile_size, oy + r * tile_size, tile_size, tile_size)
                x, y = rect[0], rect[1]
                tile = self.grid[r][c]

                colors = {
                    'W': COLOR_WALL,
                    'H': COLOR_HOLE,
                    'M': COLOR_HONEY,
                    'I': COLOR_ICE,
                    'L': COLOR_LAVA
                }

                if tile == '.':
                    surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                    surface.fill((10, 10, 15, 140))
                    screen.blit(surface, (rect[0], rect[1]))

                elif tile == 'H':
                    hole_pos = (r, c)
                    if now < self.hole_open_until.get(hole_pos, 0):
                        open_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                        open_surface.fill((90, 120, 150, 35))
                        screen.blit(open_surface, (x, y))
                        pygame.draw.rect(screen, (70, 110, 170), rect, 2)
                    else:
                        # Compuerta estilo panel metálico gris
                        pygame.draw.rect(screen, (60, 60, 70), rect)  # gris oscuro base
                        pygame.draw.rect(screen, (120, 120, 130), rect, 3)  # borde gris más claro

                        inner_margin = 5
                        inner_rect = pygame.Rect(
                            x + inner_margin,
                            y + inner_margin,
                            tile_size - inner_margin * 2,
                            tile_size - inner_margin * 2
                        )
                        pygame.draw.rect(screen, (90, 90, 100), inner_rect, 2)  # gris intermedio

                        # Ranuras superiores
                        for i in range(7):
                            sx = x + 8 + i * max(1, ((tile_size - 16) // 7))
                            pygame.draw.line(
                                screen,
                                (140, 140, 150),  # gris claro para contraste
                                (sx, y + 3),
                                (sx, y + 10),
                                1
                            )

                        # Detalles laterales
                        pygame.draw.line(screen, (100, 100, 110), (x + 4, y + 8), (x + 4, y + tile_size - 8), 2)
                        pygame.draw.line(screen, (100, 100, 110), (x + tile_size - 4, y + 8), (x + tile_size - 4, y + tile_size - 8), 2)

                        # Sombra inferior
                        pygame.draw.line(
                            screen,
                            (40, 40, 45),  # sombra gris muy oscura
                            (x, y + tile_size),
                            (x + tile_size, y + tile_size),
                            3
                        )

                elif tile == 'W':
                    pygame.draw.rect(screen, (10, 20, 40), rect)
                    pygame.draw.rect(screen, (2, 5, 15), rect, 3)

                    inner_margin = 6
                    inner_rect = pygame.Rect(
                        x + inner_margin,
                        y + inner_margin,
                        tile_size - inner_margin * 2,
                        tile_size - inner_margin * 2
                    )
                    pygame.draw.rect(screen, (2, 5, 15), inner_rect, 2)

                    for i in range(3):
                        ly = y + 10 + i * (tile_size // 4)
                        pygame.draw.line(
                            screen,
                            (35, 65, 110),
                            (x + 10, ly),
                            (x + tile_size - 10, ly),
                            2
                        )

                    pygame.draw.line(
                        screen,
                        (10, 15, 25),
                        (x, y + tile_size),
                        (x + tile_size, y + tile_size),
                        3
                    )

                elif tile == 'L':
                    # Lava estilo mosaico/pixel art
                    lava_surf = pygame.Surface((tile_size, tile_size))
                    lava_surf.fill((255, 90, 20))

                    block = max(4, tile_size // 6)
                    palette = [
                        (245, 65, 45),   # rojo
                        (255, 105, 20),  # naranja fuerte
                        (255, 170, 0),   # naranja/amarillo
                        (255, 235, 60),  # amarillo brillante
                    ]

                    for yy in range(0, tile_size, block):
                        for xx in range(0, tile_size, block):
                            # patrón fijo, sin parpadeo
                            idx = (r * 17 + c * 31 + (xx // block) * 7 + (yy // block) * 13) % len(palette)
                            pygame.draw.rect(
                                lava_surf,
                                palette[idx],
                                (xx, yy, block, block)
                            )

                    # algunos bloques extra para que no quede tan uniforme
                    for i in range(3):
                        hx = (r * 11 + c * 5 + i * 13) % tile_size
                        hy = (r * 7 + c * 19 + i * 9) % tile_size
                        pygame.draw.rect(lava_surf, (255, 240, 90), (hx, hy, max(2, block // 2), max(2, block // 2)))

                    screen.blit(lava_surf, (rect[0], rect[1]))
                elif tile == 'I':
                    x, y = rect[0], rect[1]

                    # Base azul hielo
                    pygame.draw.rect(screen, (110, 150, 210), rect)

                    pixel = tile_size // 6

                    # Paleta estilo tu imagen
                    colors = [
                        (200, 220, 255),  # blanco hielo
                        (160, 200, 255),  # azul claro
                        (130, 180, 240),  # azul medio
                    ]

                    # Patrón tipo "cristales"
                    pattern = [
                        (1, 1), (2, 2), (3, 3),
                        (4, 4), (2, 4), (3, 1)
                    ]

                    for i, (px, py) in enumerate(pattern):
                        color = colors[i % len(colors)]
                        pygame.draw.rect(
                            screen,
                            color,
                            (x + px * pixel, y + py * pixel, pixel, pixel)
                        )

                    # Brillo suave arriba
                    pygame.draw.line(
                        screen,
                        (220, 240, 255),
                        (x, y),
                        (x + tile_size, y),
                        2
                    )
                elif tile == 'M':
                    x, y = rect[0], rect[1]

                    # Base miel
                    pygame.draw.rect(screen, (240, 190, 40), rect)

                    # Tamaño del "hex"
                    hex_r = tile_size // 4

                    # Colores tipo miel
                    colors = [
                        (255, 210, 60),
                        (255, 190, 30),
                        (230, 170, 20),
                        (255, 230, 120)
                    ]

                    # Dibujar mini hexágonos (simulados)
                    for row in range(2):
                        for col in range(2):
                            cx = x + col * hex_r * 2 + hex_r
                            cy = y + row * hex_r * 2 + hex_r

                            # Offset para patrón tipo panal
                            if row % 2 == 1:
                                cx += hex_r

                            color = colors[(row * 2 + col) % len(colors)]

                            pygame.draw.polygon(screen, color, [
                                (cx, cy - hex_r),
                                (cx + hex_r, cy - hex_r // 2),
                                (cx + hex_r, cy + hex_r // 2),
                                (cx, cy + hex_r),
                                (cx - hex_r, cy + hex_r // 2),
                                (cx - hex_r, cy - hex_r // 2),
                            ])

                    # Borde suave tipo viscoso
                    pygame.draw.rect(screen, (200, 140, 20), rect, 2, border_radius=6)

                if [r, c] in self.targets:
                    x, y = rect[0], rect[1]

                    # Fondo azul marino
                    pygame.draw.rect(screen, (10, 20, 50), rect)

                    # Borde turquesa
                    pygame.draw.rect(screen, (40, 220, 200), rect, 3, border_radius=6)

                    # Círculo central turquesa
                    pygame.draw.circle(
                        screen,
                        (40, 220, 200),
                        (x + tile_size // 2, y + tile_size // 2),
                        tile_size // 4
                    )

                    # Brillo opcional (queda MUY bien)
                    pygame.draw.circle(
                        screen,
                        (120, 255, 240),
                        (x + tile_size // 2, y + tile_size // 2),
                        tile_size // 6,
                        2
                    )

        for b in self.boxes:
            x = ox + b[1]*tile_size
            y = oy + b[0]*tile_size

            rect = pygame.Rect(x+4, y+4, tile_size-8, tile_size-8)

            # Base
            pygame.draw.rect(screen, (170, 110, 40), rect, border_radius=6)

            # Sombra abajo
            pygame.draw.rect(screen, (110, 70, 25), rect, 3, border_radius=6)

            # Brillo arriba
            pygame.draw.line(
                screen,
                (230, 180, 90),
                (rect.left+3, rect.top+3),
                (rect.right-3, rect.top+3),
                2
            )

            # Línea vertical leve (detalle madera)
            pygame.draw.line(
                screen,
                (140, 90, 40),
                (rect.centerx, rect.top+5),
                (rect.centerx, rect.bottom-5),
                1
            )

        for point in self.points_coords:
            if point not in self.points_collected:
                cx = ox + point[1]*tile_size + tile_size//2
                cy = oy + point[0]*tile_size + tile_size//2
                r = tile_size // 4

                pygame.draw.polygon(screen, COLOR_POINTS, [
                    (cx, cy - r),
                    (cx + r//2, cy - r//3),
                    (cx + r, cy),
                    (cx + r//2, cy + r//3),
                    (cx, cy + r),
                    (cx - r//2, cy + r//3),
                    (cx - r, cy),
                    (cx - r//2, cy - r//3),
                ])

                # brillo
                pygame.draw.circle(screen, (255,255,200), (cx, cy), r//3)

        p = self.player_pos
        p_rect = (ox + p[1] * tile_size + 6, oy + p[0] * tile_size + 6, tile_size - 12, tile_size - 12)
        pygame.draw.ellipse(screen, COLOR_PLAYER, p_rect)

        self.draw_hud(screen)

        if self.level_won:
            msg = "¡ERES UN MAESTRO!" if self.current_level_idx == 50 else "¡NIVEL COMPLETADO!"
            sub = f"Movs: {self.moves_count} | ESPACIO: Siguiente"
            self.draw_overlay(screen, msg, sub)
        elif self.is_dead:
            self.draw_overlay(screen, "¡HAS MUERTO!", "R: Reiniciar | U: Deshacer")

    def draw_smart_border(self, screen, r, c, rect, color):
        x, y, size = rect[0], rect[1], rect[2]

        dirs = [
            (-1, 0, (x, y, size, 2)),               # arriba
            (1, 0, (x, y+size-2, size, 2)),         # abajo
            (0, -1, (x, y, 2, size)),               # izquierda
            (0, 1, (x+size-2, y, 2, size))          # derecha
        ]

        for dr, dc, line_rect in dirs:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < self.rows and 0 <= nc < self.cols) or self.grid[nr][nc] != self.grid[r][c]:
                pygame.draw.rect(screen, color, line_rect)

    def draw_hud(self, screen):
        t_str = f"Tiempo: {int(time.time() - self.start_time)}s"
        m_str = f"Movimientos: {self.moves_count}"
        l_str = f"Nivel: {self.current_level_idx}/50"
        p_str = f"Puntos: {len(self.points_collected)}/{len(self.points_coords)}"

        texts = [t_str, m_str, l_str, p_str]
        for i, txt in enumerate(texts):
            surf = self.font.render(txt, True, COLOR_TEXT)
            screen.blit(surf, (20, 20 + i * 30))

        if time.time() < self.stuck_time:
            wait = int(self.stuck_time - time.time()) + 1
            wait_text = self.font.render(f"¡PEGADO! {wait}s", True, COLOR_HONEY)
            screen.blit(wait_text, (SCREEN_WIDTH // 2 - 50, 20))

    def draw_overlay(self, screen, text, subtext):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        t_surf = self.big_font.render(text, True, (255, 255, 255))
        st_surf = self.font.render(subtext, True, (200, 200, 200))

        screen.blit(t_surf, (SCREEN_WIDTH // 2 - t_surf.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
        screen.blit(st_surf, (SCREEN_WIDTH // 2 - st_surf.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

    def clone(self):
        clone = object.__new__(SokobanEngine)

        clone.current_level_idx = self.current_level_idx
        clone.font = self.font
        clone.big_font = self.big_font

        clone.grid = [row[:] for row in self.grid]
        clone.rows = self.rows
        clone.cols = self.cols
        clone.player_pos = list(self.player_pos)
        clone.boxes = [list(b) for b in self.boxes]
        clone.targets = [list(t) for t in self.targets]
        clone.points_coords = [list(p) for p in self.points_coords]
        clone.points_collected = [list(p) for p in self.points_collected]

        clone.start_time = self.start_time
        clone.stuck_time = self.stuck_time
        clone.is_dead = self.is_dead
        clone.level_won = self.level_won
        clone.hole_open_until = dict(self.hole_open_until)
        clone.history = [
            {
                'p': list(state['p']),
                'b': [list(box) for box in state['b']],
                'g': [list(row) for row in state['g']],
                'dead': state['dead'],
                'stuck': state['stuck'],
                'points': [list(p) for p in state.get('points', [])],
                'holes': dict(state.get('holes', {}))
            }
            for state in self.history
        ]
        clone.moves_count = self.moves_count

        return clone

    def state_key(self):
        return (
            tuple(self.player_pos),
            tuple(sorted(tuple(b) for b in self.boxes)),
            tuple(sorted(tuple(p) for p in self.points_collected)),
            tuple(sorted((pos, int(t)) for pos, t in self.hole_open_until.items())),
        )