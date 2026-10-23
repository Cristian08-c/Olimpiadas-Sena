"""Tests de scoring.py — sin BD, sin Flask, solo la lógica pura.

Ejecutar desde la raíz del proyecto:

    python -m pytest src/modules/common/tests/ -v

Requiere `pytest` (pip install pytest).
"""
import pytest

from src.modules.common.scoring import (
    calcular_puntuacion,
    construir_respuestas_correctas,
)


# ============================================================================
# construir_respuestas_correctas
# ============================================================================

def test_construir_seleccion_multiple():
    result = construir_respuestas_correctas(
        [{"id_pregunta": 1, "puntos": 10, "respuesta": "París"}],
        [],
    )
    assert result == {
        "sel_1": {
            "tipo": "seleccion_multiple",
            "puntos": 10,
            "respuesta_correcta": "París",
        }
    }


def test_construir_completar_ignora_distractores():
    rows = [
        {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "correcto",   "complemento": "a", "id_respuesta2": 1},
        {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "correcto",   "complemento": "b", "id_respuesta2": 2},
        {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "distractor", "complemento": "x", "id_respuesta2": 3},
    ]
    result = construir_respuestas_correctas([], rows)
    assert result["otr_5"] == {
        "tipo": "completar",
        "puntos": 9,
        "respuesta_correcta": {"0": "a", "1": "b"},
        "num_items": 2,
    }


def test_construir_relacionar():
    rows = [
        {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "España",  "complemento": "Madrid", "id_respuesta2": 1},
        {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "Francia", "complemento": "París",  "id_respuesta2": 2},
        {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "Italia",  "complemento": "Roma",   "id_respuesta2": 3},
    ]
    result = construir_respuestas_correctas([], rows)
    assert result["otr_7"] == {
        "tipo": "relacionar",
        "puntos": 6,
        "respuesta_correcta": {"0": "0", "1": "1", "2": "2"},
        "num_items": 3,
    }


def test_construir_mixto():
    result = construir_respuestas_correctas(
        [{"id_pregunta": 1, "puntos": 10, "respuesta": "París"}],
        [{"id_pregunta2": 5, "tipo": "completar", "puntos": 3, "enunciado": "correcto", "complemento": "x", "id_respuesta2": 1}],
    )
    assert set(result.keys()) == {"sel_1", "otr_5"}


# ============================================================================
# calcular_puntuacion — selección múltiple
# ============================================================================

@pytest.fixture
def correctas_sel():
    return construir_respuestas_correctas(
        [{"id_pregunta": 1, "puntos": 10, "respuesta": "París"}], []
    )


def test_sel_correcta(correctas_sel):
    total, desglose = calcular_puntuacion({"sel_1": "París"}, correctas_sel)
    assert total == 10.0
    assert desglose["sel_1"]["correcto"] is True
    assert desglose["sel_1"]["puntos_obtenidos"] == 10.0


def test_sel_incorrecta(correctas_sel):
    total, desglose = calcular_puntuacion({"sel_1": "Londres"}, correctas_sel)
    assert total == 0.0
    assert desglose["sel_1"]["correcto"] is False


def test_sel_sin_responder(correctas_sel):
    total, desglose = calcular_puntuacion({}, correctas_sel)
    assert total == 0.0
    assert "sel_1" in desglose["_sin_respuesta"]


# ============================================================================
# calcular_puntuacion — completar (crédito parcial)
# ============================================================================

@pytest.fixture
def correctas_comp():
    return construir_respuestas_correctas(
        [],
        [
            {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "correcto", "complemento": "a", "id_respuesta2": 1},
            {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "correcto", "complemento": "b", "id_respuesta2": 2},
            {"id_pregunta2": 5, "tipo": "completar", "puntos": 9, "enunciado": "correcto", "complemento": "c", "id_respuesta2": 3},
        ],
    )


