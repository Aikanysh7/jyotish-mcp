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
    dignity own/exalted/debilitated, navamsa sign, vargottama flag,
    five-fold relationship with its dispositor), Jaimini karakas (AK..DK),
    and detected yogas (Mahapurusha, Gajakesari, yogakaraka, neecha bhanga,
    Kemadruma).
 
    Accuracy: positions match professional Jyotish software to arc-seconds.
 
    HOW TO PRESENT THE RESULT TO THE USER (important — applies to every
    jyotish_* tool, and to short answers as well as full readings):
 
    - Write flowing prose in the user's language, the way a thoughtful
      astrologer speaks to a person. NOT tables, NOT bullet lists of planets,
      NOT a data dump. Tables are acceptable only for date/period calendars.
    - Never print raw JSON, degrees to arc-seconds, or field names.
      Mention a degree only when it actually matters (e.g. a planet at the
      very edge of a sign).
    - Translate every technical term the moment it appears: "Atma Karaka —
      the planet of the soul", "vargottama — the same sign in both charts,
      a sign of integrity". A reader who knows nothing about jyotish must
      still follow the whole reading.
    - Organise by the person's life, not by the data: who they are; strengths
      and the flip side of those strengths; calling and purpose; the current
      period and what to do in it; what lies ahead with concrete dates.
      Never structure the answer as "Sun: ... Moon: ... Mars: ...".
    - Interpret, don't enumerate. One vivid, well-explained conclusion beats
      ten technically correct labels. Combine factors instead of listing them.
    - Always give real dates ("until 23 January 2027"), never "in the coming
      period". Call jyotish_vimshottari_dasha for them.
    - Be warm and honest. Do not soften hard periods into nothing, but never
      predict catastrophes, illness, or death, and never frame anything as
      fated and unavoidable — describe the weather of a period and what the
      person can do about it. If the reading touches on a hard time, say
      plainly that decisions are best made with a clear head and that the
      chart is food for thought, not a verdict.
    - Close with a brief note that this is an interpretation within the
      jyotish tradition, not a scientific forecast — once, at the end, not
      repeated throughout.
    - If the ascendant falls within the first or last 2 degrees of a sign,
      warn that the birth time must be precise.
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
 
Затем напиши разбор — живым человеческим языком, как говорил бы вдумчивый
астролог с человеком, а не как отчёт программы.
 
КАК ПИСАТЬ (это важнее, чем полнота):
— Только связная проза. Никаких таблиц с планетами, никаких списков вида
  «Солнце: … Луна: … Марс: …». Таблица допустима лишь одна — календарь
  периодов с датами.
— Ни одного сырого термина без перевода прямо на месте: «Атма Карака —
  планета души», «варготтама — тот же знак и в основной карте, и в навамше,
  признак цельности». Человек, ничего не знающий о джйотише, должен понять
  всё до последней фразы.
— Не перечисляй факторы — соединяй их. Один яркий, хорошо объяснённый вывод
  ценнее десяти верных ярлыков.
— Всегда конкретные даты («до 23 января 2027»), а не «в ближайший период».
— Структура — по жизни человека, а не по данным карты:
  1) Кто он: лагна, лагнеш, характер — и сразу тени сильных сторон.
  2) Главные йоги — что они дают практически, без перечня названий.
  3) Миссия: Атма Карака, её накшатра, ось Раху–Кету, 10-й дом.
  4) Кармический слой: ретроградные планеты, узлы, соединения с узлами.
  5) Проверка картой биографии: предложи 3–4 датированные точки прошлого
     («примерно в такие-то годы должно было произойти вот что») и попроси
     подтвердить — это лучший способ убедиться в верности времени рождения.
  6) Текущий период: что за погода, что делать и чего не делать.
  7) Что впереди: светлые и трудные окна с датами.
 
ТОН: тепло и честно. Трудные периоды не замазывай, но и не пугай: описывай
погоду периода и что человек может с ней сделать. Никаких предсказаний
болезней, катастроф и смерти; ничего «неотвратимого». Если период тяжёлый —
скажи прямо, что важные решения лучше принимать со свежей головой.
 
ФАКТЫ: не выдумывай позиции — только данные инструментов. В самом конце
(один раз, не по ходу текста) напомни, что это интерпретация традиции, а не
научный прогноз. Если лагна в первых или последних 2° знака — предупреди о
чувствительности к точности времени рождения."""
 
 
@mcp.prompt(name="jyotish_short_reading",
            description="Короткий разбор карты: суть, текущий период, что делать")
def jyotish_short_reading(date: str, time: str, place: str = "",
                          latitude: str = "", longitude: str = "") -> str:
    return f"""Сделай короткий разбор ведической карты (джйотиш) — на 3–4 абзаца.
 
Данные рождения: {date} {time}, {place} {latitude} {longitude}
Если координаты не заданы — определи их через jyotish_find_place и передай
timezone (исторический пояс посчитается сам).
 
Вызови jyotish_compute_chart и jyotish_vimshottari_dasha. По желанию —
jyotish_current_transits для Саде Сати.
 
Напиши связной прозой, без таблиц, списков и без единого непереведённого
термина, ровно четыре вещи:
1. Кто этот человек в двух-трёх фразах — по лагне, её управителю и главной
   йоге. С тенью: сильная сторона и её обратная сторона.
2. Его призвание — по Атма Караке и 10-му дому, одним абзацем.
3. Что происходит сейчас: текущий период, его характер и конкретные даты
   начала и конца.
4. Один практический совет на ближайшие месяцы и одна дата, когда станет
   легче или откроется хорошее окно.
 
Тепло, по-человечески, без запугивания. В конце одной строкой — что это
традиция джйотиш, а не научный прогноз."""
 
 
if __name__ == "__main__":
    if USE_HTTP:
        # Remote connector endpoint will be  http(s)://<host>/mcp
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
