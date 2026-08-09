"""Jyotish (Vedic astrology) computation core.
 
Sidereal zodiac (Lahiri ayanamsa), whole-sign houses, Vimshottari dasha.
Uses Swiss Ephemeris (Moshier model — no ephemeris files needed).
"""
from __future__ import annotations
 
import datetime as dt
from typing import Optional
 
import swisseph as swe
 
swe.set_sid_mode(swe.SIDM_LAHIRI)
 
FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
 
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGNS_RU = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
            "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
 
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
 
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
 
# Vimshottari dasha: lord -> years, in natural order starting from Ketu
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
YEAR_DAYS = 365.25
 
PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
}
 
EXALTATION = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
DEBILITATION = {p: (s + 6) % 12 for p, s in EXALTATION.items()}
OWN_SIGNS = {
    "Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
    "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10],
}
MOOLATRIKONA = {"Sun": 4, "Moon": 1, "Mars": 0, "Mercury": 5, "Jupiter": 8, "Venus": 6, "Saturn": 10}
 
# Yogakaraka planet by lagna sign index
YOGAKARAKA = {3: "Mars", 4: "Mars", 1: "Saturn", 6: "Saturn", 9: "Venus", 10: "Venus"}
 
KARAKA_NAMES = ["Atma Karaka (AK)", "Amatya Karaka (AmK)", "Bhratri Karaka (BK)",
                "Matri Karaka (MK)", "Putra Karaka (PK)", "Gnati Karaka (GK)",
                "Dara Karaka (DK)"]
 
 
def _dms(deg: float) -> str:
    d = int(deg)
    m = int((deg - d) * 60)
    s = int(round(((deg - d) * 60 - m) * 60))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}°{m:02d}'{s:02d}\""
 
 
def julian_day(date_str: str, time_str: str, utc_offset: float) -> float:
    """Local date/time + UTC offset -> Julian day (UT)."""
    local = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    ut = local - dt.timedelta(hours=utc_offset)
    return swe.julday(ut.year, ut.month, ut.day,
                      ut.hour + ut.minute / 60.0 + ut.second / 3600.0)
 
 
def jd_to_date(jd: float) -> str:
    y, m, d, h = swe.revjul(jd)
    return f"{y:04d}-{m:02d}-{d:02d}"
 
 
