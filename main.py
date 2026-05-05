import heapq
import pygame
import sys
import time

from constants import *
from engine import SokobanEngine


HEURISTIC_MODES = {
    "min_time": {
        "label": "Minimizar tiempo",
        "goal": "min",
    },
    "min_moves": {
        "label": "Minimizar movimientos",
        "goal": "min",
    },
    "max_points": {
        "label": "Maximizar puntos",
        "goal": "max",
    },
}

LEVEL_SEARCH_LIMITS = {
    "min_time": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
    "min_moves": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
    "max_points": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
}


def draw_text(screen, text, font, color, x, y):
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(x, y))
    screen.blit(surf, rect)


def draw_button(screen, text, font, x, y, w, h, mouse_pos, active=False):
    rect = pygame.Rect(x - w // 2, y - h // 2, w, h)
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


def get_heuristic_label(mode):
    return HEURISTIC_MODES.get(mode, HEURISTIC_MODES["min_time"])["label"]


def is_maximizing(mode):
    return HEURISTIC_MODES.get(mode, HEURISTIC_MODES["min_time"])["goal"] == "max"


def evaluate_heuristic(engine, mode, depth=0):
    box_positions = {tuple(b) for b in engine.boxes}
    target_positions = [tuple(t) for t in engine.targets]
    collected_points = {tuple(p) for p in engine.points_collected}

    total_points = len(engine.points_coords)
    points_collected = len(collected_points)
    remaining_points = total_points - points_collected

    box_distance = 0
    if target_positions:
        for box in box_positions:
            box_distance += min(abs(box[0] - t[0]) + abs(box[1] - t[1]) for t in target_positions)

    player_to_box = 0
    if box_positions:
        p = tuple(engine.player_pos)
        player_to_box = min(abs(p[0] - b[0]) + abs(p[1] - b[1]) for b in box_positions)

    # 🔥 Heurísticas corregidas según objetivo REAL
    if mode == "min_moves":
        # penaliza fuertemente cada paso
        return depth * 20 + box_distance * 25 + player_to_box * 8

    if mode == "max_points":
        # recompensa puntos y luego completar
        return -(points_collected * 2000) + box_distance * 10 + player_to_box * 3 + depth * 5

    # min_time → similar a movimientos pero más agresivo
    return depth * 15 + box_distance * 20 + player_to_box * 6


def priority_from_score(score, mode):
    return -score if is_maximizing(mode) else score


def is_better(score, best_score, mode):
    if is_maximizing(mode):
        return score > best_score
    return score < best_score


def path_to_string(path):
    dir_map = {(-1, 0): 'U', (1, 0): 'D', (0, -1): 'L', (0, 1): 'R'}
    return '-'.join(dir_map.get(move, '?') for move in path)


def find_greedy_solution(start_engine, mode, max_nodes=100000, max_time=20.0, max_depth=1000):
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    start_time = time.time()

    pq = []
    node_id = 0
    nodes_explored = 0

    start_score = evaluate_heuristic(start_engine, mode, depth=0)
    heapq.heappush(
        pq,
        (priority_from_score(start_score, mode), 0, node_id, start_engine.clone(), [])
    )

    best_seen = {start_engine.state_key(): start_score}

    while pq and nodes_explored < max_nodes and (time.time() - start_time) < max_time:
        _, depth, _, node, path = heapq.heappop(pq)
        nodes_explored += 1

        if node.level_won:
            return path, nodes_explored, node

        if depth >= max_depth:
            continue

        for dr, dc in directions:
            child = node.clone()
            child.move(dr, dc)

            if child.player_pos == node.player_pos and child.boxes == node.boxes:
                continue

            if child.is_dead:
                continue

            key = child.state_key()
            score = evaluate_heuristic(child, mode, depth + 1)

            if key in best_seen and not is_better(score, best_seen[key], mode):
                continue

            best_seen[key] = score

            if child.level_won:
                return path + [(dr, dc)], nodes_explored, child

            node_id += 1
            heapq.heappush(
                pq,
                (priority_from_score(score, mode), depth + 1, node_id, child, path + [(dr, dc)])
            )

    return None, nodes_explored, None


def calculate_solution_cost(final_state, path, mode):
    if mode == "min_moves":
        return len(path), f"Movimientos: {len(path)}"

    if mode == "min_time":
        estimated_time_ms = len(path) * 130
        estimated_time_s = estimated_time_ms / 1000
        return estimated_time_s, f"Tiempo estimado: {estimated_time_s:.2f}s ({len(path)} pasos)"

    if mode == "max_points":
        if final_state:
            points_collected = len(final_state.points_collected)
            total_points = len(final_state.points_coords)
            return points_collected, f"Puntos: {points_collected}/{total_points} | Pasos: {len(path)}"
        return 0, f"Pasos: {len(path)}"

    return 0, f"Pasos: {len(path)}"


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Sokoban Ultimate Edition")
    clock = pygame.time.Clock()

    background = pygame.image.load("assets/bg1.png")
    background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))

    title_font = pygame.font.SysFont("Verdana", 80, bold=True)
    config_title_font = pygame.font.SysFont("Verdana", 46, bold=True)
    menu_font = pygame.font.SysFont("Verdana", 25, bold=True)
    small_font = pygame.font.SysFont("Verdana", 18)
    level_num_font = pygame.font.SysFont("Verdana", 20, bold=True)

    game = SokobanEngine()
    current_state = STATE_MENU
    selected_mode = "min_time"

    auto_state = {
        'path': [],
        'step': 0,
        'searching': False,
        'level': 1,
        'message': "",
        'next_move_time': 0,
        'nodes': 0,
        'final_state': None,
        'level_complete_until': 0,
        'pending_next_level': False,
        'completion_text': "",
    }

    while True:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if current_state == STATE_MENU:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    btn_jugar = pygame.Rect(SCREEN_WIDTH // 2 - 100, 330, 200, 50)
                    btn_heuristica = pygame.Rect(SCREEN_WIDTH // 2 - 100, 410, 200, 50)
                    btn_niveles = pygame.Rect(SCREEN_WIDTH // 2 - 100, 490, 200, 50)

                    if btn_jugar.collidepoint(event.pos):
                        current_state = STATE_PLAYING
                    elif btn_heuristica.collidepoint(event.pos):
                        current_state = STATE_HEURISTIC_CONFIG
                    elif btn_niveles.collidepoint(event.pos):
                        current_state = STATE_LEVEL_SELECT

            elif current_state == STATE_HEURISTIC_CONFIG:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    current_state = STATE_MENU

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    btn_min_time = pygame.Rect(SCREEN_WIDTH // 2 - 390, 360 - 28, 250, 58)
                    btn_min_moves = pygame.Rect(SCREEN_WIDTH // 2 - 125, 360 - 28, 250, 58)
                    btn_max_points = pygame.Rect(SCREEN_WIDTH // 2 + 140, 360 - 28, 250, 58)
                    btn_iniciar = pygame.Rect(SCREEN_WIDTH // 2 - 140, 565 - 30, 280, 60)

                    if btn_min_time.collidepoint(event.pos):
                        selected_mode = "min_time"
                    elif btn_min_moves.collidepoint(event.pos):
                        selected_mode = "min_moves"
                    elif btn_max_points.collidepoint(event.pos):
                        selected_mode = "max_points"
                    elif btn_iniciar.collidepoint(event.pos):
                        current_state = STATE_AUTOPLAY
                        auto_state['level'] = 1
                        auto_state['step'] = 0
                        auto_state['path'] = []
                        auto_state['searching'] = True
                        auto_state['message'] = f"Iniciando autoplay desde nivel 1: {get_heuristic_label(selected_mode)}"
                        auto_state['next_move_time'] = pygame.time.get_ticks()
                        auto_state['nodes'] = 0
                        auto_state['final_state'] = None
                        auto_state['level_complete_until'] = 0
                        auto_state['pending_next_level'] = False
                        auto_state['completion_text'] = ""
                        game.current_level_idx = 1
                        game.load_level(1)

            elif current_state == STATE_AUTOPLAY:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    current_state = STATE_MENU

            elif current_state == STATE_LEVEL_SELECT:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        current_state = STATE_MENU

                if event.type == pygame.MOUSEBUTTONDOWN:
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
                            current_state = STATE_MENU

            elif current_state == STATE_PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        current_state = STATE_MENU
                    if event.key == pygame.K_r:
                        game.load_level(game.current_level_idx)
                    if event.key == pygame.K_u:
                        game.undo()

                    if not game.level_won and not game.is_dead:
                        if event.key == pygame.K_UP:
                            game.move(-1, 0)
                        if event.key == pygame.K_DOWN:
                            game.move(1, 0)
                        if event.key == pygame.K_LEFT:
                            game.move(0, -1)
                        if event.key == pygame.K_RIGHT:
                            game.move(0, 1)

                    if game.level_won and event.key == pygame.K_SPACE:
                        if game.current_level_idx < 50:
                            game.current_level_idx += 1
                            game.load_level(game.current_level_idx)
                        else:
                            print("¡Felicidades! Has completado todos los niveles.")
                            game.draw_overlay(screen, "¡ERES UN MAESTRO!", f"Movs Totales: {game.moves_count} | Gracias por jugar")

        screen.blit(background, (0, 0))

        if current_state == STATE_MENU:
            panel_w, panel_h = 760, 500
            panel_x = SCREEN_WIDTH // 2 - panel_w // 2
            panel_y = 100
            draw_panel(screen, panel_x, panel_y, panel_w, panel_h)

            draw_text(screen, "SOKOBAN", title_font, COLOR_PLAYER, SCREEN_WIDTH // 2, 170)
            draw_text(screen, "Creado por: huevoscartoon", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 215)
            draw_button(screen, "JUGAR", menu_font, SCREEN_WIDTH // 2, 340, 260, 65, mouse_pos)
            draw_button(screen, "HEURÍSTICA", menu_font, SCREEN_WIDTH // 2, 425, 260, 65, mouse_pos)
            draw_button(screen, "NIVELES", menu_font, SCREEN_WIDTH // 2, 510, 260, 65, mouse_pos)
            draw_text(screen, f"Nivel Seleccionado: {game.current_level_idx}", small_font, COLOR_TARGET, SCREEN_WIDTH // 2, 580)
            draw_text(screen, f"Heurística: {get_heuristic_label(selected_mode)}", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 610)

        elif current_state == STATE_HEURISTIC_CONFIG:
            panel_w, panel_h = 900, 620
            panel_x = SCREEN_WIDTH // 2 - panel_w // 2
            panel_y = 80
            draw_panel(screen, panel_x, panel_y, panel_w, panel_h)

            draw_text(screen, "CONFIGURAR HEURÍSTICA", config_title_font, COLOR_PLAYER, SCREEN_WIDTH // 2, 165)
            draw_text(screen, "Elige una sola modalidad de búsqueda automática.", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 220)
            draw_text(screen, "Luego pulsa INICIAR para ejecutar autoplay desde el nivel 1.", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 245)
            draw_text(screen, "Los puntos se recolectan pasando por las casillas con 'S'.", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 270)

            draw_text(screen, "Modo:", menu_font, COLOR_TEXT, SCREEN_WIDTH // 2, 315)
            draw_button(
                screen,
                "MINIMIZAR TIEMPO",
                menu_font,
                SCREEN_WIDTH // 2 - 300,
                360,
                250,
                58,
                mouse_pos,
                active=(selected_mode == "min_time")
            )
            draw_button(
                screen,
                "MINIMIZAR MOVS.",
                menu_font,
                SCREEN_WIDTH // 2,
                360,
                250,
                58,
                mouse_pos,
                active=(selected_mode == "min_moves")
            )
            draw_button(
                screen,
                "MAXIMIZAR PUNTOS",
                menu_font,
                SCREEN_WIDTH // 2 + 300,
                360,
                250,
                58,
                mouse_pos,
                active=(selected_mode == "max_points")
            )

            draw_button(screen, "INICIAR", menu_font, SCREEN_WIDTH // 2, 565, 320, 65, mouse_pos)
            draw_text(screen, "Presiona ESC para volver al menú", small_font, (180, 180, 180), SCREEN_WIDTH // 2, 635)
            draw_text(screen, f"Seleccionado: {get_heuristic_label(selected_mode)}", small_font, COLOR_TARGET, SCREEN_WIDTH // 2, 690)

        elif current_state == STATE_AUTOPLAY:
            game.draw(screen)
            draw_text(screen, "AUTOPLAY ACTIVADO", menu_font, COLOR_PLAYER, SCREEN_WIDTH // 2, 80)
            draw_text(screen, f"Nivel automático: {auto_state['level']}", small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 110)
            draw_text(screen, auto_state['message'], small_font, COLOR_TEXT, SCREEN_WIDTH // 2, 135)
            if auto_state['completion_text']:
                draw_text(screen, auto_state['completion_text'], small_font, COLOR_TARGET, SCREEN_WIDTH // 2, 160)

            if auto_state['searching']:
                draw_text(screen, "Buscando solución... Esto puede tomar algunos segundos.", small_font, COLOR_BTN_HOVER, SCREEN_WIDTH // 2, 190)

            if auto_state['path']:
                draw_text(screen, f"Pasos: {len(auto_state['path'])}  Nodo(s): {auto_state['nodes']}", small_font, COLOR_TARGET, SCREEN_WIDTH // 2, 215)

            draw_text(screen, "Presiona ESC para detener autoplay", small_font, (180, 180, 180), SCREEN_WIDTH // 2, 710)

            if auto_state['searching']:
                limits = LEVEL_SEARCH_LIMITS.get(selected_mode, LEVEL_SEARCH_LIMITS['min_time'])
                solution, nodes, final_state = find_greedy_solution(
                    game,
                    selected_mode,
                    max_nodes=limits['max_nodes'],
                    max_time=limits['max_time'],
                    max_depth=limits['max_depth']
                )
                auto_state['nodes'] = nodes
                auto_state['final_state'] = final_state
                auto_state['searching'] = False

                if solution:
                    auto_state['path'] = solution
                    auto_state['step'] = 0
                    auto_state['message'] = f"Solución encontrada: {len(solution)} pasos"
                    auto_state['next_move_time'] = pygame.time.get_ticks()
                else:
                    auto_state['message'] = f"No se encontró solución en este nivel ({nodes} nodos). Presiona ESC."
                    auto_state['path'] = []

            elif pygame.time.get_ticks() >= auto_state['next_move_time']:

                # --- NIVEL COMPLETADO ---
                if game.level_won:
                    if auto_state['level_complete_until'] == 0:
                        route_str = path_to_string(auto_state['path'])
                        _, cost_str = calculate_solution_cost(
                            auto_state['final_state'],
                            auto_state['path'],
                            selected_mode
                        )

                        print(f"[Nivel {auto_state['level']}] Ruta: {route_str}")
                        print(f"[Nivel {auto_state['level']}] Costo: {cost_str}")
                        print(f"[Nivel {auto_state['level']}] Nodos: {auto_state['nodes']}")
                        print()

                        auto_state['message'] = f"✔ Nivel {auto_state['level']} completado"
                        auto_state['completion_text'] = cost_str
                        auto_state['level_complete_until'] = pygame.time.get_ticks() + 1800
                        auto_state['path'] = []

                    elif pygame.time.get_ticks() >= auto_state['level_complete_until']:
                        auto_state['level_complete_until'] = 0
                        auto_state['completion_text'] = ""

                        if auto_state['level'] < 50:
                            auto_state['level'] += 1
                            game.current_level_idx = auto_state['level']
                            game.load_level(auto_state['level'])
                            auto_state['searching'] = True
                            auto_state['message'] = f"Nivel {auto_state['level']}..."
                            auto_state['step'] = 0
                            auto_state['final_state'] = None
                        else:
                            auto_state['message'] = "Autoplay completado"
                            auto_state['completion_text'] = "✔ Todos los niveles"
                            print("[Autoplay] Completado")

                # --- EJECUTAR RUTA ---
                elif auto_state['path'] and auto_state['step'] < len(auto_state['path']):
                    dr, dc = auto_state['path'][auto_state['step']]
                    game.move(dr, dc)
                    auto_state['step'] += 1
                    auto_state['next_move_time'] = pygame.time.get_ticks() + 180

                else:
                    auto_state['message'] = "No se pudo ejecutar la ruta"
                    auto_state['path'] = []

            elif not auto_state['path'] and not auto_state['searching'] and not game.level_won:
                auto_state['message'] = "No se puede resolver este nivel automáticamente."

        elif current_state == STATE_LEVEL_SELECT:
            draw_text(screen, "SELECCIONA UN NIVEL", menu_font, COLOR_TEXT, SCREEN_WIDTH // 2, 100)

            margin, size, gap = 100, 50, 15
            for i in range(50):
                lvl_num = i + 1
                col = i % 10
                row = i // 10
                x = margin + col * (size + gap)
                y = 200 + row * (size + gap)

                rect = pygame.Rect(x, y, size, size)

                if rect.collidepoint(mouse_pos):
                    color = COLOR_PLAYER
                elif lvl_num == game.current_level_idx:
                    color = COLOR_TARGET
                else:
                    color = COLOR_BTN

                pygame.draw.rect(screen, color, rect, border_radius=5)
                draw_text(screen, str(lvl_num), level_num_font, COLOR_TEXT, x + size // 2, y + size // 2)

            draw_text(screen, "Presiona ESC para volver al menú", small_font, (150, 150, 150), SCREEN_WIDTH // 2, 700)

        elif current_state == STATE_PLAYING:
            game.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
