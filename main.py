import heapq
import pygame
import sys
from constants import *
from engine import SokobanEngine

def draw_text(screen, text, font, color, x, y):
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(x, y))
    screen.blit(surf, rect)

def draw_button(screen, text, font, x, y, w, h, mouse_pos, active=False):
    rect = pygame.Rect(x - w//2, y - h//2, w, h)
    if active:
        color = COLOR_BTN_ACTIVE
    else:
        color = COLOR_BTN_HOVER if rect.collidepoint(mouse_pos) else COLOR_BTN
    pygame.draw.rect(screen, color, rect, border_radius=10)
    pygame.draw.rect(screen, COLOR_TEXT, rect, 2, border_radius=10)
    draw_text(screen, text, font, COLOR_TEXT, x, y)
    return rect


def draw_panel(screen, x, y, w, h):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, (40, 40, 55), rect, border_radius=20)
    pygame.draw.rect(screen, COLOR_BTN, rect, 2, border_radius=20)


def evaluate_heuristic(engine, heuristic_type):
    if heuristic_type == "Puntos":
        heuristic_type = "Tiempo"

    distance_sum = 0
    for box in engine.boxes:
        dist = min(abs(box[0] - t[0]) + abs(box[1] - t[1]) for t in engine.targets) if engine.targets else 0
        distance_sum += dist

    player_dist = 0
    if engine.boxes:
        player_dist = min(abs(engine.player_pos[0] - box[0]) + abs(engine.player_pos[1] - box[1]) for box in engine.boxes)

    if heuristic_type == "Tiempo":
        return distance_sum + 0.08 * player_dist
    if heuristic_type == "Movimientos":
        return distance_sum * 1.15 + 0.03 * player_dist
    return distance_sum + 0.15 * player_dist


