import heapq
import pygame
import sys
import time
import threading
from collections import deque

from constants import *
from engine import SokobanEngine


# -----------------------------------------------------------------------------
# MODOS DE BÚSQUEDA
# -----------------------------------------------------------------------------
# min_time  -> ruta más rápida (penaliza mucho el terreno lento como miel)
# min_moves -> ruta con menos movimientos (ignora el costo del terreno en la
#              medida de lo posible; prioriza ahorrar pasos)
# max_points-> primero recolectar todas las S, y luego completar el nivel
# -----------------------------------------------------------------------------
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

# Límites más realistas para que el juego no se congele.
# Ajustados para mantener el estilo de búsqueda voraz sin explotar el tiempo.
LIMITES_BUSQUEDA_NIVELES = {
    "min_time": {"max_nodes": 150000, "max_time": 10.0, "max_depth": 400},
    "min_moves": {"max_nodes": 150000, "max_time": 10.0, "max_depth": 400},
    "max_points": {"max_nodes": 250000, "max_time": 20.0, "max_depth": 1000},
}


# -----------------------------------------------------------------------------
# DIBUJO UI
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# UTILIDADES DE HEURÍSTICA
# -----------------------------------------------------------------------------
def obtener_etiqueta_heuristica(modo):
    return MODOS_HEURISTICA.get(modo, MODOS_HEURISTICA["min_time"])["label"]


def es_maximizador(modo):
    return MODOS_HEURISTICA.get(modo, MODOS_HEURISTICA["min_time"])["goal"] == "max"


def puntos_key(motor):
    return tuple(sorted(tuple(p) for p in getattr(motor, "points_collected", [])))


def puntos_totales(motor):
    return len(getattr(motor, "points_coords", []))


def puntos_pendientes(motor):
    coords = [tuple(p) for p in getattr(motor, "points_coords", [])]
    recogidos = set(puntos_key(motor))
    return [p for p in coords if p not in recogidos]


# -----------------------------------------------------------------------------
# LECTURA DEL TABLERO
# -----------------------------------------------------------------------------
# El motor puede exponer el mapa con distintos nombres según tu implementación.
# Estas funciones intentan encontrarlo sin romper si cambia el atributo.
# -----------------------------------------------------------------------------
def obtener_tablero(motor):
    candidatos = [
        "board",
        "grid",
        "map",
        "level_map",
        "current_map",
        "tiles",
        "level_data",
    ]

    for nombre in candidatos:
        if not hasattr(motor, nombre):
            continue

        tablero = getattr(motor, nombre)
        if tablero is None:
            continue

        if isinstance(tablero, str):
            return [list(line) for line in tablero.splitlines() if line]

        if isinstance(tablero, (list, tuple)) and tablero:
            primera = tablero[0]
            if isinstance(primera, str):
                return [list(fila) for fila in tablero]
            if isinstance(primera, (list, tuple)):
                return [list(fila) for fila in tablero]

    return None


def celda_en(motor, pos):
    tablero = obtener_tablero(motor)
    if tablero is None:
        return None

    r, c = pos
    if r < 0 or c < 0 or r >= len(tablero):
        return None
    if c >= len(tablero[r]):
        return None
    return tablero[r][c]


def es_paso_valido(celda):
    # Los caracteres de pared nunca deben entrar al camino.
    return celda is not None and celda != "W"


def costo_terreno(celda, modo):
    # Costo al entrar en una celda.
    # - min_time: evita miel / hielo / lava / huecos porque encarecen el trayecto.
    # - min_moves: ignora en gran medida el terreno, porque solo importa el número
    #   de movimientos. La miel no debe asustar al algoritmo aquí.
    # - max_points: prioriza puntos; el terreno importa poco hasta juntar todas las S.
    if celda is None:
        return float("inf")

    if celda == "W":
        return float("inf")

    if modo == "min_moves":
        if celda in {"H", "M", "I", "L", ".", "S", "T", "P", "B"}:
            return 1
        return 1

    if modo == "max_points":
        if celda in {"H", "M", "I", "L"}:
            return 1
        return 1

    # min_time
    if celda == "M":
        return 8
    if celda == "I":
        return 4
    if celda == "L":
        return 10
    if celda == "H":
        return 12
    return 1


