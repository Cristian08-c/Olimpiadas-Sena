"""Lógica de calificación de exámenes — funciones puras, sin BD ni Flask.

Esta pieza centraliza el cálculo de puntuación que antes vivía enterrado en
`finalizar_examen()` (app.py). Al ser puro, es testeable con pytest sin
necesidad de MySQL, y puede reutilizarse para:

  - Recalcular notas si cambian los pesos de las preguntas.
  - Mostrar al aprendiz "acertaste 2/3 en esta pregunta".
  - Debuggear sin tocar la BD.

Contrato de datos (idéntico al que produce el SQL original):

  rows_seleccion:
      [{"id_pregunta": int, "puntos": int, "respuesta": str}, ...]
      (solo filas con `respuestas_seleccion.estado = 'verdadero'`)

  rows_otras:
      [{"id_pregunta2": int, "tipo": "completar" | "relacionar",
        "puntos": int, "enunciado": str, "complemento": str,
        "id_respuesta2": int}, ...]
      ordenadas por (id_pregunta2, id_respuesta2) ASC — el orden es
      crucial para 'completar', donde el índice del espacio en blanco
      se deriva del orden de las respuestas correctas.

  respuestas_usuario:
      {
        "sel_<id>": "texto de la opción elegida",
        "otr_<id>": {"0": "a", "1": "b"},   # completar
        "otr_<id>": {"0": "2", "1": "0"},   # relacionar (izq → der original)
      }

  respuestas_correctas (salida de `construir_respuestas_correctas`):
      {
        "sel_<id>": {"tipo": "seleccion_multiple", "puntos": int,
                     "respuesta_correcta": str},
        "otr_<id>": {"tipo": "completar", "puntos": int,
                     "respuesta_correcta": {"0": "a", ...},
                     "num_items": int},
        "otr_<id>": {"tipo": "relacionar", "puntos": int,
                     "respuesta_correcta": {"0": "0", ...},
                     "num_items": int},
      }

TODO (Paso 6 - limpieza): el redondeo actual (`round()` del total) es
injusto en casos como 2 items de 3 pts con 1 acierto (1.5 → 2). Decidir
si migrar a DECIMAL(6,2) en BD o a redondeo por ítem. Esta función NO
redondea: el caller decide.
"""
from typing import Any


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def construir_respuestas_correctas(
    rows_seleccion: list[dict[str, Any]],
    rows_otras: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Transforma filas crudas de BD al formato canónico de respuestas correctas.

    Parámetros
    ----------
    rows_seleccion : list[dict]
        Filas de `preguntas_seleccion JOIN respuestas_seleccion`
        con `estado = 'verdadero'`. Cada fila: `id_pregunta`, `puntos`,
        `respuesta`.
    rows_otras : list[dict]
        Filas de `preguntas_otras JOIN respuestas_otras`, ordenadas por
        `(id_pregunta2, id_respuesta2)`. Cada fila: `id_pregunta2`,
        `tipo`, `puntos`, `enunciado`, `complemento`, `id_respuesta2`.

    Devuelve
    --------
    dict
        Mapa `unique_id -> info` con `unique_id = "sel_<id>"` o `"otr_<id>"`.
    """
    respuestas: dict[str, dict[str, Any]] = {}

    # --- Selección múltiple ---
    for row in rows_seleccion:
        unique_id = f"sel_{row['id_pregunta']}"
        respuestas[unique_id] = {
            "tipo": "seleccion_multiple",
            "puntos": row["puntos"],
            "respuesta_correcta": row["respuesta"],
        }

    # --- Otras (completar / relacionar) ---
    # Agrupamos por id_pregunta2 para saber cuántos ítems tiene cada pregunta.
    agrupadas: dict[int, dict[str, Any]] = {}
    for row in rows_otras:
        pid = row["id_pregunta2"]
        if pid not in agrupadas:
            agrupadas[pid] = {
                "tipo": row["tipo"],
                "puntos": row["puntos"],
                "respuestas": [],
            }
        agrupadas[pid]["respuestas"].append(row)

    for pid, data in agrupadas.items():
        unique_id = f"otr_{pid}"

        if data["tipo"] == "completar":
            # Solo las filas con `enunciado == 'correcto'` cuentan. El índice
            # del espacio en blanco es su posición en el orden recibido.
            correctas = [
                r["complemento"]
                for r in data["respuestas"]
                if r["enunciado"] == "correcto"
            ]
            respuestas[unique_id] = {
                "tipo": "completar",
                "puntos": data["puntos"],
                "respuesta_correcta": {str(i): v for i, v in enumerate(correctas)},
                "num_items": len(correctas),
            }

        elif data["tipo"] == "relacionar":
            # El frontend envía pares (índice_izq → índice_original_der).
            # Correcto = cada ítem i empareja con el ítem i.
            num_items = len(data["respuestas"])
            respuestas[unique_id] = {
                "tipo": "relacionar",
                "puntos": data["puntos"],
                "respuesta_correcta": {str(i): str(i) for i in range(num_items)},
                "num_items": num_items,
            }

        else:
            # Tipo desconocido: no suma, pero lo registramos para que el
            # caller pueda auditar. Evita crashear en datos corruptos.
            respuestas[unique_id] = {
                "tipo": data["tipo"],
                "puntos": data["puntos"],
                "respuesta_correcta": None,
                "num_items": 0,
                "_error": f"tipo desconocido: {data['tipo']}",
            }

    return respuestas


def calcular_puntuacion(
    respuestas_usuario: dict[str, Any],
    respuestas_correctas: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Calcula la puntuación total y el desglose por pregunta.

    Respeta crédito parcial de `completar` y `relacionar`
    (`puntos_por_item = puntos_totales / num_items`).

    No redondea: devuelve un float. El caller decide el redondeo final
    (hoy `finalizar_examen` usa `round(...)` y lo guarda en BD).

    Devuelve
    --------
    (puntuacion_total, desglose)
        desglose contiene:
          - una entrada por cada unique_id de `respuestas_correctas`
          - `"_huerfanas"`:      keys de `respuestas_usuario` que no existen
                                 en el examen (basura del cliente)
          - `"_sin_respuesta"`:  preguntas del examen que el usuario no
                                 contestó
          - `"_resumen"`:        totales agregados listos para UI
    """
    puntuacion_total = 0.0
    desglose: dict[str, Any] = {}

    for unique_id, info in respuestas_correctas.items():
        # --- Preguntas mal construidas: no suman, pero se registran ---
        if info.get("respuesta_correcta") is None:
            desglose[unique_id] = {
                "tipo": info.get("tipo"),
                "puntos_obtenidos": 0.0,
                "puntos_maximos": info.get("puntos", 0),
                "aciertos": 0,
                "total_items": 0,
                "correcto": False,
                "_error": info.get("_error", "pregunta sin respuesta correcta"),
            }
            continue

        tipo = info["tipo"]
        resp_usuario = respuestas_usuario.get(unique_id)

        # --- Selección múltiple ---
        if tipo == "seleccion_multiple":
            correcto = resp_usuario == info["respuesta_correcta"]
            puntos_obtenidos = float(info["puntos"]) if correcto else 0.0
            puntuacion_total += puntos_obtenidos
            desglose[unique_id] = {
                "tipo": tipo,
                "puntos_obtenidos": puntos_obtenidos,
                "puntos_maximos": info["puntos"],
                "aciertos": 1 if correcto else 0,
                "total_items": 1,
                "correcto": correcto,
            }
            continue

        # --- Completar / Relacionar (crédito parcial) ---
        num_items = info["num_items"]

        if num_items == 0:
            desglose[unique_id] = {
                "tipo": tipo,
                "puntos_obtenidos": 0.0,
                "puntos_maximos": info["puntos"],
                "aciertos": 0,
                "total_items": 0,
                "correcto": False,
                "_error": "pregunta sin ítems definidos",
            }
            continue

        if not isinstance(resp_usuario, dict):
            desglose[unique_id] = {
                "tipo": tipo,
                "puntos_obtenidos": 0.0,
                "puntos_maximos": info["puntos"],
                "aciertos": 0,
                "total_items": num_items,
                "correcto": False,
                "_error": "respuesta no es un diccionario",
            }
            continue

        puntos_por_item = info["puntos"] / num_items
        correctas = info["respuesta_correcta"]

        if tipo == "completar":
            aciertos = sum(
                1
                for idx, palabra in resp_usuario.items()
                if idx in correctas and correctas[idx] == palabra
            )
        else:  # relacionar
            aciertos = sum(
                1
                for idx_a, idx_b in resp_usuario.items()
                if idx_a in correctas and correctas[idx_a] == idx_b
            )

        puntos_obtenidos = aciertos * puntos_por_item
        puntuacion_total += puntos_obtenidos
        desglose[unique_id] = {
            "tipo": tipo,
            "puntos_obtenidos": puntos_obtenidos,
            "puntos_maximos": info["puntos"],
            "aciertos": aciertos,
            "total_items": num_items,
            "correcto": aciertos == num_items,
        }

    # --- Metadatos de auditoría ---
    todos_los_ids = set(respuestas_correctas.keys())
    ids_contestados = set(respuestas_usuario.keys())

    desglose["_huerfanas"] = sorted(ids_contestados - todos_los_ids)
    desglose["_sin_respuesta"] = sorted(todos_los_ids - ids_contestados)
    desglose["_resumen"] = {
        "total_preguntas": len(todos_los_ids),
        "contestadas": len(ids_contestados & todos_los_ids),
        "puntos_obtenidos": round(puntuacion_total, 2),
        "puntos_maximos": sum(i.get("puntos", 0) for i in respuestas_correctas.values()),
    }

    return puntuacion_total, desglose