def find_greedy_solution(start_engine, heuristic_goal, heuristic_type, max_nodes=7000):
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    node_id = 0
    nodes_explored = 0
    priority_queue = []
    start_score = evaluate_heuristic(start_engine, heuristic_type)
    start_priority = start_score if heuristic_goal == "Minimizar" else -start_score
    heapq.heappush(priority_queue, (start_priority, node_id, start_engine.clone(), []))
    visited = {start_engine.state_key()}

    while priority_queue and nodes_explored < max_nodes:
        _, _, node, path = heapq.heappop(priority_queue)
        nodes_explored += 1

        if node.level_won:
            return path, nodes_explored

        for dr, dc in directions:
            child = node.clone()
            child.move(dr, dc)
            if child.level_won:
                return path + [(dr, dc)], nodes_explored
            if child.player_pos == node.player_pos and child.boxes == node.boxes:
                continue
            if child.is_dead:
                continue

            key = child.state_key()
            if key in visited:
                continue
            visited.add(key)

            score = evaluate_heuristic(child, heuristic_type)
            priority = score if heuristic_goal == "Minimizar" else -score
            node_id += 1
            heapq.heappush(priority_queue, (priority, node_id, child, path + [(dr, dc)]))

    return None, nodes_explored


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Sokovan Ultimate Edition")
    clock = pygame.time.Clock()
    
    title_font = pygame.font.SysFont("Verdana", 80, bold=True)
    config_title_font = pygame.font.SysFont("Verdana", 46, bold=True)
    menu_font = pygame.font.SysFont("Verdana", 25, bold=True)
    small_font = pygame.font.SysFont("Verdana", 18)
    level_num_font = pygame.font.SysFont("Verdana", 20, bold=True)

    game = SokobanEngine()
    current_state = STATE_MENU
    heuristic_goal = "Minimizar"
    heuristic_type = "Tiempo"
    auto_state = {
        'path': [],
        'step': 0,
        'searching': False,
        'level': 1,
        'message': "",
        'next_move_time': 0,
        'nodes': 0
    }

    while True:
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            # --- LÓGICA DEL MENÚ ---
            if current_state == STATE_MENU:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    btn_jugar = pygame.Rect(SCREEN_WIDTH//2 - 100, 330, 200, 50)
                    btn_heuristica = pygame.Rect(SCREEN_WIDTH//2 - 100, 410, 200, 50)
                    btn_niveles = pygame.Rect(SCREEN_WIDTH//2 - 100, 490, 200, 50)

                    if btn_jugar.collidepoint(event.pos):
                        current_state = STATE_PLAYING
                    elif btn_heuristica.collidepoint(event.pos):
                        current_state = STATE_HEURISTIC_CONFIG
                    elif btn_niveles.collidepoint(event.pos):
                        current_state = STATE_LEVEL_SELECT

            # --- LÓGICA CONFIGURACIÓN DE HEURÍSTICA ---
            elif current_state == STATE_HEURISTIC_CONFIG:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    current_state = STATE_MENU

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    btn_minimizar = pygame.Rect(SCREEN_WIDTH//2 - 120 - 110, 350 - 25, 220, 55)
                    btn_maximizar = pygame.Rect(SCREEN_WIDTH//2 + 120 - 110, 350 - 25, 220, 55)
                    btn_tiempo = pygame.Rect(SCREEN_WIDTH//2 - 250 - 105, 480 - 25, 210, 55)
                    btn_movimientos = pygame.Rect(SCREEN_WIDTH//2 - 105, 480 - 25, 210, 55)
                    btn_puntos = pygame.Rect(SCREEN_WIDTH//2 + 250 - 105, 480 - 25, 210, 55)
                    btn_iniciar = pygame.Rect(SCREEN_WIDTH//2 - 140, 565 - 30, 280, 60)

                    if btn_minimizar.collidepoint(event.pos):
                        heuristic_goal = "Minimizar"
                    elif btn_maximizar.collidepoint(event.pos):
                        heuristic_goal = "Maximizar"
                    elif btn_tiempo.collidepoint(event.pos):
                        heuristic_type = "Tiempo"
                    elif btn_movimientos.collidepoint(event.pos):
                        heuristic_type = "Movimientos"
                    elif btn_puntos.collidepoint(event.pos):
                        heuristic_type = "Puntos"
                    elif btn_iniciar.collidepoint(event.pos):
                        current_state = STATE_AUTOPLAY
                        auto_state['level'] = 1
                        auto_state['step'] = 0
                        auto_state['path'] = []
                        auto_state['searching'] = True
                        auto_state['message'] = f"Iniciando autoplay desde nivel 1: {heuristic_goal} / {heuristic_type}"
                        auto_state['next_move_time'] = pygame.time.get_ticks()
                        auto_state['nodes'] = 0
                        if heuristic_type == "Puntos":
                            auto_state['message'] += " (Puntos no implementado, usando Tiempo)"
                        game.current_level_idx = 1
                        game.load_level(1)

            elif current_state == STATE_AUTOPLAY:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    current_state = STATE_MENU

            # --- LÓGICA SELECTOR DE NIVELES ---
            elif current_state == STATE_LEVEL_SELECT:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        current_state = STATE_MENU
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Detectar click en la cuadrícula
                    # (Usamos la misma lógica que el dibujo para detectar colisión)
                    margin, size, gap = 100, 50, 15
                    for i in range(50):
                        col = i % 10
                        row = i // 10
                        x = margin + col * (size + gap)
                        y = 200 + row * (size + gap)
                        level_rect = pygame.Rect(x, y, size, size)
                        
                        if level_rect.collidepoint(event.pos):
                            game.current_level_idx = i + 1
                            game.load_level(game.current_level_idx)
                            current_state = STATE_MENU # Volver al menú

            # --- LÓGICA JUEGO ---
            elif current_state == STATE_PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        current_state = STATE_MENU
                    if event.key == pygame.K_r: game.load_level(game.current_level_idx)
                    if event.key == pygame.K_u: game.undo()
                    
                    if not game.level_won and not game.is_dead:
                        if event.key == pygame.K_UP:    game.move(-1, 0)
                        if event.key == pygame.K_DOWN:  game.move(1, 0)
                        if event.key == pygame.K_LEFT:  game.move(0, -1)
                        if event.key == pygame.K_RIGHT: game.move(0, 1)
                    
                    if game.level_won and event.key == pygame.K_SPACE:
                        if game.current_level_idx < 50:
                            game.current_level_idx += 1
                            game.load_level(game.current_level_idx)
                        else:
                            # Aquí podrías cambiar a un nuevo estado STATE_GAME_OVER
                            print("¡Felicidades! Has completado todos los niveles.")
                            # O simplemente mostrar las estadísticas finales:
                            game.draw_overlay(screen, "¡ERES UN MAESTRO!", f"Movs Totales: {game.moves_count} | Gracias por jugar")

        # --- RENDERIZADO ---
        screen.fill(COLOR_BG)

        if current_state == STATE_MENU:
            panel_w, panel_h = 760, 500
            panel_x = SCREEN_WIDTH//2 - panel_w//2
            panel_y = 100
            draw_panel(screen, panel_x, panel_y, panel_w, panel_h)

            draw_text(screen, "SOKOVAN", title_font, COLOR_PLAYER, SCREEN_WIDTH//2, 170)
            draw_text(screen, "Creado por: huevoscartoon", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 215)
            draw_button(screen, "JUGAR", menu_font, SCREEN_WIDTH//2, 340, 260, 65, mouse_pos)
            draw_button(screen, "HEURÍSTICA", menu_font, SCREEN_WIDTH//2, 425, 260, 65, mouse_pos)
            draw_button(screen, "NIVELES", menu_font, SCREEN_WIDTH//2, 510, 260, 65, mouse_pos)
            draw_text(screen, f"Nivel Seleccionado: {game.current_level_idx}", small_font, COLOR_TARGET, SCREEN_WIDTH//2, 580)
            draw_text(screen, f"Heurística: {heuristic_goal} / {heuristic_type}", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 610)

        elif current_state == STATE_HEURISTIC_CONFIG:
            panel_w, panel_h = 860, 620
            panel_x = SCREEN_WIDTH//2 - panel_w//2
            panel_y = 80
            draw_panel(screen, panel_x, panel_y, panel_w, panel_h)

            draw_text(screen, "CONFIGURAR HEURÍSTICA", config_title_font, COLOR_PLAYER, SCREEN_WIDTH//2, 165)
            draw_text(screen, "Selecciona el objetivo y el tipo de heurística.", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 220)
            draw_text(screen, "INICIAR ejecutará autoplay desde el nivel 1.", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 245)
            draw_text(screen, "El modo Puntos todavía no está implementado.", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 270)

            draw_text(screen, "Objetivo:", menu_font, COLOR_TEXT, SCREEN_WIDTH//2, 305)
            draw_button(screen, "MINIMIZAR", menu_font, SCREEN_WIDTH//2 - 120, 350, 220, 55, mouse_pos, active=(heuristic_goal == "Minimizar"))
            draw_button(screen, "MAXIMIZAR", menu_font, SCREEN_WIDTH//2 + 120, 350, 220, 55, mouse_pos, active=(heuristic_goal == "Maximizar"))

            draw_text(screen, "Heurística:", menu_font, COLOR_TEXT, SCREEN_WIDTH//2, 425)
            draw_button(screen, "TIEMPO", menu_font, SCREEN_WIDTH//2 - 250, 480, 210, 55, mouse_pos, active=(heuristic_type == "Tiempo"))
            draw_button(screen, "MOVIMIENTOS", menu_font, SCREEN_WIDTH//2, 480, 210, 55, mouse_pos, active=(heuristic_type == "Movimientos"))
            draw_button(screen, "PUNTOS", menu_font, SCREEN_WIDTH//2 + 250, 480, 210, 55, mouse_pos, active=(heuristic_type == "Puntos"))

            draw_button(screen, "INICIAR", menu_font, SCREEN_WIDTH//2, 565, 320, 65, mouse_pos)
            draw_text(screen, "Presiona ESC para volver al menú", small_font, (180, 180, 180), SCREEN_WIDTH//2, 635)

            draw_text(screen, f"Seleccionado: {heuristic_goal} / {heuristic_type}", small_font, COLOR_TARGET, SCREEN_WIDTH//2, 690)

        elif current_state == STATE_AUTOPLAY:
            game.draw(screen)
            draw_text(screen, "AUTOPLAY ACTIVADO", menu_font, COLOR_PLAYER, SCREEN_WIDTH//2, 80)
            draw_text(screen, f"Nivel automático: {auto_state['level']}", small_font, COLOR_TEXT, SCREEN_WIDTH//2, 110)
            draw_text(screen, auto_state['message'], small_font, COLOR_TEXT, SCREEN_WIDTH//2, 135)
            if auto_state['searching']:
                draw_text(screen, "Buscando solución... Esto puede tomar algunos segundos.", small_font, COLOR_BTN_HOVER, SCREEN_WIDTH//2, 160)
            if auto_state['path']:
                draw_text(screen, f"Pasos: {len(auto_state['path'])}  Nodo(s): {auto_state['nodes']}", small_font, COLOR_TARGET, SCREEN_WIDTH//2, 185)
            draw_text(screen, "Presiona ESC para detener autoplay", small_font, (180, 180, 180), SCREEN_WIDTH//2, 710)

            if auto_state['searching']:
                solution, nodes = find_greedy_solution(game, heuristic_goal, heuristic_type)
                auto_state['nodes'] = nodes
                auto_state['searching'] = False
                if solution:
                    auto_state['path'] = solution
                    auto_state['step'] = 0
                    auto_state['message'] = f"Solución encontrada: {len(solution)} pasos"
                    auto_state['next_move_time'] = pygame.time.get_ticks()
                else:
                    auto_state['message'] = f"No se encontró solución en este nivel ({nodes} nodos). Presiona ESC."
                    auto_state['path'] = []

            elif auto_state['path'] and pygame.time.get_ticks() >= auto_state['next_move_time']:
                dr, dc = auto_state['path'][auto_state['step']]
                game.move(dr, dc)
                auto_state['step'] += 1
                auto_state['next_move_time'] = pygame.time.get_ticks() + 130

                if game.level_won:
                    if auto_state['level'] < 50:
                        auto_state['level'] += 1
                        game.current_level_idx = auto_state['level']
                        game.load_level(auto_state['level'])
                        auto_state['searching'] = True
                        auto_state['message'] = f"Nivel {auto_state['level']} cargado. Buscando solución..."
                        auto_state['path'] = []
                        auto_state['step'] = 0
                    else:
                        auto_state['message'] = "Autoplay completado."
                        auto_state['path'] = []

            elif not auto_state['path'] and not auto_state['searching'] and not game.level_won:
                auto_state['message'] = f"No se puede resolver este nivel automáticamente." 

        elif current_state == STATE_LEVEL_SELECT:
            draw_text(screen, "SELECCIONA UN NIVEL", menu_font, COLOR_TEXT, SCREEN_WIDTH//2, 100)
            
            # Dibujar cuadrícula de 50 niveles
            margin, size, gap = 100, 50, 15
            for i in range(50):
                lvl_num = i + 1
                col = i % 10
                row = i // 10
                x = margin + col * (size + gap)
                y = 200 + row * (size + gap)
                
                rect = pygame.Rect(x, y, size, size)
                # Resaltar si el mouse está encima o si es el nivel actual
                if rect.collidepoint(mouse_pos):
                    color = COLOR_PLAYER
                elif lvl_num == game.current_level_idx:
                    color = COLOR_TARGET
                else:
                    color = COLOR_BTN
                
                pygame.draw.rect(screen, color, rect, border_radius=5)
                draw_text(screen, str(lvl_num), level_num_font, COLOR_TEXT, x + size//2, y + size//2)

            draw_text(screen, "Presiona ESC para volver al menú", small_font, (150, 150, 150), SCREEN_WIDTH//2, 700)

        elif current_state == STATE_PLAYING:
            game.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()