def obtener_posiciones_objetivo(motor, modo):
    # Para min_time/min_moves queremos resolver cajas -> targets.
    # Para max_points, primero nos enfocamos en las S restantes.
    if modo == "max_points":
        pendientes = puntos_pendientes(motor)
        if pendientes:
            return pendientes

    return [tuple(obj) for obj in getattr(motor, "targets", [])]


def distancia_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def es_deadlock_simple(motor, caja_pos):
    # Detecta si una caja está en una posición de deadlock simple (esquina sin target)
    targets = {tuple(t) for t in getattr(motor, "targets", [])}
    if caja_pos in targets:
        return False
    r, c = caja_pos
    tablero = obtener_tablero(motor)
    if tablero is None:
        return False
    rows = len(tablero)
    cols = len(tablero[0]) if tablero else 0
    up = (r-1 < 0) or tablero[r-1][c] == 'W'
    down = (r+1 >= rows) or tablero[r+1][c] == 'W'
    left = (c-1 < 0) or tablero[r][c-1] == 'W'
    right = (c+1 >= cols) or tablero[r][c+1] == 'W'
    return (up and left) or (up and right) or (down and left) or (down and right)


def distancia_ponderada(motor, inicio, objetivos, modo, bloqueos=None):
    # Dijkstra simple para estimar costo de ruta hacia el objetivo más cercano.
    # Es más caro que Manhattan, pero permite distinguir miel / hielo / lava.
    if not objetivos:
        return 0

    tablero = obtener_tablero(motor)
    if tablero is None:
        return min(distancia_manhattan(inicio, obj) for obj in objetivos)

    objetivos = {tuple(o) for o in objetivos}
    bloqueos = set(bloqueos or [])
    filas = len(tablero)

    def en_rango(r, c):
        return 0 <= r < filas and 0 <= c < len(tablero[r])

    visitados = {}
    cola = [(0, tuple(inicio))]

    while cola:
        costo_actual, (r, c) = heapq.heappop(cola)
        if (r, c) in visitados and visitados[(r, c)] <= costo_actual:
            continue
        visitados[(r, c)] = costo_actual

        if (r, c) in objetivos:
            return costo_actual

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if not en_rango(nr, nc):
                continue

            if (nr, nc) in bloqueos and (nr, nc) not in objetivos:
                continue

            celda = tablero[nr][nc]
            if not es_paso_valido(celda):
                continue

            paso = costo_terreno(celda, modo)
            if paso == float("inf"):
                continue

            nuevo_costo = costo_actual + paso
            if (nr, nc) not in visitados or nuevo_costo < visitados[(nr, nc)]:
                heapq.heappush(cola, (nuevo_costo, (nr, nc)))

    # Si no se puede calcular una ruta exacta, usamos Manhattan como respaldo.
    return min(distancia_manhattan(inicio, obj) for obj in objetivos)


def simular_movimiento(motor, inicio, dr, dc, bloqueos=None, modo=None):
    tablero = obtener_tablero(motor)
    if tablero is None:
        return None, None, None

    filas = len(tablero)
    cols = len(tablero[0]) if tablero else 0

    def en_rango(r, c):
        return 0 <= r < filas and 0 <= c < cols

    bloqueos = set(bloqueos or [])
    nr, nc = inicio[0] + dr, inicio[1] + dc

    if not en_rango(nr, nc):
        return None, None, None

    if (nr, nc) in bloqueos:
        return None, None, None

    celda = tablero[nr][nc]
    if not es_paso_valido(celda):
        return None, None, None

    posicion = (nr, nc)
    costo = costo_terreno(celda, modo) if modo else 1

    while celda == 'I':
        siguiente = (posicion[0] + dr, posicion[1] + dc)
        if not en_rango(*siguiente) or siguiente in bloqueos:
            break
        siguiente_celda = tablero[siguiente[0]][siguiente[1]]
        if siguiente_celda == 'W' or not es_paso_valido(siguiente_celda):
            break
        posicion = siguiente
        celda = siguiente_celda
        costo += costo_terreno(celda, modo) if modo else 0
        if celda != 'I':
            break

    return posicion, celda, costo


