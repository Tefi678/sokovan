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
        self.load_level(self.current_level_idx)

    def load_level(self, idx):
        # Si el nivel no existe, vuelve al 1 (seguridad)
        layout = LEVEL_DATA.get(idx, LEVEL_DATA[1])
        self.grid = [list(row) for row in layout]
        self.rows = len(self.grid)
        self.cols = len(self.grid[0])
        
        self.player_pos = []
        self.boxes = []
        self.targets = []
        
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

        self.start_time = time.time()
        self.stuck_time = 0
        self.is_dead = False
        self.level_won = False
        self.history = []
        self.moves_count = 0

    def save_state(self):
        """ Guarda una copia profunda de la posición actual """
        state = {
            'p': list(self.player_pos),
            'b': [list(box) for box in self.boxes],
            'g': [list(row) for row in self.grid],
            'dead': self.is_dead,
            'stuck': self.stuck_time
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
            self.level_won = False # No puedes ganar mientras deshaces
            self.moves_count = max(0, self.moves_count - 1)

    def move(self, dr, dc):
        if self.level_won or self.is_dead or time.time() < self.stuck_time:
            return

        self.save_state()
        nr, nc = self.player_pos[0] + dr, self.player_pos[1] + dc

        # Validar límites
        if not (0 <= nr < self.rows and 0 <= nc < self.cols): 
            self.history.pop()
            return

        target_tile = self.grid[nr][nc]
        if target_tile == 'W': 
            self.history.pop()
            return

        # --- LÓGICA DE EMPUJAR CAJA ---
        if [nr, nc] in self.boxes:
            box_idx = self.boxes.index([nr, nc])
            br, bc = nr + dr, nc + dc
            
            # Verificar si el espacio tras la caja está libre
            if self.grid[br][bc] != 'W' and [br, bc] not in self.boxes:
                self.boxes[box_idx] = [br, bc]
                self.player_pos = [nr, nc]
                self.moves_count += 1
                
                # Deslizar caja si cae en hielo
                if self.grid[br][bc] == 'I':
                    self.slide_entity(self.boxes[box_idx], dr, dc, is_box=True, idx=box_idx)
                
                # Caer en hueco
                if self.grid[self.boxes[box_idx][0]][self.boxes[box_idx][1]] == 'H':
                    self.boxes.pop(box_idx)
            else:
                self.history.pop() # Movimiento inválido
                return
        else:
            # --- MOVIMIENTO SIMPLE JUGADOR ---
            self.player_pos = [nr, nc]
            self.moves_count += 1
            
            # Deslizar jugador si pisa hielo
            if self.grid[self.player_pos[0]][self.player_pos[1]] == 'I':
                self.slide_entity(self.player_pos, dr, dc, is_box=False)

        # --- EFECTOS DE TERRENO ---
        r, c = self.player_pos
        current_tile = self.grid[r][c]
        
        if current_tile == 'M': # Miel: te quedas pegado 5 seg
            self.stuck_time = time.time() + 5
        elif current_tile == 'L': # Lava: muerte
            self.is_dead = True

        # --- CHECK VICTORIA ---
        if len(self.targets) > 0 and all(t in self.boxes for t in self.targets):
            self.level_won = True

    def slide_entity(self, pos, dr, dc, is_box=False, idx=None):
        """ Desliza objetos en el hielo hasta que choquen con algo que no sea hielo """
        while True:
            nr, nc = pos[0] + dr, pos[1] + dc
            
            # Se detiene ante pared o si hay una caja delante
            if self.grid[nr][nc] == 'W' or [nr, nc] in self.boxes:
                break
            
            # Actualizar posición
            if is_box:
                self.boxes[idx] = [nr, nc]
                pos = self.boxes[idx]
            else:
                self.player_pos = [nr, nc]
                pos = self.player_pos
                
            # Si el suelo ya no es hielo, se detiene
            if self.grid[nr][nc] != 'I':
                break

    def draw(self, screen):
        # Ajuste dinámico de cámara
        tile_size = min(SCREEN_HEIGHT // (self.rows + 2), 60)
        ox = (SCREEN_WIDTH - self.cols * tile_size) // 2
        oy = (SCREEN_HEIGHT - self.rows * tile_size) // 2

        # 1. Dibujar Suelo y Terrenos Especiales
        for r in range(self.rows):
            for c in range(self.cols):
                rect = (ox + c*tile_size, oy + r*tile_size, tile_size, tile_size)
                tile = self.grid[r][c]
                
                # Color base según el tipo de celda
                colors = {'W': COLOR_WALL, 'H': COLOR_HOLE, 'M': COLOR_HONEY, 
                          'I': COLOR_ICE, 'L': COLOR_LAVA}
                color = colors.get(tile, COLOR_BG)
                
                pygame.draw.rect(screen, color, rect)
                
                # Dibujar Metas (Targets)
                if [r, c] in self.targets:
                    pygame.draw.circle(screen, COLOR_TARGET, 
                                      (rect[0]+tile_size//2, rect[1]+tile_size//2), 
                                      tile_size//4)

        # 2. Dibujar Cajas
        for b in self.boxes:
            rect = (ox + b[1]*tile_size + 4, oy + b[0]*tile_size + 4, tile_size - 8, tile_size - 8)
            pygame.draw.rect(screen, COLOR_BOX, rect, border_radius=5)
            pygame.draw.rect(screen, (0,0,0), rect, 2, border_radius=5) # Borde caja

        # 3. Dibujar Jugador
        p = self.player_pos
        p_rect = (ox + p[1]*tile_size + 6, oy + p[0]*tile_size + 6, tile_size - 12, tile_size - 12)
        pygame.draw.ellipse(screen, COLOR_PLAYER, p_rect)

        # 4. HUD (Interfaz de usuario)
        self.draw_hud(screen)

        # 5. Overlays (Ganar/Morir)
        if self.level_won:
            msg = "¡ERES UN MAESTRO!" if self.current_level_idx == 50 else "¡NIVEL COMPLETADO!"
            sub = f"Movs: {self.moves_count} | ESPACIO: Siguiente"
            self.draw_overlay(screen, msg, sub)
        elif self.is_dead:
            self.draw_overlay(screen, "¡HAS MUERTO!", "R: Reiniciar | U: Deshacer")

    def draw_hud(self, screen):
        t_str = f"Tiempo: {int(time.time() - self.start_time)}s"
        m_str = f"Movimientos: {self.moves_count}"
        l_str = f"Nivel: {self.current_level_idx}/50"
        
        texts = [t_str, m_str, l_str]
        for i, txt in enumerate(texts):
            surf = self.font.render(txt, True, COLOR_TEXT)
            screen.blit(surf, (20, 20 + i*30))

        if time.time() < self.stuck_time:
            wait = int(self.stuck_time - time.time()) + 1
            wait_text = self.font.render(f"¡PEGADO! {wait}s", True, COLOR_HONEY)
            screen.blit(wait_text, (SCREEN_WIDTH//2 - 50, 20))

    def draw_overlay(self, screen, text, subtext):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0,0))
        
        t_surf = self.big_font.render(text, True, (255, 255, 255))
        st_surf = self.font.render(subtext, True, (200, 200, 200))
        
        screen.blit(t_surf, (SCREEN_WIDTH//2 - t_surf.get_width()//2, SCREEN_HEIGHT//2 - 50))
        screen.blit(st_surf, (SCREEN_WIDTH//2 - st_surf.get_width()//2, SCREEN_HEIGHT//2 + 30))

    def clone(self):
        clone = SokobanEngine()
        clone.current_level_idx = self.current_level_idx
        clone.grid = [list(row) for row in self.grid]
        clone.rows = self.rows
        clone.cols = self.cols
        clone.player_pos = list(self.player_pos)
        clone.boxes = [list(b) for b in self.boxes]
        clone.targets = [list(t) for t in self.targets]
        clone.start_time = self.start_time
        clone.stuck_time = self.stuck_time
        clone.is_dead = self.is_dead
        clone.level_won = self.level_won
        clone.history = [
            {
                'p': list(state['p']),
                'b': [list(box) for box in state['b']],
                'g': [list(row) for row in state['g']],
                'dead': state['dead'],
                'stuck': state['stuck']
            }
            for state in self.history
        ]
        clone.moves_count = self.moves_count
        return clone

    def state_key(self):
        return (
            self.player_pos[0],
            self.player_pos[1],
            tuple(tuple(row) for row in self.grid),
            tuple(tuple(box) for box in self.boxes)
        )