def nakshatra_of(lon: float) -> dict:
    span = 360.0 / 27.0
    idx = int(lon // span)
    within = lon - idx * span
    pada = int(within // (span / 4)) + 1
    lord = NAKSHATRA_LORDS[idx % 9]
    return {"name": NAKSHATRAS[idx], "pada": pada, "lord": lord,
            "fraction_traversed": within / span}
 
 
def navamsa_sign(lon: float) -> int:
    sign = int(lon // 30)
    deg_in_sign = lon - sign * 30
    part = int(deg_in_sign // (30.0 / 9.0))
    return (sign * 9 + part) % 12
 
 
def dignity_of(planet: str, sign: int) -> str:
    if planet not in EXALTATION:
        return "-"
    if sign == EXALTATION[planet]:
        return "exalted"
    if sign == DEBILITATION[planet]:
        return "debilitated"
    if sign in OWN_SIGNS[planet]:
        return "own sign"
    return "neutral"
 
 
def compute_positions(jd: float, lat: float, lon: float) -> dict:
    """Sidereal longitudes of lagna and 9 grahas."""
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"W", FLAGS)
    asc = ascmc[0] % 360.0
 
    positions = {"Ascendant": {"lon": asc, "retrograde": False}}
    for name, pid in PLANETS.items():
        xx, _ = swe.calc_ut(jd, pid, FLAGS)
        positions[name] = {"lon": xx[0] % 360.0, "retrograde": xx[3] < 0}
    xx, _ = swe.calc_ut(jd, swe.TRUE_NODE, FLAGS)
    rahu = xx[0] % 360.0
    positions["Rahu"] = {"lon": rahu, "retrograde": True}
    positions["Ketu"] = {"lon": (rahu + 180.0) % 360.0, "retrograde": True}
    return positions
 
 
def build_chart(date_str: str, time_str: str, utc_offset: float,
                lat: float, lon: float, place: str = "") -> dict:
    jd = julian_day(date_str, time_str, utc_offset)
    pos = compute_positions(jd, lat, lon)
    asc_lon = pos["Ascendant"]["lon"]
    asc_sign = int(asc_lon // 30)
 
    bodies = {}
    for name, p in pos.items():
        lon_p = p["lon"]
        sign = int(lon_p // 30)
        deg_in_sign = lon_p - sign * 30
        d9 = navamsa_sign(lon_p)
        house = (sign - asc_sign) % 12 + 1
        bodies[name] = {
            "sign": SIGNS_EN[sign], "sign_ru": SIGNS_RU[sign], "sign_index": sign,
            "degree_in_sign": round(deg_in_sign, 4), "degree_dms": _dms(deg_in_sign),
            "house": house if name != "Ascendant" else 1,
            "nakshatra": nakshatra_of(lon_p),
            "navamsa_sign": SIGNS_EN[d9], "navamsa_sign_ru": SIGNS_RU[d9],
            "vargottama": d9 == sign,
            "retrograde": p["retrograde"],
            "dignity": dignity_of(name, sign),
            "longitude": round(lon_p, 4),
        }
 
    # Five-fold relationship (pancha-dha maitri) with each planet's dispositor
    _signs = {p: bodies[p]["sign_index"] for p in PLANETS}
    for p in PLANETS:
        rel = relationship_with_dispositor(p, _signs[p], _signs)
        if rel:
            bodies[p]["relationship_with_dispositor"] = rel
 
    # Jaimini karakas: 7 planets by degree-in-sign descending (Rahu excluded, 7-karaka scheme)
    ranked = sorted(PLANETS.keys(),
                    key=lambda n: bodies[n]["degree_in_sign"], reverse=True)
    karakas = {KARAKA_NAMES[i]: ranked[i] for i in range(7)}
 
    chart = {
        "input": {"date": date_str, "time": time_str, "utc_offset": utc_offset,
                  "latitude": lat, "longitude": lon, "place": place,
                  "ayanamsa": "Lahiri", "houses": "whole sign",
                  "ayanamsa_value": round(swe.get_ayanamsa_ut(jd), 4)},
        "ascendant": bodies["Ascendant"],
        "planets": {k: v for k, v in bodies.items() if k != "Ascendant"},
        "karakas": karakas,
        "yogas": detect_yogas(bodies, asc_sign),
    }
    return chart
 
 
def detect_yogas(bodies: dict, asc_sign: int) -> dict:
    yogas = {}
    kendra_houses = {1, 4, 7, 10}
 
    # Mahapurusha yogas
    mp_names = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
                "Venus": "Malavya", "Saturn": "Shasha"}
    found = []
    for planet, yname in mp_names.items():
        b = bodies[planet]
        if b["house"] in kendra_houses and b["dignity"] in ("own sign", "exalted"):
            found.append({"yoga": f"{yname} (Mahapurusha)", "planet": planet,
                          "detail": f"{planet} in {b['sign']} ({b['dignity']}) in house {b['house']}"})
    yogas["mahapurusha"] = found
 
    # Gajakesari: Jupiter in kendra from Moon
    moon_sign = bodies["Moon"]["sign_index"]
    jup_sign = bodies["Jupiter"]["sign_index"]
    diff = (jup_sign - moon_sign) % 12
    yogas["gajakesari"] = diff in (0, 3, 6, 9)
 
    # Yogakaraka
    yk = YOGAKARAKA.get(asc_sign)
    if yk:
        b = bodies[yk]
        yogas["yogakaraka"] = {"planet": yk, "house": b["house"], "sign": b["sign"],
                               "dignity": b["dignity"], "retrograde": b["retrograde"]}
    else:
        yogas["yogakaraka"] = None
 
    # Debilitated planets + neecha bhanga conditions (simplified classical checks)
    nb = []
    for planet in PLANETS:
        b = bodies[planet]
        if b["dignity"] != "debilitated":
            continue
        sign = b["sign_index"]
        conds = []
        disp = SIGN_LORDS[sign]
        exalt_lord = next((p for p, s in EXALTATION.items() if s == sign), None)
        if disp in bodies and bodies[disp]["house"] in kendra_houses:
            conds.append(f"dispositor {disp} in kendra from lagna")
        if exalt_lord and bodies[exalt_lord]["house"] in kendra_houses:
            conds.append(f"exaltation lord of the sign ({exalt_lord}) in kendra from lagna")
        if b["vargottama"]:
            conds.append("planet is vargottama")
        nb.append({"planet": planet, "sign": b["sign"],
                   "neecha_bhanga_conditions": conds,
                   "neecha_bhanga": len(conds) > 0})
    yogas["debilitations"] = nb
 
    # Kemadruma check (no planets in 2nd/12th from Moon, excluding Sun/nodes)
    moon = bodies["Moon"]["sign_index"]
    flanks = {(moon + 1) % 12, (moon - 1) % 12}
    has_flank = any(bodies[p]["sign_index"] in flanks
                    for p in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"])
    yogas["kemadruma"] = not has_flank
 
    return yogas
 
 
def vimshottari_dasha(date_str: str, time_str: str, utc_offset: float,
                      lat: float, lon: float,
                      target_date: Optional[str] = None,
                      levels: int = 3) -> dict:
    """Vimshottari dasha tree.
 
    Returns all mahadashas, antardashas of every mahadasha, and
    pratyantardashas for the period containing target_date (default: today).
    """
    jd_birth = julian_day(date_str, time_str, utc_offset)
    pos = compute_positions(jd_birth, lat, lon)
    moon_lon = pos["Moon"]["lon"]
    nak = nakshatra_of(moon_lon)
 
    start_lord = nak["lord"]
    start_idx = DASHA_ORDER.index(start_lord)
    balance = (1.0 - nak["fraction_traversed"]) * DASHA_YEARS[start_lord]
 
    if target_date is None:
        target_jd = swe.julday(*dt.date.today().timetuple()[:3], 12.0)
    else:
        td = dt.datetime.strptime(target_date, "%Y-%m-%d")
        target_jd = swe.julday(td.year, td.month, td.day, 12.0)
 
    def sub_periods(lord: str, start_jd: float, span_years: float):
        """Split a period into 9 sub-periods starting from its own lord."""
        idx = DASHA_ORDER.index(lord)
        out = []
        cur = start_jd
        for i in range(9):
            sub = DASHA_ORDER[(idx + i) % 9]
            span = span_years * DASHA_YEARS[sub] / 120.0
            out.append({"lord": sub, "start_jd": cur, "years": span})
            cur += span * YEAR_DAYS
        return out
 
    # Mahadashas
    mahadashas = []
    cur = jd_birth
    first_span = balance
    for i in range(9):
        lord = DASHA_ORDER[(start_idx + i) % 9]
        span = first_span if i == 0 else DASHA_YEARS[lord]
        full = DASHA_YEARS[lord]
        md_start_full = cur - (full - span) * YEAR_DAYS  # notional full-period start (for i==0)
        mahadashas.append({"lord": lord, "start_jd": cur, "years": span,
                           "full_start_jd": md_start_full, "full_years": full})
        cur += span * YEAR_DAYS
 
    result_md = []
    current = {}
    for md in mahadashas:
        md_end = md["start_jd"] + md["years"] * YEAR_DAYS
        entry = {"maha_dasha": md["lord"],
                 "start": jd_to_date(md["start_jd"]), "end": jd_to_date(md_end)}
        # antardashas computed on the notional full period, clipped to actual
        ads = sub_periods(md["lord"], md["full_start_jd"], md["full_years"])
        ad_list = []
        for ad in ads:
            ad_end = ad["start_jd"] + ad["years"] * YEAR_DAYS
            if ad_end <= md["start_jd"]:
                continue  # elapsed before birth
            a_start = max(ad["start_jd"], md["start_jd"])
            ad_entry = {"antar_dasha": ad["lord"],
                        "start": jd_to_date(a_start), "end": jd_to_date(ad_end)}
            if levels >= 3 and ad["start_jd"] <= target_jd < ad_end and md["start_jd"] <= target_jd < md_end:
                pds = sub_periods(ad["lord"], ad["start_jd"], ad["years"])
                pd_list = []
                for pd in pds:
                    pd_end = pd["start_jd"] + pd["years"] * YEAR_DAYS
                    pd_entry = {"pratyantar_dasha": pd["lord"],
                                "start": jd_to_date(pd["start_jd"]), "end": jd_to_date(pd_end)}
                    if pd["start_jd"] <= target_jd < pd_end:
                        pd_entry["active_on_target_date"] = True
                        current = {"maha_dasha": md["lord"], "antar_dasha": ad["lord"],
                                   "pratyantar_dasha": pd["lord"],
                                   "target_date": jd_to_date(target_jd)}
                    pd_list.append(pd_entry)
                ad_entry["pratyantar_dashas"] = pd_list
                ad_entry["active_on_target_date"] = True
            ad_list.append(ad_entry)
        entry["antar_dashas"] = ad_list
        if md["start_jd"] <= target_jd < md_end:
            entry["active_on_target_date"] = True
        result_md.append(entry)
 
    return {
        "moon_nakshatra": nak["name"], "moon_nakshatra_lord": start_lord,
        "balance_of_first_dasha_years": round(balance, 3),
        "current_period": current,
        "mahadashas": result_md,
    }
 
 
def current_transits(date_str: str, time_str: str, utc_offset: float,
                     lat: float, lon: float,
                     on_date: Optional[str] = None) -> dict:
    """Transit snapshot: sidereal positions today + Sade Sati status + houses from lagna/Moon."""
    jd_birth = julian_day(date_str, time_str, utc_offset)
    natal = compute_positions(jd_birth, lat, lon)
    asc_sign = int(natal["Ascendant"]["lon"] // 30)
    moon_sign = int(natal["Moon"]["lon"] // 30)
 
    if on_date is None:
        today = dt.date.today()
        jd_t = swe.julday(today.year, today.month, today.day, 12.0)
    else:
        td = dt.datetime.strptime(on_date, "%Y-%m-%d")
        jd_t = swe.julday(td.year, td.month, td.day, 12.0)
 
    transits = {}
    for name, pid in list(PLANETS.items()):
        xx, _ = swe.calc_ut(jd_t, pid, FLAGS)
        lon_t = xx[0] % 360.0
        sign = int(lon_t // 30)
        transits[name] = {
            "sign": SIGNS_EN[sign], "sign_ru": SIGNS_RU[sign],
            "degree_dms": _dms(lon_t - sign * 30),
            "retrograde": xx[3] < 0,
            "house_from_lagna": (sign - asc_sign) % 12 + 1,
            "house_from_moon": (sign - moon_sign) % 12 + 1,
        }
    xx, _ = swe.calc_ut(jd_t, swe.TRUE_NODE, FLAGS)
    rahu_lon = xx[0] % 360.0
    for name, lon_t in (("Rahu", rahu_lon), ("Ketu", (rahu_lon + 180) % 360)):
        sign = int(lon_t // 30)
        transits[name] = {
            "sign": SIGNS_EN[sign], "sign_ru": SIGNS_RU[sign],
            "degree_dms": _dms(lon_t - sign * 30), "retrograde": True,
            "house_from_lagna": (sign - asc_sign) % 12 + 1,
            "house_from_moon": (sign - moon_sign) % 12 + 1,
        }
 
    sat_from_moon = transits["Saturn"]["house_from_moon"]
    sade_sati = {12: "phase 1 (rising, Saturn in 12th from Moon)",
                 1: "phase 2 (peak, Saturn over natal Moon)",
                 2: "phase 3 (setting, Saturn in 2nd from Moon)"}.get(sat_from_moon)
 
    return {
        "date": jd_to_date(jd_t),
        "natal_moon_sign": SIGNS_EN[moon_sign],
        "natal_lagna_sign": SIGNS_EN[asc_sign],
        "transits": transits,
        "sade_sati": {"active": sade_sati is not None, "phase": sade_sati},
        "saturn_return": transits["Saturn"]["sign"] == SIGNS_EN[int(natal["Saturn"]["lon"] // 30)],
    }
 
 
# ---------------------------------------------------------------------------
# Ashtakavarga (Parashari bindu tables)
# For each planet's BAV: houses (counted from each contributor's natal sign)
# where the contributor grants one bindu. "Asc" = lagna sign.
# Column sums: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56, Venus 52,
# Saturn 39 — total SAV is always 337.
# ---------------------------------------------------------------------------
BAV_TABLES = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11], "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11], "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11], "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Asc": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11], "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11], "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12], "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11], "Asc": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11], "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11], "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12], "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11], "Asc": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12], "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11], "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12], "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Asc": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11], "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11], "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11], "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12], "Asc": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12], "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 5, 6, 9, 11, 12], "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11], "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11], "Asc": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11], "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12], "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12], "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11], "Asc": [1, 3, 4, 6, 10, 11],
    },
}
 
 
def ashtakavarga(date_str: str, time_str: str, utc_offset: float,
                 lat: float, lon: float) -> dict:
    """Bhinnashtakavarga (BAV) for the 7 planets and Sarvashtakavarga (SAV)."""
    jd = julian_day(date_str, time_str, utc_offset)
    pos = compute_positions(jd, lat, lon)
    ref_signs = {p: int(pos[p]["lon"] // 30) for p in PLANETS}
    ref_signs["Asc"] = int(pos["Ascendant"]["lon"] // 30)
    asc_sign = ref_signs["Asc"]
 
    bav = {}
    for planet, table in BAV_TABLES.items():
        per_sign = [0] * 12
        for contributor, houses in table.items():
            c_sign = ref_signs[contributor]
            for h in houses:
                per_sign[(c_sign + h - 1) % 12] += 1
        bav[planet] = {
            "bindus_by_sign": {SIGNS_EN[i]: per_sign[i] for i in range(12)},
            "in_own_sign": per_sign[ref_signs[planet]],
            "total": sum(per_sign),
        }
 
    sav = [sum(bav[p]["bindus_by_sign"][SIGNS_EN[i]] for p in BAV_TABLES)
           for i in range(12)]
    return {
        "bav": bav,
        "sav": {
            "bindus_by_sign": {SIGNS_EN[i]: sav[i] for i in range(12)},
            "bindus_by_house": {f"house_{(i - asc_sign) % 12 + 1}": sav[i] for i in range(12)},
            "total": sum(sav),
        },
        "note": ("SAV: >28 bindus in a sign = strong area; <25 = weak. "
                 "BAV of a planet in its sign: >=5 strong, <=3 weak. Total is always 337."),
    }
 
 
# ---------------------------------------------------------------------------
# Divisional charts (vargas)
# ---------------------------------------------------------------------------
def varga_sign(lon: float, varga: str) -> int:
    """Sign index of a longitude in a given divisional chart."""
    sign = int(lon // 30)
    deg = lon - sign * 30
    odd = sign % 2 == 0  # Aries=0 is odd sign in astrology terms
 
    if varga == "D1":
        return sign
    if varga == "D2":  # hora: halves belong to Leo (Sun) / Cancer (Moon)
        if odd:
            return 4 if deg < 15 else 3
        return 3 if deg < 15 else 4
    if varga == "D3":  # drekkana: 1st -> same, 2nd -> +4, 3rd -> +8
        return (sign + int(deg // 10) * 4) % 12
    if varga == "D7":  # saptamsha: odd from same sign, even from 7th
        part = int(deg // (30.0 / 7.0))
        start = sign if odd else (sign + 6) % 12
        return (start + part) % 12
    if varga == "D9":
        return navamsa_sign(lon)
    if varga == "D10":  # dashamsha: odd from same sign, even from 9th
        part = int(deg // 3.0)
        start = sign if odd else (sign + 8) % 12
        return (start + part) % 12
    if varga == "D12":  # dwadashamsha: from the sign itself
        part = int(deg // 2.5)
        return (sign + part) % 12
    raise ValueError(f"Unsupported varga: {varga}. Use D1,D2,D3,D7,D9,D10,D12")
 
 
VARGA_MEANINGS = {
    "D2": "wealth (hora)", "D3": "siblings, courage (drekkana)",
    "D7": "children (saptamsha)", "D9": "marriage, dharma (navamsha)",
    "D10": "career, public deeds (dashamsha)", "D12": "parents (dwadashamsha)",
}
 
 
def divisional_chart(date_str: str, time_str: str, utc_offset: float,
                     lat: float, lon: float, varga: str) -> dict:
    """Positions of lagna and all grahas in a divisional chart."""
    varga = varga.upper()
    jd = julian_day(date_str, time_str, utc_offset)
    pos = compute_positions(jd, lat, lon)
    v_asc = varga_sign(pos["Ascendant"]["lon"], varga)
 
    placements = {}
    for name in list(PLANETS) + ["Rahu", "Ketu"]:
        v_sign = varga_sign(pos[name]["lon"], varga)
        placements[name] = {
            "sign": SIGNS_EN[v_sign], "sign_ru": SIGNS_RU[v_sign],
            "house_from_varga_lagna": (v_sign - v_asc) % 12 + 1,
            "dignity": dignity_of(name, v_sign),
        }
    return {
        "varga": varga,
        "meaning": VARGA_MEANINGS.get(varga, ""),
        "ascendant": {"sign": SIGNS_EN[v_asc], "sign_ru": SIGNS_RU[v_asc]},
        "planets": placements,
    }
 
 
# ---------------------------------------------------------------------------
# Pancha-dha maitri — five-fold planetary relationship with the dispositor
# (natural + temporal). Nodes are excluded: traditions differ on their scheme.
# ---------------------------------------------------------------------------
NATURAL_FRIENDS = {
    "Sun": ["Moon", "Mars", "Jupiter"],
    "Moon": ["Sun", "Mercury"],
    "Mars": ["Sun", "Moon", "Jupiter"],
    "Mercury": ["Sun", "Venus"],
    "Jupiter": ["Sun", "Moon", "Mars"],
    "Venus": ["Mercury", "Saturn"],
    "Saturn": ["Mercury", "Venus"],
}
NATURAL_ENEMIES = {
    "Sun": ["Venus", "Saturn"],
    "Moon": [],
    "Mars": ["Mercury"],
    "Mercury": ["Moon"],
    "Jupiter": ["Mercury", "Venus"],
    "Venus": ["Sun", "Moon"],
    "Saturn": ["Sun", "Moon", "Mars"],
}
 
 
def _natural_relation(a: str, b: str) -> int:
    """+1 friend, 0 neutral, -1 enemy (as seen from planet a)."""
    if b in NATURAL_FRIENDS.get(a, []):
        return 1
    if b in NATURAL_ENEMIES.get(a, []):
        return -1
    return 0
 
 
def _temporal_relation(sign_a: int, sign_b: int) -> int:
    """Temporal friendship: houses 2,3,4,10,11,12 from a planet are friendly."""
    house = (sign_b - sign_a) % 12 + 1
    return 1 if house in (2, 3, 4, 10, 11, 12) else -1
 
 
COMPOUND = {2: "great friend", 1: "friend", 0: "neutral", -1: "enemy", -2: "great enemy"}
COMPOUND_RU = {2: "Большой друг", 1: "Друг", 0: "Нейтрально",
               -1: "Враг", -2: "Большой враг"}
 
 
def relationship_with_dispositor(planet: str, sign: int, positions_signs: dict) -> dict | None:
    """Five-fold relationship between a planet and the lord of the sign it occupies."""
    if planet not in NATURAL_FRIENDS:
        return None
    lord = SIGN_LORDS[sign]
    if lord == planet:
        return {"dispositor": lord, "relation": "own sign", "relation_ru": "Свой знак"}
    score = _natural_relation(planet, lord) + _temporal_relation(sign, positions_signs[lord])
    score = max(-2, min(2, score))
    return {"dispositor": lord,
            "natural": COMPOUND[max(-1, min(1, _natural_relation(planet, lord)))],
            "temporal": "friend" if _temporal_relation(sign, positions_signs[lord]) == 1 else "enemy",
            "relation": COMPOUND[score], "relation_ru": COMPOUND_RU[score]}