def distancia_min_moves(motor, inicio, objetivos, bloqueos=None):
    if not objetivos:
        return 0

    tablero = obtener_tablero(motor)
    if tablero is None:
        return min(distancia_manhattan(inicio, obj) for obj in objetivos)

    objetivos = {tuple(o) for o in objetivos}
    bloqueos = set(bloqueos or [])
    filas = len(tablero)
    cols = len(tablero[0]) if tablero else 0

    def en_rango(r, c):
        return 0 <= r < filas and 0 <= c < cols

    visitados = {tuple(inicio): 0}
    cola = deque([(0, tuple(inicio))])

    while cola:
        movimientos, pos = cola.popleft()
        if pos in objetivos:
            return movimientos

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            siguiente, _, _ = simular_movimiento(motor, pos, dr, dc, bloqueos, modo="min_moves")
            if siguiente is None:
                continue
            if siguiente not in visitados:
                visitados[siguiente] = movimientos + 1
                cola.append((movimientos + 1, siguiente))

    return min(distancia_manhattan(inicio, obj) for obj in objetivos)


def distancia_min_time(motor, inicio, objetivos, bloqueos=None):
    if not objetivos:
        return 0

    tablero = obtener_tablero(motor)
    if tablero is None:
        return min(distancia_manhattan(inicio, obj) for obj in objetivos)

    objetivos = {tuple(o) for o in objetivos}
    bloqueos = set(bloqueos or [])
    filas = len(tablero)
    cols = len(tablero[0]) if tablero else 0

    def en_rango(r, c):
        return 0 <= r < filas and 0 <= c < cols

    visitados = {}
    cola = [(0, tuple(inicio))]

    while cola:
        costo_actual, pos = heapq.heappop(cola)
        if pos in visitados and visitados[pos] <= costo_actual:
            continue
        visitados[pos] = costo_actual

        if pos in objetivos:
            return costo_actual

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            siguiente, celda, costo_movimiento = simular_movimiento(motor, pos, dr, dc, bloqueos, modo="min_time")
            if siguiente is None:
                continue
            if costo_movimiento is None or costo_movimiento == float("inf"):
                continue
            nuevo_costo = costo_actual + costo_movimiento
            if siguiente not in visitados or nuevo_costo < visitados[siguiente]:
                heapq.heappush(cola, (nuevo_costo, siguiente))

    return min(distancia_manhattan(inicio, obj) for obj in objetivos)


