"""Offline city lookup + historical timezone offsets."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import geonamescache

_gc = geonamescache.GeonamesCache()
_countries = _gc.get_countries()


def search_city(query: str, limit: int = 8) -> list[dict]:
    """Search cities (population >= 15000, worldwide) by name substring."""
    q = query.strip().lower()
    hits = []
    for c in _gc.get_cities().values():
        names = [c["name"].lower()] + [a.lower() for a in c.get("alternatenames", [])]
        if any(q == n for n in names):
            score = 2
        elif any(q in n for n in names):
            score = 1
        else:
            continue
        hits.append((score, c.get("population", 0), c))
    hits.sort(key=lambda t: (-t[0], -t[1]))
    out = []
    for _, _, c in hits[:limit]:
        country = _countries.get(c["countrycode"], {}).get("name", c["countrycode"])
        out.append({
            "name": c["name"], "country": country,
            "latitude": c["latitude"], "longitude": c["longitude"],
            "timezone": c["timezone"], "population": c.get("population", 0),
        })
    return out


def utc_offset_for(timezone: str, date_str: str, time_str: str) -> float:
    """Historical UTC offset (hours) in effect at that timezone on that local datetime.

    Uses the IANA tz database, which includes historical rules
    (e.g. Soviet decree + summer time).
    """
    local = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    aware = local.replace(tzinfo=ZoneInfo(timezone))
    return aware.utcoffset().total_seconds() / 3600.0