def test_comp_todos_correctos(correctas_comp):
    total, desglose = calcular_puntuacion(
        {"otr_5": {"0": "a", "1": "b", "2": "c"}}, correctas_comp
    )
    assert total == 9.0
    assert desglose["otr_5"]["aciertos"] == 3
    assert desglose["otr_5"]["correcto"] is True


def test_comp_parcial(correctas_comp):
    total, desglose = calcular_puntuacion(
        {"otr_5": {"0": "a", "1": "X", "2": "c"}}, correctas_comp
    )
    assert total == 6.0  # 2/3 × 9
    assert desglose["otr_5"]["aciertos"] == 2
    assert desglose["otr_5"]["correcto"] is False


def test_comp_cero_aciertos(correctas_comp):
    total, _ = calcular_puntuacion(
        {"otr_5": {"0": "X", "1": "Y", "2": "Z"}}, correctas_comp
    )
    assert total == 0.0


def test_comp_items_incompletos(correctas_comp):
    # El usuario solo envía 1 de los 3 esperados
    total, desglose = calcular_puntuacion({"otr_5": {"0": "a"}}, correctas_comp)
    assert total == 3.0  # 1/3 × 9
    assert desglose["otr_5"]["aciertos"] == 1


def test_comp_respuesta_no_es_dict(correctas_comp):
    total, desglose = calcular_puntuacion({"otr_5": "basura"}, correctas_comp)
    assert total == 0.0
    assert "no es un diccionario" in desglose["otr_5"].get("_error", "")


# ============================================================================
# calcular_puntuacion — relacionar (crédito parcial)
# ============================================================================

@pytest.fixture
def correctas_rel():
    return construir_respuestas_correctas(
        [],
        [
            {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "España",  "complemento": "Madrid", "id_respuesta2": 1},
            {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "Francia", "complemento": "París",  "id_respuesta2": 2},
            {"id_pregunta2": 7, "tipo": "relacionar", "puntos": 6, "enunciado": "Italia",  "complemento": "Roma",   "id_respuesta2": 3},
        ],
    )


def test_rel_todos_correctos(correctas_rel):
    total, desglose = calcular_puntuacion(
        {"otr_7": {"0": "0", "1": "1", "2": "2"}}, correctas_rel
    )
    assert total == 6.0
    assert desglose["otr_7"]["correcto"] is True


def test_rel_parcial(correctas_rel):
    total, desglose = calcular_puntuacion(
        {"otr_7": {"0": "0", "1": "2", "2": "1"}}, correctas_rel
    )
    assert total == 2.0  # 1/3 × 6
    assert desglose["otr_7"]["aciertos"] == 1


# ============================================================================
# calcular_puntuacion — casos borde
# ============================================================================

def test_huerfanas_no_suman(correctas_sel):
    total, desglose = calcular_puntuacion(
        {"sel_1": "París", "sel_999": "x"}, correctas_sel
    )
    assert total == 10.0
    assert desglose["_huerfanas"] == ["sel_999"]


def test_todo_vacio(correctas_sel, correctas_comp):
    correctas = {**correctas_sel, **correctas_comp}
    total, desglose = calcular_puntuacion({}, correctas)
    assert total == 0.0
    assert "sel_1" in desglose["_sin_respuesta"]
    assert "otr_5" in desglose["_sin_respuesta"]
    assert desglose["_huerfanas"] == []


def test_resumen(correctas_sel, correctas_comp, correctas_rel):
    correctas = {**correctas_sel, **correctas_comp, **correctas_rel}
    respuestas = {
        "sel_1": "París",                         # ✓ 10
        "otr_5": {"0": "a", "1": "X", "2": "c"},  # 2/3 → 6
        "otr_7": {"0": "0", "1": "1", "2": "2"},  # ✓ 6
    }
    total, desglose = calcular_puntuacion(respuestas, correctas)
    assert total == 22.0
    assert desglose["_resumen"] == {
        "total_preguntas": 3,
        "contestadas": 3,
        "puntos_obtenidos": 22.0,
        "puntos_maximos": 25,   # 10 + 9 + 6
    }