# -----------------------------------------------------------------------------
# HEURÍSTICA PRINCIPAL
# -----------------------------------------------------------------------------
def evaluar_heuristica(motor, modo):
    # Cada modo devuelve solo la estimación heurística h(n).
    # No usamos g(n) ni profundidad en la prioridad de la cola, para mantener
    # la búsqueda como Greedy Best-First Search pura.
    posiciones_cajas = {tuple(caja) for caja in getattr(motor, "boxes", [])}
    posiciones_objetivos = [tuple(objetivo) for objetivo in getattr(motor, "targets", [])]

    px, py = tuple(getattr(motor, "player_pos", (0, 0)))
    posicion_jugador = (px, py)

    total_puntos = puntos_totales(motor)
    puntos_recolectados_count = len(puntos_key(motor))
    puntos_restantes_count = total_puntos - puntos_recolectados_count

    # -------------------------------------------------------------------------
    # MODO: MINIMIZAR MOVIMIENTOS
    # Ruta con menos pasos, aunque atraviese miel si eso ahorra movimientos.
    # Prioriza resolver cajas -> objetivos. Si no hay cajas visibles, se enfoca en el siguiente objetivo.
    # Puede usar hielo para ahorrar pasos, pero no le gusta la miel porque complica el camino. 
    # -------------------------------------------------------------------------
    if modo == "min_moves":
        if posiciones_cajas and posiciones_objetivos:
            bloqueos = set(posiciones_cajas)
            mejor_jugador_a_caja = min(
                distancia_min_moves(motor, posicion_jugador, [caja], bloqueos=bloqueos - {caja})
                for caja in posiciones_cajas
            )
            mejor_caja_a_objetivo = sum(
                min(
                    distancia_min_moves(motor, caja, [obj], bloqueos=posiciones_cajas - {tuple(caja)})
                    for obj in posiciones_objetivos
                )
                for caja in posiciones_cajas
            )
            heuristica = mejor_jugador_a_caja + 2 * mejor_caja_a_objetivo
            cajas_deadlock = sum(1 for caja in posiciones_cajas if es_deadlock_simple(motor, caja))
            if cajas_deadlock > 0:
                heuristica += cajas_deadlock * 10000
            return heuristica
        if posiciones_objetivos:
            return distancia_min_moves(motor, posicion_jugador, posiciones_objetivos)
        return 0

    if modo == "max_points":
        pendientes = puntos_pendientes(motor)
        if pendientes:
            # Distancia Manhattan al punto más cercano
            dist_punto = min(distancia_manhattan(posicion_jugador, p) for p in pendientes)
            score = (
                puntos_recolectados_count * 120000
                - puntos_restantes_count * 80000
                - dist_punto * 800
            )
            # Castigo fuerte si la solución ya ganó pero todavía faltan puntos.
            if getattr(motor, "level_won", False):
                score -= 2_000_000
            return score

        # Ya no quedan puntos: ahora sí importa terminar el nivel.
        if posiciones_cajas and posiciones_objetivos:
            # Usar Manhattan para ser más rápido
            mejor_jugador_a_caja = min(
                distancia_manhattan(posicion_jugador, caja)
                for caja in posiciones_cajas
            )
            dist_cajas_objetivos = sum(
                min(distancia_manhattan(caja, obj) for obj in posiciones_objetivos)
                for caja in posiciones_cajas
            )
            return 300000 + puntos_recolectados_count * 150000 - mejor_jugador_a_caja * 12 - dist_cajas_objetivos * 15

        return 200000 + puntos_recolectados_count * 150000

    # -------------------------------------------------------------------------
    # MODO: MINIMIZAR TIEMPO
    # Ruta más rápida. Aquí la miel es muy costosa, el hielo es barato, y los huecos son carísimos porque matan.
    # -------------------------------------------------------------------------
    if posiciones_cajas and posiciones_objetivos:
        bloqueos = set(posiciones_cajas)
        mejor_jugador_a_caja = min(
            distancia_min_time(motor, posicion_jugador, [caja], bloqueos=bloqueos - {caja})
            for caja in posiciones_cajas
        )
        mejor_caja_a_objetivo = sum(
            min(
                distancia_min_time(motor, caja, [obj], bloqueos=posiciones_cajas - {tuple(caja)})
                for obj in posiciones_objetivos
            )
            for caja in posiciones_cajas
        )
        heuristica = mejor_jugador_a_caja + mejor_caja_a_objetivo
        cajas_deadlock = sum(1 for caja in posiciones_cajas if es_deadlock_simple(motor, caja))
        if cajas_deadlock > 0:
            heuristica += cajas_deadlock * 20000
        return heuristica

    if posiciones_objetivos:
        return distancia_min_time(motor, posicion_jugador, posiciones_objetivos)

    return 0


def prioridad_desde_puntaje(puntaje, modo):
    # En modos de maximizar, la cola prioriza puntajes más altos.
    # En modos de minimizar, prioriza puntajes más bajos.
    return -puntaje if es_maximizador(modo) else puntaje


def es_mejor(puntaje, mejor_puntaje, modo):
    return puntaje > mejor_puntaje if es_maximizador(modo) else puntaje < mejor_puntaje


def ruta_a_cadena(ruta):
    mapa_direcciones = {(-1, 0): "U", (1, 0): "D", (0, -1): "L", (0, 1): "R"}
    return "-".join(mapa_direcciones.get(movimiento, "?") for movimiento in ruta)


