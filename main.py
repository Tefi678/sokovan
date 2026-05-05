import heapq
import pygame
import sys
import time

from constants import *
from engine import SokobanEngine


MODOS_HEURISTICA = {
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

LIMITES_BUSQUEDA_NIVELES = {
    "min_time": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
    "min_moves": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
    "max_points": {"max_nodes": 500000, "max_time": 45.0, "max_depth": 3000},
}


def dibujar_texto(pantalla, texto, fuente, color, x, y):
    superficie = fuente.render(texto, True, color)
    rectangulo = superficie.get_rect(center=(x, y))
    pantalla.blit(superficie, rectangulo)


def dibujar_boton(pantalla, texto, fuente, x, y, ancho, alto, posicion_mouse, activo=False):
    rectangulo = pygame.Rect(x - ancho // 2, y - alto // 2, ancho, alto)
    if activo:
        color = COLOR_BTN_ACTIVE
    else:
        color = COLOR_BTN_HOVER if rectangulo.collidepoint(posicion_mouse) else COLOR_BTN
    pygame.draw.rect(pantalla, color, rectangulo, border_radius=10)
    pygame.draw.rect(pantalla, COLOR_TEXT, rectangulo, 2, border_radius=10)
    dibujar_texto(pantalla, texto, fuente, COLOR_TEXT, x, y)
    return rectangulo


def dibujar_panel(pantalla, x, y, ancho, alto):
    rectangulo = pygame.Rect(x, y, ancho, alto)
    pygame.draw.rect(pantalla, (40, 40, 55), rectangulo, border_radius=20)
    pygame.draw.rect(pantalla, COLOR_BTN, rectangulo, 2, border_radius=20)


def obtener_etiqueta_heuristica(modo):
    return MODOS_HEURISTICA.get(modo, MODOS_HEURISTICA["min_time"])["label"]


def es_maximizador(modo):
    return MODOS_HEURISTICA.get(modo, MODOS_HEURISTICA["min_time"])["goal"] == "max"


def evaluar_heuristica(motor, modo, profundidad=0):
    posiciones_cajas = {tuple(caja) for caja in motor.boxes}
    posiciones_objetivos = [tuple(objetivo) for objetivo in motor.targets]
    puntos_recolectados = {tuple(punto) for punto in motor.points_collected}

    total_puntos = len(motor.points_coords)
    puntos_recolectados_count = len(puntos_recolectados)
    puntos_restantes = total_puntos - puntos_recolectados_count

    distancia_cajas = 0
    if posiciones_objetivos:
        for caja in posiciones_cajas:
            distancia_cajas += min(
                abs(caja[0] - objetivo[0]) + abs(caja[1] - objetivo[1])
                for objetivo in posiciones_objetivos
            )

    jugador_a_caja = 0
    if posiciones_cajas:
        posicion_jugador = tuple(motor.player_pos)
        jugador_a_caja = min(
            abs(posicion_jugador[0] - caja[0]) + abs(posicion_jugador[1] - caja[1])
            for caja in posiciones_cajas
        )

    if modo == "min_moves":
        return profundidad * 20 + distancia_cajas * 25 + jugador_a_caja * 8

    if modo == "max_points":
        # Ahora sí: más puntos = mejor puntaje
        # La prioridad ya se invierte en prioridad_desde_puntaje(),
        # así que aquí debe ser un valor mayor para estados mejores.
        return (
            puntos_recolectados_count * 2000
            - distancia_cajas * 10
            - jugador_a_caja * 3
            - profundidad * 5
        )

    return profundidad * 15 + distancia_cajas * 20 + jugador_a_caja * 6

def prioridad_desde_puntaje(puntaje, modo):
    return -puntaje if es_maximizador(modo) else puntaje


def es_mejor(puntaje, mejor_puntaje, modo):
    if es_maximizador(modo):
        return puntaje > mejor_puntaje
    return puntaje < mejor_puntaje


def ruta_a_cadena(ruta):
    mapa_direcciones = {(-1, 0): 'U', (1, 0): 'D', (0, -1): 'L', (0, 1): 'R'}
    return '-'.join(mapa_direcciones.get(movimiento, '?') for movimiento in ruta)


def encontrar_solucion_voraz(motor_inicial, modo, max_nodos=100000, max_tiempo=20.0, max_profundidad=1000):
    direcciones = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    tiempo_inicio = time.time()

    cola_prioridad = []
    id_nodo = 0
    nodos_explorados = 0

    puntaje_inicial = evaluar_heuristica(motor_inicial, modo, profundidad=0)
    heapq.heappush(
        cola_prioridad,
        (prioridad_desde_puntaje(puntaje_inicial, modo), 0, id_nodo, motor_inicial.clone(), [])
    )

    mejor_visto = {motor_inicial.state_key(): puntaje_inicial}

    mejor_solucion = None
    mejor_estado = None
    mejor_puntaje = float("-inf")

    while cola_prioridad and nodos_explorados < max_nodos and (time.time() - tiempo_inicio) < max_tiempo:
        _, profundidad, _, nodo, ruta = heapq.heappop(cola_prioridad)
        nodos_explorados += 1

        if nodo.level_won:
            if modo == "max_points":
                puntaje_actual = len(nodo.points_collected)

                if puntaje_actual > mejor_puntaje:
                    mejor_puntaje = puntaje_actual
                    mejor_solucion = ruta
                    mejor_estado = nodo

                # NO hacemos return, seguimos buscando mejores
            else:
                return ruta, nodos_explorados, nodo

        if profundidad >= max_profundidad:
            continue

        for dr, dc in direcciones:
            hijo = nodo.clone()
            hijo.move(dr, dc)

            if hijo.player_pos == nodo.player_pos and hijo.boxes == nodo.boxes:
                continue

            if hijo.is_dead:
                continue

            clave = hijo.state_key()
            puntaje = evaluar_heuristica(hijo, modo, profundidad + 1)

            if clave in mejor_visto and not es_mejor(puntaje, mejor_visto[clave], modo):
                continue

            mejor_visto[clave] = puntaje

            id_nodo += 1
            heapq.heappush(
                cola_prioridad,
                (prioridad_desde_puntaje(puntaje, modo), profundidad + 1, id_nodo, hijo, ruta + [(dr, dc)])
            )

    if modo == "max_points" and mejor_solucion is not None:
        return mejor_solucion, nodos_explorados, mejor_estado

    return None, nodos_explorados, None


def calcular_costo_solucion(estado_final, ruta, modo):
    if modo == "min_moves":
        return len(ruta), f"Movimientos: {len(ruta)}"

    if modo == "min_time":
        tiempo_estimado_ms = len(ruta) * 130
        tiempo_estimado_s = tiempo_estimado_ms / 1000
        return tiempo_estimado_s, f"Tiempo estimado: {tiempo_estimado_s:.2f}s ({len(ruta)} pasos)"

    if modo == "max_points":
        if estado_final:
            puntos_recolectados = len(estado_final.points_collected)
            total_puntos = len(estado_final.points_coords)
            return puntos_recolectados, f"Puntos: {puntos_recolectados}/{total_puntos} | Pasos: {len(ruta)}"
        return 0, f"Pasos: {len(ruta)}"

    return 0, f"Pasos: {len(ruta)}"


def main():
    pygame.init()
    pantalla = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Sokoban Ultimate Edition")
    reloj = pygame.time.Clock()

    fondo = pygame.image.load("assets/bg1.png")
    fondo = pygame.transform.scale(fondo, (SCREEN_WIDTH, SCREEN_HEIGHT))

    fuente_titulo = pygame.font.SysFont("Verdana", 80, bold=True)
    fuente_titulo_config = pygame.font.SysFont("Verdana", 46, bold=True)
    fuente_menu = pygame.font.SysFont("Verdana", 25, bold=True)
    fuente_pequena = pygame.font.SysFont("Verdana", 18)
    fuente_numero_nivel = pygame.font.SysFont("Verdana", 20, bold=True)

    juego = SokobanEngine()
    estado_actual = STATE_MENU
    modo_seleccionado = "min_time"

    estado_auto = {
        'ruta': [],
        'paso': 0,
        'buscando': False,
        'nivel': 1,
        'mensaje': "",
        'tiempo_siguiente_movimiento': 0,
        'nodos': 0,
        'estado_final': None,
        'tiempo_fin_nivel': 0,
        'pendiente_siguiente_nivel': False,
        'texto_completado': "",
    }

    while True:
        posicion_mouse = pygame.mouse.get_pos()

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if estado_actual == STATE_MENU:
                if evento.type == pygame.MOUSEBUTTONDOWN:
                    btn_jugar = pygame.Rect(SCREEN_WIDTH // 2 - 100, 330, 200, 50)
                    btn_heuristica = pygame.Rect(SCREEN_WIDTH // 2 - 100, 410, 200, 50)
                    btn_niveles = pygame.Rect(SCREEN_WIDTH // 2 - 100, 490, 200, 50)

                    if btn_jugar.collidepoint(evento.pos):
                        estado_actual = STATE_PLAYING
                    elif btn_heuristica.collidepoint(evento.pos):
                        estado_actual = STATE_HEURISTIC_CONFIG
                    elif btn_niveles.collidepoint(evento.pos):
                        estado_actual = STATE_LEVEL_SELECT

            elif estado_actual == STATE_HEURISTIC_CONFIG:
                if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
                    estado_actual = STATE_MENU

                if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                    btn_min_tiempo = pygame.Rect(SCREEN_WIDTH // 2 - 390, 360 - 28, 250, 58)
                    btn_min_movs = pygame.Rect(SCREEN_WIDTH // 2 - 125, 360 - 28, 250, 58)
                    btn_max_puntos = pygame.Rect(SCREEN_WIDTH // 2 + 140, 360 - 28, 250, 58)
                    btn_iniciar = pygame.Rect(SCREEN_WIDTH // 2 - 140, 565 - 30, 280, 60)

                    if btn_min_tiempo.collidepoint(evento.pos):
                        modo_seleccionado = "min_time"
                    elif btn_min_movs.collidepoint(evento.pos):
                        modo_seleccionado = "min_moves"
                    elif btn_max_puntos.collidepoint(evento.pos):
                        modo_seleccionado = "max_points"
                    elif btn_iniciar.collidepoint(evento.pos):
                        estado_actual = STATE_AUTOPLAY
                        estado_auto['nivel'] = 1
                        estado_auto['paso'] = 0
                        estado_auto['ruta'] = []
                        estado_auto['buscando'] = True
                        estado_auto['mensaje'] = f"Iniciando autoplay desde nivel 1: {obtener_etiqueta_heuristica(modo_seleccionado)}"
                        estado_auto['tiempo_siguiente_movimiento'] = pygame.time.get_ticks()
                        estado_auto['nodos'] = 0
                        estado_auto['estado_final'] = None
                        estado_auto['tiempo_fin_nivel'] = 0
                        estado_auto['pendiente_siguiente_nivel'] = False
                        estado_auto['texto_completado'] = ""
                        juego.current_level_idx = 1
                        juego.load_level(1)

            elif estado_actual == STATE_AUTOPLAY:
                if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
                    estado_actual = STATE_MENU

            elif estado_actual == STATE_LEVEL_SELECT:
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_ESCAPE:
                        estado_actual = STATE_MENU

                if evento.type == pygame.MOUSEBUTTONDOWN:
                    margen, tamano, espacio = 100, 50, 15
                    for i in range(50):
                        col = i % 10
                        row = i // 10
                        x = margen + col * (tamano + espacio)
                        y = 200 + row * (tamano + espacio)
                        rect_nivel = pygame.Rect(x, y, tamano, tamano)

                        if rect_nivel.collidepoint(evento.pos):
                            juego.current_level_idx = i + 1
                            juego.load_level(juego.current_level_idx)
                            estado_actual = STATE_MENU

            elif estado_actual == STATE_PLAYING:
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_ESCAPE:
                        estado_actual = STATE_MENU
                    if evento.key == pygame.K_r:
                        juego.load_level(juego.current_level_idx)
                    if evento.key == pygame.K_u:
                        juego.undo()

                    if not juego.level_won and not juego.is_dead:
                        if evento.key == pygame.K_UP:
                            juego.move(-1, 0)
                        if evento.key == pygame.K_DOWN:
                            juego.move(1, 0)
                        if evento.key == pygame.K_LEFT:
                            juego.move(0, -1)
                        if evento.key == pygame.K_RIGHT:
                            juego.move(0, 1)

                    if juego.level_won and evento.key == pygame.K_SPACE:
                        if juego.current_level_idx < 50:
                            juego.current_level_idx += 1
                            juego.load_level(juego.current_level_idx)
                        else:
                            print("¡Felicidades! Has completado todos los niveles.")
                            juego.draw_overlay(pantalla, "¡ERES UN MAESTRO!", f"Movs Totales: {juego.moves_count} | Gracias por jugar")

        pantalla.blit(fondo, (0, 0))

        if estado_actual == STATE_MENU:
            panel_ancho, panel_alto = 760, 500
            panel_x = SCREEN_WIDTH // 2 - panel_ancho // 2
            panel_y = 100
            dibujar_panel(pantalla, panel_x, panel_y, panel_ancho, panel_alto)

            dibujar_texto(pantalla, "SOKOBAN", fuente_titulo, COLOR_PLAYER, SCREEN_WIDTH // 2, 170)
            dibujar_texto(pantalla, "Creado por: huevoscartoon", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 215)
            dibujar_boton(pantalla, "JUGAR", fuente_menu, SCREEN_WIDTH // 2, 340, 260, 65, posicion_mouse)
            dibujar_boton(pantalla, "HEURÍSTICA", fuente_menu, SCREEN_WIDTH // 2, 425, 260, 65, posicion_mouse)
            dibujar_boton(pantalla, "NIVELES", fuente_menu, SCREEN_WIDTH // 2, 510, 260, 65, posicion_mouse)
            dibujar_texto(pantalla, f"Nivel Seleccionado: {juego.current_level_idx}", fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 580)
            dibujar_texto(pantalla, f"Heurística: {obtener_etiqueta_heuristica(modo_seleccionado)}", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 610)

        elif estado_actual == STATE_HEURISTIC_CONFIG:
            panel_ancho, panel_alto = 900, 620
            panel_x = SCREEN_WIDTH // 2 - panel_ancho // 2
            panel_y = 80
            dibujar_panel(pantalla, panel_x, panel_y, panel_ancho, panel_alto)

            dibujar_texto(pantalla, "CONFIGURAR HEURÍSTICA", fuente_titulo_config, COLOR_PLAYER, SCREEN_WIDTH // 2, 165)
            dibujar_texto(pantalla, "Elige una sola modalidad de búsqueda automática.", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 220)
            dibujar_texto(pantalla, "Luego pulsa INICIAR para ejecutar autoplay desde el nivel 1.", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 245)
            dibujar_texto(pantalla, "Los puntos se recolectan pasando por las casillas con 'S'.", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 270)

            dibujar_texto(pantalla, "Modo:", fuente_menu, COLOR_TEXT, SCREEN_WIDTH // 2, 315)
            dibujar_boton(
                pantalla,
                "MINIMIZAR TIEMPO",
                fuente_menu,
                SCREEN_WIDTH // 2 - 300,
                360,
                250,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "min_time")
            )
            dibujar_boton(
                pantalla,
                "MINIMIZAR MOVS.",
                fuente_menu,
                SCREEN_WIDTH // 2,
                360,
                250,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "min_moves")
            )
            dibujar_boton(
                pantalla,
                "MAXIMIZAR PUNTOS",
                fuente_menu,
                SCREEN_WIDTH // 2 + 300,
                360,
                250,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "max_points")
            )

            dibujar_boton(pantalla, "INICIAR", fuente_menu, SCREEN_WIDTH // 2, 565, 320, 65, posicion_mouse)
            dibujar_texto(pantalla, "Presiona ESC para volver al menú", fuente_pequena, (180, 180, 180), SCREEN_WIDTH // 2, 635)
            dibujar_texto(pantalla, f"Seleccionado: {obtener_etiqueta_heuristica(modo_seleccionado)}", fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 690)

        elif estado_actual == STATE_AUTOPLAY:
            juego.draw(pantalla)
            dibujar_texto(pantalla, "AUTOPLAY ACTIVADO", fuente_menu, COLOR_PLAYER, SCREEN_WIDTH // 2, 80)
            dibujar_texto(pantalla, f"Nivel automático: {estado_auto['nivel']}", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 110)
            dibujar_texto(pantalla, estado_auto['mensaje'], fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 135)
            if estado_auto['texto_completado']:
                dibujar_texto(pantalla, estado_auto['texto_completado'], fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 160)

            if estado_auto['buscando']:
                dibujar_texto(pantalla, "Buscando solución... Esto puede tomar algunos segundos.", fuente_pequena, COLOR_BTN_HOVER, SCREEN_WIDTH // 2, 190)

            if estado_auto['ruta']:
                dibujar_texto(pantalla, f"Pasos: {len(estado_auto['ruta'])}  Nodo(s): {estado_auto['nodos']}", fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 215)

            dibujar_texto(pantalla, "Presiona ESC para detener autoplay", fuente_pequena, (180, 180, 180), SCREEN_WIDTH // 2, 710)

            if estado_auto['buscando']:
                limites = LIMITES_BUSQUEDA_NIVELES.get(modo_seleccionado, LIMITES_BUSQUEDA_NIVELES['min_time'])
                solucion, nodos, estado_final = encontrar_solucion_voraz(
                    juego,
                    modo_seleccionado,
                    max_nodos=limites['max_nodes'],
                    max_tiempo=limites['max_time'],
                    max_profundidad=limites['max_depth']
                )
                estado_auto['nodos'] = nodos
                estado_auto['estado_final'] = estado_final
                estado_auto['buscando'] = False

                if solucion:
                    estado_auto['ruta'] = solucion
                    estado_auto['paso'] = 0
                    estado_auto['mensaje'] = f"Solución encontrada: {len(solucion)} pasos"
                    estado_auto['tiempo_siguiente_movimiento'] = pygame.time.get_ticks()
                else:
                    estado_auto['mensaje'] = f"No se encontró solución en este nivel ({nodos} nodos). Presiona ESC."
                    estado_auto['ruta'] = []

            elif pygame.time.get_ticks() >= estado_auto['tiempo_siguiente_movimiento']:

                # --- NIVEL COMPLETADO ---
                if juego.level_won:
                    if estado_auto['tiempo_fin_nivel'] == 0:
                        cadena_ruta = ruta_a_cadena(estado_auto['ruta'])
                        _, cadena_costo = calcular_costo_solucion(
                            estado_auto['estado_final'],
                            estado_auto['ruta'],
                            modo_seleccionado
                        )

                        print(f"[Nivel {estado_auto['nivel']}] Ruta: {cadena_ruta}")
                        print(f"[Nivel {estado_auto['nivel']}] Costo: {cadena_costo}")
                        print(f"[Nivel {estado_auto['nivel']}] Nodos: {estado_auto['nodos']}")
                        print()

                        estado_auto['mensaje'] = f"✔ Nivel {estado_auto['nivel']} completado"
                        estado_auto['texto_completado'] = cadena_costo
                        estado_auto['tiempo_fin_nivel'] = pygame.time.get_ticks() + 1800
                        estado_auto['ruta'] = []

                    elif pygame.time.get_ticks() >= estado_auto['tiempo_fin_nivel']:
                        estado_auto['tiempo_fin_nivel'] = 0
                        estado_auto['texto_completado'] = ""

                        if estado_auto['nivel'] < 50:
                            estado_auto['nivel'] += 1
                            juego.current_level_idx = estado_auto['nivel']
                            juego.load_level(estado_auto['nivel'])
                            estado_auto['buscando'] = True
                            estado_auto['mensaje'] = f"Nivel {estado_auto['nivel']}..."
                            estado_auto['paso'] = 0
                            estado_auto['estado_final'] = None
                        else:
                            estado_auto['mensaje'] = "Autoplay completado"
                            estado_auto['texto_completado'] = "✔ Todos los niveles"
                            print("[Autoplay] Completado")

                # --- EJECUTAR RUTA ---
                elif estado_auto['ruta'] and estado_auto['paso'] < len(estado_auto['ruta']):
                    dr, dc = estado_auto['ruta'][estado_auto['paso']]
                    juego.move(dr, dc)
                    estado_auto['paso'] += 1
                    estado_auto['tiempo_siguiente_movimiento'] = pygame.time.get_ticks() + 180

                else:
                    estado_auto['mensaje'] = "No se pudo ejecutar la ruta"
                    estado_auto['ruta'] = []

            elif not estado_auto['ruta'] and not estado_auto['buscando'] and not juego.level_won:
                estado_auto['mensaje'] = "No se puede resolver este nivel automáticamente."

        elif estado_actual == STATE_LEVEL_SELECT:
            dibujar_texto(pantalla, "SELECCIONA UN NIVEL", fuente_menu, COLOR_TEXT, SCREEN_WIDTH // 2, 100)

            margen, tamano, espacio = 100, 50, 15
            for i in range(50):
                numero_nivel = i + 1
                col = i % 10
                row = i // 10
                x = margen + col * (tamano + espacio)
                y = 200 + row * (tamano + espacio)

                rectangulo = pygame.Rect(x, y, tamano, tamano)

                if rectangulo.collidepoint(posicion_mouse):
                    color = COLOR_PLAYER
                elif numero_nivel == juego.current_level_idx:
                    color = COLOR_TARGET
                else:
                    color = COLOR_BTN

                pygame.draw.rect(pantalla, color, rectangulo, border_radius=5)
                dibujar_texto(pantalla, str(numero_nivel), fuente_numero_nivel, COLOR_TEXT, x + tamano // 2, y + tamano // 2)

            dibujar_texto(pantalla, "Presiona ESC para volver al menú", fuente_pequena, (150, 150, 150), SCREEN_WIDTH // 2, 700)

        elif estado_actual == STATE_PLAYING:
            juego.draw(pantalla)

        pygame.display.flip()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()