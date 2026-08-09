"""jyotish_mcp — MCP server for Vedic astrology (Jyotish) chart computation.

Exposes precise Swiss-Ephemeris-based computation so the LLM can focus on
interpretation. Sidereal zodiac (Lahiri), whole-sign houses, Vimshottari dasha.

Run modes:
  python server.py            -> stdio (local, Claude Desktop config)
  python server.py --http     -> streamable HTTP on 0.0.0.0:$PORT (remote connector)
  MCP_TRANSPORT=http python server.py   -> same as --http (for PaaS like Render)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from mcp.server.fastmcp import FastMCP

import jyotish_core as jc
import geo

USE_HTTP = "--http" in sys.argv or os.environ.get("MCP_TRANSPORT", "").lower() in ("http", "streamable-http")

mcp = FastMCP(
    "jyotish_mcp",
    # stateless HTTP: each request is independent -> easy to scale, survives restarts
    stateless_http=True,
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)


class BirthDataInput(BaseModel):
    """Birth data. Time must be local birth time. Provide EITHER utc_offset
    (historical offset incl. DST) OR timezone (IANA name like 'Asia/Bishkek' —
    the historical offset for the birth date is then computed automatically,
    which is the recommended way)."""

    date: str = Field(..., description="Birth date, YYYY-MM-DD (e.g. '1986-05-03')")
    time: str = Field(..., description="Local birth time, HH:MM 24h (e.g. '09:15')")
    utc_offset: float | None = Field(default=None, ge=-12, le=14,
                                     description="UTC offset in hours in effect at birth, e.g. 7.0. "
                                                 "Leave empty if 'timezone' is provided.")
    timezone: str | None = Field(default=None,
                                 description="IANA timezone of the birthplace, e.g. 'Asia/Bishkek'. "
                                             "Preferred over utc_offset: historical rules (incl. Soviet "
                                             "summer time) are applied automatically. Get it from "
                                             "jyotish_find_place.")
    latitude: float = Field(..., ge=-90, le=90, description="Birthplace latitude, e.g. 42.8667")
    longitude: float = Field(..., ge=-180, le=180, description="Birthplace longitude, e.g. 74.5833")
    place: str = Field(default="", description="Optional place name for reference")

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        import datetime
        datetime.datetime.strptime(v, "%Y-%m-%d")
        return v

    @field_validator("time")
    @classmethod
    def _check_time(cls, v: str) -> str:
        import datetime
        datetime.datetime.strptime(v, "%H:%M")
        return v

    @model_validator(mode="after")
    def _resolve_offset(self):
        if self.utc_offset is None:
            if not self.timezone:
                raise ValueError("Provide either utc_offset or timezone "
                                 "(use jyotish_find_place to get the timezone).")
            self.utc_offset = geo.utc_offset_for(self.timezone, self.date, self.time)
        return self


class DashaInput(BirthDataInput):
    target_date: Optional[str] = Field(
        default=None,
        description="YYYY-MM-DD date for which to identify the active period and expand "
                    "pratyantardashas (default: today)")


class TransitInput(BirthDataInput):
    on_date: Optional[str] = Field(
        default=None,
        description="YYYY-MM-DD date of the transit snapshot (default: today)")


@mcp.tool(
    name="jyotish_compute_chart",
    annotations={"title": "Compute Vedic birth chart (D1 + D9)",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_compute_chart(params: BirthDataInput) -> str:
    """Compute a complete sidereal (Lahiri) Vedic birth chart.

    Returns JSON with: ascendant (sign, degree, nakshatra), all 9 grahas
    (sign, degree, whole-sign house, nakshatra+pada+lord, retrogradation,
    dignity own/exalted/debilitated, navamsa sign, vargottama flag),
    Jaimini karakas (AK..DK, 7-planet scheme), and detected yogas
    (Mahapurusha, Gajakesari, yogakaraka, neecha bhanga conditions, Kemadruma).

    Accuracy: positions match professional Jyotish software to arc-seconds.
    """
    chart = jc.build_chart(params.date, params.time, params.utc_offset,
                           params.latitude, params.longitude, params.place)
    return json.dumps(chart, ensure_ascii=False, indent=1)


@mcp.tool(
    name="jyotish_vimshottari_dasha",
    annotations={"title": "Vimshottari dasha periods (3 levels)",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_vimshottari_dasha(params: DashaInput) -> str:
    """Compute the Vimshottari dasha tree from the natal Moon nakshatra.

    Returns JSON with: all 9 mahadashas with dates, every antardasha inside
    each mahadasha, pratyantardashas expanded for the period containing
    target_date, and 'current_period' identifying the active MD/AD/PD.
    Use target_date to inspect any past or future moment of life.
    """
    d = jc.vimshottari_dasha(params.date, params.time, params.utc_offset,
                             params.latitude, params.longitude,
                             target_date=params.target_date)
    return json.dumps(d, ensure_ascii=False, indent=1)


@mcp.tool(
    name="jyotish_current_transits",
    annotations={"title": "Transit snapshot vs natal chart (incl. Sade Sati)",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_current_transits(params: TransitInput) -> str:
    """Sidereal transit positions on a given date, referenced to the natal chart.

    Returns JSON with: each graha's transit sign and its house counted from
    the natal lagna and from the natal Moon, Sade Sati status (active + phase),
    and whether Saturn is transiting its natal sign (Saturn return).
    """
    t = jc.current_transits(params.date, params.time, params.utc_offset,
                            params.latitude, params.longitude,
                            on_date=params.on_date)
    return json.dumps(t, ensure_ascii=False, indent=1)


class PlaceInput(BaseModel):
    """City search input."""
    city: str = Field(..., min_length=2, description="City name, e.g. 'Bishkek', 'Алматы', 'London'")


@mcp.tool(
    name="jyotish_find_place",
    annotations={"title": "Find birthplace: coordinates and timezone",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_find_place(params: PlaceInput) -> str:
    """Look up a city (offline database, cities over 15k population worldwide).

    Returns JSON list of matches with latitude, longitude and IANA timezone.
    Pass the timezone (not a hand-computed utc_offset) to the other tools —
    the historically correct offset for the birth date is then applied
    automatically. If several matches are returned, confirm the country
    with the user.
    """
    hits = geo.search_city(params.city)
    if not hits:
        return json.dumps({"matches": [], "hint": "City not found in the offline database. "
                           "Ask the user for coordinates and timezone, or try an alternate spelling "
                           "(the database uses English names, e.g. 'Bishkek' not 'Бишкек' — "
                           "but many local spellings are indexed too)."}, ensure_ascii=False)
    return json.dumps({"matches": hits}, ensure_ascii=False, indent=1)


class VargaInput(BirthDataInput):
    varga: str = Field(default="D9",
                       description="Divisional chart: D2 (wealth), D3 (siblings), D7 (children), "
                                   "D9 (marriage/dharma), D10 (career), D12 (parents)")


@mcp.tool(
    name="jyotish_divisional_chart",
    annotations={"title": "Divisional chart (varga) D2/D3/D7/D9/D10/D12",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_divisional_chart(params: VargaInput) -> str:
    """Compute a divisional chart (varga): sign of every graha and the varga lagna.

    Use D7 for questions about children, D10 for career depth, D9 for marriage,
    D2 for wealth, D3 for siblings/courage, D12 for parents and lineage.
    Returns JSON with each planet's varga sign, house from varga lagna, dignity.
    """
    d = jc.divisional_chart(params.date, params.time, params.utc_offset,
                            params.latitude, params.longitude, params.varga)
    return json.dumps(d, ensure_ascii=False, indent=1)


@mcp.tool(
    name="jyotish_ashtakavarga",
    annotations={"title": "Ashtakavarga (BAV + SAV bindus)",
                 "readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False},
)
def jyotish_ashtakavarga(params: BirthDataInput) -> str:
    """Compute Ashtakavarga: Bhinnashtakavarga (bindus of each of the 7 planets
    by sign) and Sarvashtakavarga (total bindus per sign and per house).

    Interpretation hints: SAV >28 in a sign = strong life area, <25 = weak;
    a planet with >=5 bindus in its own sign gives good results in its dasha,
    <=3 — weak results. SAV total is always 337 (built-in sanity check).
    """
    av = jc.ashtakavarga(params.date, params.time, params.utc_offset,
                         params.latitude, params.longitude)
    return json.dumps(av, ensure_ascii=False, indent=1)


@mcp.prompt(name="jyotish_full_analysis",
            description="Полный разбор карты рождения в традиции джйотиш")
def jyotish_full_analysis(date: str, time: str, utc_offset: str,
                          latitude: str, longitude: str, place: str = "") -> str:
    return f"""Проведи полный разбор ведической карты рождения (джйотиш).