# -----------------------------------------------------------------------------
# BÚSQUEDA VORAZ
# -----------------------------------------------------------------------------
# Sigue siendo voraz: no hace A*, no hace búsqueda exhaustiva.
# La mejora importante está en la heurística, para que cada modo priorice lo que toca.
# -----------------------------------------------------------------------------
def encontrar_solucion_voraz(motor_inicial, modo, max_nodos=100000, max_tiempo=20.0, max_profundidad=1000):
    direcciones = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    tiempo_inicio = time.time()

    cola_prioridad = []
    id_nodo = 0
    nodos_explorados = 0

    puntaje_inicial = evaluar_heuristica(motor_inicial, modo)
    clave_inicial = motor_inicial.state_key()

    if modo == "max_points":
        clave_inicial = (clave_inicial, puntos_key(motor_inicial))

    heapq.heappush(
        cola_prioridad,
        (prioridad_desde_puntaje(puntaje_inicial, modo), id_nodo, motor_inicial.clone(), [])
    )

    mejor_visto = {clave_inicial: puntaje_inicial}
    mejor_solucion = None
    mejor_estado = None
    mejor_puntaje = float("-inf") if es_maximizador(modo) else float("inf")

    while cola_prioridad and nodos_explorados < max_nodos and (time.time() - tiempo_inicio) < max_tiempo:
        _, _, nodo, ruta = heapq.heappop(cola_prioridad)
        nodos_explorados += 1
        profundidad = len(ruta)

        puntaje_actual = evaluar_heuristica(nodo, modo)

        if es_mejor(puntaje_actual, mejor_puntaje, modo):
            mejor_puntaje = puntaje_actual
            mejor_solucion = ruta
            mejor_estado = nodo

        puntos_actuales = len(puntos_key(nodo))
        total_puntos = puntos_totales(nodo)

        # Condiciones de terminación del problema.
        if modo != "max_points" and nodo.level_won:
            return ruta, nodos_explorados, nodo

        if modo == "max_points" and nodo.level_won and puntos_actuales >= total_puntos:
            return ruta, nodos_explorados, nodo

        if profundidad >= max_profundidad:
            continue

        for dr, dc in direcciones:

            # --- VALIDACIÓN ANTES DE CLONAR (MUY IMPORTANTE) ---
            nr, nc = nodo.player_pos[0] + dr, nodo.player_pos[1] + dc

            if nr < 0 or nc < 0:
                continue

            tablero = obtener_tablero(nodo)

            if tablero is not None:
                if nr >= len(tablero) or nc >= len(tablero[nr]):
                    continue
                celda = tablero[nr][nc]
            else:
                celda = None

            if celda == "W":
                continue

            # lógica de empuje de cajas
            if [nr, nc] in nodo.boxes:
                br, bc = nr + dr, nc + dc

                if br < 0 or bc < 0:
                    continue

                if tablero is not None:
                    if br >= len(tablero) or bc >= len(tablero[br]):
                        continue
                    celda_caja = tablero[br][bc]
                else:
                    celda_caja = None

                if celda_caja == "W":
                    continue

                if [br, bc] in nodo.boxes:
                    continue

                # PROHIBIDO: empujar a hueco
                if celda_caja == "H":
                    continue

            # --- SIMULACIÓN ---
            hijo = nodo.clone()
            hijo.move(dr, dc)
            hijo.stuck_time = 0

            # sin cambio real
            if hijo.player_pos == nodo.player_pos and hijo.boxes == nodo.boxes:
                continue

            # caja desapareció (seguridad extra)
            if len(hijo.boxes) < len(nodo.boxes):
                continue

            # muerte
            if hijo.is_dead:
                continue

            # DEADLOCK: caja en esquina sin target
            deadlock = False
            for box in hijo.boxes:
                if box not in hijo.targets:
                    r, c = box

                    up = (r-1 < 0) or hijo.grid[r-1][c] == 'W'
                    down = (r+1 >= hijo.rows) or hijo.grid[r+1][c] == 'W'
                    left = (c-1 < 0) or hijo.grid[r][c-1] == 'W'
                    right = (c+1 >= hijo.cols) or hijo.grid[r][c+1] == 'W'

                    if (up and left) or (up and right) or (down and left) or (down and right):
                        deadlock = True
                        break

            if deadlock:
                continue

            # --- ESTADO ---
            clave = hijo.state_key()

            if modo == "max_points":
                clave = (clave, puntos_key(hijo))

            puntaje = evaluar_heuristica(hijo, modo)

            if clave in mejor_visto and not es_mejor(puntaje, mejor_visto[clave], modo):
                continue

            mejor_visto[clave] = puntaje
            id_nodo += 1

            heapq.heappush(
                cola_prioridad,
                (prioridad_desde_puntaje(puntaje, modo), id_nodo, hijo, ruta + [(dr, dc)])
            )

    if mejor_solucion is not None:
        return mejor_solucion, nodos_explorados, mejor_estado

    return None, nodos_explorados, None

# -----------------------------------------------------------------------------
# RESUMEN DE COSTO
# -----------------------------------------------------------------------------
def calcular_costo_solucion(estado_final, ruta, modo):
    if modo == "min_moves":
        return len(ruta), f"Movimientos: {len(ruta)}"

    if modo == "min_time":
        tiempo_estimado_ms = len(ruta) * 130
        tiempo_estimado_s = tiempo_estimado_ms / 1000
        return tiempo_estimado_s, f"Tiempo estimado: {tiempo_estimado_s:.2f}s ({len(ruta)} pasos)"

    if modo == "max_points":
        if estado_final:
            puntos_recolectados = len(puntos_key(estado_final))
            total_puntos = len(getattr(estado_final, "points_coords", []))
            return puntos_recolectados, f"Puntos: {puntos_recolectados}/{total_puntos} | Pasos: {len(ruta)}"
        return 0, f"Pasos: {len(ruta)}"

    return 0, f"Pasos: {len(ruta)}"


