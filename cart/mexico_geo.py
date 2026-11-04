"""
Estados, municipios y códigos postales de México con cobertura de contra
entrega en Dropi México.

Fuente: cart/data/mexico_geo.json, generado por scripts/build_mexico_geo.py
desde la API de Dropi México (trajectory/bycity con "CON RECAUDO"). Se usan
los nombres de Dropi porque el pedido se le manda con ellos: si el estado o la
ciudad no coinciden con su catálogo, la guía no se genera.

Para el cliente se muestran los nombres en formato legible ("label"); al
armar el pedido se traducen a los de Dropi con dropi_names().

Los códigos postales de Dropi no están completos (en algunos estados hay
ciudades con cobertura pero sin CP cargados), por eso el CP ayuda a llenar
estado y municipio, pero no se rechaza un pedido porque su CP no esté aquí.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent / "data" / "mexico_geo.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_DATA_FILE.read_text(encoding="utf-8"))


def _states() -> list[dict]:
    return _data()["states"]


def norm(value: str) -> str:
    """'Jesús María' / 'JESÚS MARÍA' → 'jesus maria'."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    return " ".join(value.split())


@lru_cache(maxsize=1)
def states() -> list[tuple[str, str]]:
    """[(código, nombre visible)] ordenados por nombre: ('AGU', 'Aguascalientes')."""
    # Ordenado sin tildes: Dropi pone "MÉXICO" después de "MORELOS".
    rows = [(s["code"], s["label"]) for s in _states() if s["cities"]]
    return sorted(rows, key=lambda row: norm(row[1]))


@lru_cache(maxsize=1)
def municipios_by_state_label() -> dict[str, list[str]]:
    """{'Aguascalientes': ['Aguascalientes', 'Asientos', ...]} (nombres visibles)."""
    return {s["label"]: [c["label"] for c in s["cities"]] for s in _states() if s["cities"]}


@lru_cache(maxsize=1)
def cities_by_state_code() -> dict[str, list[str]]:
    return {s["code"]: [c["label"] for c in s["cities"]] for s in _states() if s["cities"]}


@lru_cache(maxsize=1)
def _by_code() -> dict[str, dict]:
    return {s["code"]: s for s in _states()}


@lru_cache(maxsize=1)
def _city_index() -> dict[tuple[str, str], dict]:
    """(código de estado, ciudad normalizada) → ciudad de Dropi."""
    return {(s["code"], norm(c["label"])): c for s in _states() for c in s["cities"]}


@lru_cache(maxsize=1)
def _zip_index() -> dict[str, list[tuple[str, str]]]:
    """CP → [(código de estado, ciudad visible)]. Un CP casi siempre es de una
    sola ciudad, pero Dropi a veces lo repite en dos municipios vecinos."""
    out: dict[str, list[tuple[str, str]]] = {}
    for s in _states():
        for c in s["cities"]:
            for z in c["zips"]:
                out.setdefault(z, []).append((s["code"], c["label"]))
    return out


def state_label(code: str) -> str:
    state = _by_code().get(code or "")
    return state["label"] if state else ""


def find_city(state_code: str, city: str) -> dict | None:
    return _city_index().get((state_code or "", norm(city)))


def lookup_zip(zip_code: str) -> list[tuple[str, str]]:
    return list(_zip_index().get((zip_code or "").strip(), []))


def dropi_names(state_code: str, city_label: str) -> tuple[str, str]:
    """Nombres de estado y ciudad tal como los espera Dropi en el pedido.
    Si no se encuentran (no debería pasar tras validar el formulario), se
    devuelven los visibles para no perder el pedido."""
    state = _by_code().get(state_code or "")
    city = find_city(state_code, city_label)
    return (
        state["name"] if state else (state_code or ""),
        city["name"] if city else (city_label or ""),
    )


def state_code_for_label(label: str) -> str:
    key = norm(label)
    for s in _states():
        if norm(s["label"]) == key or norm(s["name"]) == key or s["code"].lower() == key:
            return s["code"]
    return ""