Данные рождения: {date} {time}, UTC{'+' if not utc_offset.startswith('-') else ''}{utc_offset}, {latitude} {longitude} {place}

Шаги:
0. Если известен только город — вызови jyotish_find_place, возьми координаты
   и timezone (пояс на дату рождения посчитается автоматически).
1. Вызови jyotish_compute_chart — получи лагну, планеты, йоги, караки.
2. Вызови jyotish_vimshottari_dasha — получи периоды и текущую дашу.
3. Вызови jyotish_current_transits — проверь Саде Сати и ключевые транзиты.
4. Вызови jyotish_ashtakavarga — сила домов и планет в бинду.
5. По запросу тем: дети — jyotish_divisional_chart D7, карьера — D10,
   брак — D9, родители — D12, богатство — D2.

Затем дай интерпретацию в следующей структуре, тёплым живым языком:
— Лагна и рисунок личности (лагна, лагнеш, накшатра лагны).
— Главные йоги и что они означают практически.
— Сильные стороны и их тени (слабости как обратные стороны сильных сторон).
— Миссия жизни: по Атма Караке, её накшатре, оси Раху–Кету, 10-му дому.
— Кармический слой: ретроградные планеты, узлы, соединения с узлами.
— Периоды: прошедшие даши (предложи 3–4 контрольные точки биографии для
  проверки карты), текущий период и его характер, будущие светлые и
  трудные окна с датами.
— Практические выводы: что делать и чего не делать в текущий период.

Правила: не выдумывай позиции — используй только данные инструментов;
интерпретируй смело, но напомни, что это традиция, а не научный прогноз,
и что решения стоит принимать головой. Если лагна в первых или последних
2° знака — предупреди о чувствительности к точности времени рождения."""


if __name__ == "__main__":
    if USE_HTTP:
        # Remote connector endpoint will be  http(s)://<host>/mcp
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