# -----------------------------------------------------------------------------
# AUTOPLAY EN HILO
# -----------------------------------------------------------------------------
def iniciar_busqueda_autoplay(juego, modo_seleccionado, estado_auto):
    # Evita lanzar dos búsquedas simultáneas.
    if estado_auto.get("buscando"):
        return

    limites_base = LIMITES_BUSQUEDA_NIVELES.get(modo_seleccionado, LIMITES_BUSQUEDA_NIVELES["min_time"])
    # Escalar límites con el nivel para niveles más difíciles (5% por nivel, máximo 3x)
    nivel = juego.current_level_idx
    factor_escala = min(3.0, 1.0 + (nivel - 1) * 0.05)
    limites = {
        "max_nodes": int(limites_base["max_nodes"] * factor_escala),
        "max_time": limites_base["max_time"] * factor_escala,
        "max_depth": int(limites_base["max_depth"] * factor_escala),
    }
    snapshot = juego.clone()

    estado_auto["buscando"] = True
    estado_auto["resultado_busqueda"] = None
    estado_auto["snapshot_busqueda"] = snapshot

    def worker():
        solucion, nodos, estado_final = encontrar_solucion_voraz(
            snapshot,
            modo_seleccionado,
            max_nodos=limites["max_nodes"],
            max_tiempo=limites["max_time"],
            max_profundidad=limites["max_depth"],
        )

        # Si la búsqueda voraz no encuentra solución con los límites normales,
        # hacemos un segundo intento con límites ampliados. Esto conserva la
        # naturaleza greedy de la búsqueda principal pero evita bloqueos
        # en niveles muy difíciles como el 50.
        if not solucion:
            solucion_fallback, nodos_fallback, estado_final_fallback = encontrar_solucion_voraz(
                snapshot,
                modo_seleccionado,
                max_nodos=int(limites["max_nodes"] * 2),
                max_tiempo=limites["max_time"] * 2.0,
                max_profundidad=int(limites["max_depth"] * 2),
            )
            if solucion_fallback:
                solucion, nodos, estado_final = solucion_fallback, nodos_fallback, estado_final_fallback

        estado_auto["resultado_busqueda"] = (solucion, nodos, estado_final)
        estado_auto["buscando"] = False

    estado_auto["thread"] = threading.Thread(target=worker)
    estado_auto["thread"].daemon = True
    estado_auto["thread"].start()

# MAIN LOOP
# -----------------------------------------------------------------------------
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
        "ruta": [],
        "paso": 0,
        "buscando": False,
        "nivel": 1,
        "mensaje": "",
        "tiempo_siguiente_movimiento": 0,
        "nodos": 0,
        "estado_final": None,
        "tiempo_fin_nivel": 0,
        "pendiente_siguiente_nivel": False,
        "texto_completado": "",
        "thread": None,
        "resultado_busqueda": None,
        "snapshot_busqueda": None,
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
                    btn_min_tiempo = pygame.Rect(SCREEN_WIDTH // 2 - 125, 330, 250, 58)
                    btn_min_movs = pygame.Rect(SCREEN_WIDTH // 2 - 125, 410, 250, 58)
                    btn_max_puntos = pygame.Rect(SCREEN_WIDTH // 2 - 125, 490, 250, 58)
                    btn_iniciar = pygame.Rect(SCREEN_WIDTH // 2 - 140, 580, 280, 60)

                    if btn_min_tiempo.collidepoint(evento.pos):
                        modo_seleccionado = "min_time"
                    elif btn_min_movs.collidepoint(evento.pos):
                        modo_seleccionado = "min_moves"
                    elif btn_max_puntos.collidepoint(evento.pos):
                        modo_seleccionado = "max_points"
                    elif btn_iniciar.collidepoint(evento.pos):
                        estado_actual = STATE_AUTOPLAY
                        estado_auto["nivel"] = juego.current_level_idx
                        estado_auto["paso"] = 0
                        estado_auto["ruta"] = []
                        estado_auto["mensaje"] = f"Iniciando autoplay desde nivel {juego.current_level_idx}: {obtener_etiqueta_heuristica(modo_seleccionado)}"
                        estado_auto["tiempo_siguiente_movimiento"] = pygame.time.get_ticks()
                        estado_auto["nodos"] = 0
                        estado_auto["estado_final"] = None
                        estado_auto["tiempo_fin_nivel"] = 0
                        estado_auto["pendiente_siguiente_nivel"] = False
                        estado_auto["texto_completado"] = ""
                        estado_auto["thread"] = None
                        estado_auto["resultado_busqueda"] = None
                        estado_auto["snapshot_busqueda"] = None
                        juego.load_level(juego.current_level_idx)
                        iniciar_busqueda_autoplay(juego, modo_seleccionado, estado_auto)

            elif estado_actual == STATE_AUTOPLAY:
                if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
                    estado_actual = STATE_MENU

            elif estado_actual == STATE_LEVEL_SELECT:
                if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
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
            dibujar_texto(pantalla, "Elige una sola modalidad de búsqueda automática", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 220)
            dibujar_texto(pantalla, "Luego pulsa INICIAR para ejecutar autoplay desde el nivel seleccionado", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 245)
            dibujar_texto(pantalla, "Modo:", fuente_menu, COLOR_TEXT, SCREEN_WIDTH // 2, 270)
            dibujar_boton(
                pantalla,
                "MINIMIZAR TIEMPO",
                fuente_menu,
                SCREEN_WIDTH // 2,
                320,
                310,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "min_time")
            )
            dibujar_boton(
                pantalla,
                "MINIMIZAR MOVS.",
                fuente_menu,
                SCREEN_WIDTH // 2,
                400,
                310,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "min_moves")
            )
            dibujar_boton(
                pantalla,
                "MAXIMIZAR PUNTOS",
                fuente_menu,
                SCREEN_WIDTH // 2,
                480,
                310,
                58,
                posicion_mouse,
                activo=(modo_seleccionado == "max_points")
            )
            dibujar_boton(pantalla, "INICIAR", fuente_menu, SCREEN_WIDTH // 2, 560, 320, 65, posicion_mouse)

            dibujar_texto(pantalla, "Presiona ESC para volver al menú", fuente_pequena, (180, 180, 180), SCREEN_WIDTH // 2, 620)
            dibujar_texto(pantalla, f"Seleccionado: {obtener_etiqueta_heuristica(modo_seleccionado)}", fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 640)

        elif estado_actual == STATE_AUTOPLAY:
            juego.draw(pantalla)
            dibujar_texto(pantalla, "AUTOPLAY ACTIVADO", fuente_menu, COLOR_PLAYER, SCREEN_WIDTH // 2, 80)
            dibujar_texto(pantalla, f"Nivel automático: {estado_auto['nivel']}", fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 110)
            dibujar_texto(pantalla, estado_auto["mensaje"], fuente_pequena, COLOR_TEXT, SCREEN_WIDTH // 2, 135)
            if estado_auto["texto_completado"]:
                dibujar_texto(pantalla, estado_auto["texto_completado"], fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 160)

            if estado_auto["buscando"]:
                dibujar_texto(pantalla, "Buscando solución... Esto puede tomar algunos segundos.", fuente_pequena, COLOR_BTN_HOVER, SCREEN_WIDTH // 2, 190)

            if estado_auto["ruta"]:
                dibujar_texto(pantalla, f"Pasos: {len(estado_auto['ruta'])}  Nodo(s): {estado_auto['nodos']}", fuente_pequena, COLOR_TARGET, SCREEN_WIDTH // 2, 215)

            dibujar_texto(pantalla, "Presiona ESC para detener autoplay", fuente_pequena, (180, 180, 180), SCREEN_WIDTH // 2, 710)

            # Si la búsqueda en segundo plano terminó, consumimos el resultado.
            if estado_auto["buscando"]:
                if estado_auto["thread"] is not None and not estado_auto["thread"].is_alive():
                    solucion, nodos, estado_final = estado_auto["resultado_busqueda"]
                    estado_auto["nodos"] = nodos
                    estado_auto["estado_final"] = estado_final
                    estado_auto["buscando"] = False
                    estado_auto["thread"] = None
                    estado_auto["resultado_busqueda"] = None

                    if solucion:
                        estado_auto["ruta"] = solucion
                        estado_auto["paso"] = 0
                        estado_auto["mensaje"] = f"Solución encontrada: {len(solucion)} pasos"
                        estado_auto["tiempo_siguiente_movimiento"] = pygame.time.get_ticks()
                    else:
                        estado_auto["mensaje"] = f"No se encontró solución en este nivel ({nodos} nodos). Presiona ESC."
                        estado_auto["ruta"] = []

            elif pygame.time.get_ticks() >= estado_auto["tiempo_siguiente_movimiento"]:
                # -----------------------------------------------------------------
                # NIVEL COMPLETADO
                # -----------------------------------------------------------------
                if juego.level_won:
                    # Cuando el nivel ya está ganado, mostramos el resumen y pasamos al siguiente.
                    if estado_auto["tiempo_fin_nivel"] == 0:
                        cadena_ruta = ruta_a_cadena(estado_auto["ruta"])
                        _, cadena_costo = calcular_costo_solucion(
                            estado_auto["estado_final"],
                            estado_auto["ruta"],
                            modo_seleccionado
                        )

                        print(f"[Nivel {estado_auto['nivel']}] Ruta: {cadena_ruta}")
                        print(f"[Nivel {estado_auto['nivel']}] Costo: {cadena_costo}")
                        print(f"[Nivel {estado_auto['nivel']}] Nodos: {estado_auto['nodos']}")
                        print()

                        estado_auto["mensaje"] = f"✔ Nivel {estado_auto['nivel']} completado"
                        estado_auto["texto_completado"] = cadena_costo
                        estado_auto["tiempo_fin_nivel"] = pygame.time.get_ticks() + 1800
                        estado_auto["ruta"] = []

                    elif pygame.time.get_ticks() >= estado_auto["tiempo_fin_nivel"]:
                        estado_auto["tiempo_fin_nivel"] = 0
                        estado_auto["texto_completado"] = ""

                        if estado_auto["nivel"] < 50:
                            estado_auto["nivel"] += 1
                            juego.current_level_idx = estado_auto["nivel"]
                            juego.load_level(estado_auto["nivel"])
                            estado_auto["buscando"] = False
                            estado_auto["mensaje"] = f"Nivel {estado_auto['nivel']}..."
                            estado_auto["paso"] = 0
                            estado_auto["estado_final"] = None
                            estado_auto["thread"] = None
                            estado_auto["resultado_busqueda"] = None
                            iniciar_busqueda_autoplay(juego, modo_seleccionado, estado_auto)
                        else:
                            estado_auto["mensaje"] = "Autoplay completado"
                            estado_auto["texto_completado"] = "✔ Todos los niveles"
                            print("[Autoplay] Completado")

                # -----------------------------------------------------------------
                # EJECUTAR RUTA ACTUAL
                # -----------------------------------------------------------------
                elif estado_auto["ruta"] and estado_auto["paso"] < len(estado_auto["ruta"]):
                    dr, dc = estado_auto["ruta"][estado_auto["paso"]]
                    juego.move(dr, dc)
                    estado_auto["paso"] += 1
                    estado_auto["tiempo_siguiente_movimiento"] = pygame.time.get_ticks() + 180

                else:
                    # Si estamos en max_points y la ruta ya terminó, volvemos a buscar
                    # desde el estado actual mientras aún queden S pendientes.
                    if modo_seleccionado == "max_points":
                        puntos_actuales = len(juego.points_collected)
                        total_puntos = len(juego.points_coords)

                        if puntos_actuales >= total_puntos:
                            estado_auto['mensaje'] = "Resolviendo nivel..."
                            iniciar_busqueda_autoplay(juego, "min_moves", estado_auto)
                            continue
                        if not estado_auto['ruta']:
                            estado_auto['mensaje'] = "No se pueden recolectar más puntos"
                            continue

                        estado_auto['mensaje'] = f"Recolectando puntos... ({puntos_actuales}/{total_puntos})"
                        iniciar_busqueda_autoplay(juego, modo_seleccionado, estado_auto)
                    else:
                        estado_auto["mensaje"] = "No se pudo ejecutar la ruta"
                        estado_auto["ruta"] = []

            elif not estado_auto["ruta"] and not estado_auto["buscando"] and not juego.level_won:
                estado_auto["mensaje"] = "No se puede resolver este nivel automáticamente."

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
