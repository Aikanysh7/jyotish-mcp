# jyotish-mcp

**A Vedic astrology (Jyotish) MCP server for Claude.** Precise Swiss-Ephemeris
calculations — birth chart, divisional charts, Vimshottari dashas, transits,
Ashtakavarga — exposed as tools so the model interprets real data instead of
inventing planetary positions.

LLMs are good at interpretation and bad at ephemeris arithmetic: ask any chatbot
for a chart and it will confidently hallucinate degrees, nakshatras and dasha
dates. This server closes that gap.

## Try it (no installation)

Add it in Claude: **Settings → Connectors → Add custom connector**

```
https://jyotish-mcp-h6px.onrender.com/mcp
```

Then just ask, in any language:

> Analyse my chart: 15 August 1975, 06:30, Delhi

Claude resolves the city, applies the historically correct timezone, computes
everything and writes the reading. *(Free hosting tier — the first request after
idle time may take ~50 s to wake up.)*

## Tools

| Tool | What it returns |
|---|---|
| `jyotish_find_place` | Coordinates + IANA timezone for a city (offline database) |
| `jyotish_compute_chart` | D1 + D9: ascendant, 9 grahas, nakshatras & padas, dignity, vargottama, retrogradation, five-fold relationship with dispositor, Jaimini karakas, yogas (Mahapurusha, Gajakesari, yogakaraka, neecha bhanga, Kemadruma) |
| `jyotish_vimshottari_dasha` | Maha / antar / pratyantar dashas, active period for any date |
| `jyotish_current_transits` | Transit positions by house from lagna and Moon, Sade Sati phase, Saturn return |
| `jyotish_ashtakavarga` | BAV per planet + SAV per sign and per house |
| `jyotish_divisional_chart` | D2, D3, D7, D9, D10, D12 |

Two prompts are included: `jyotish_full_analysis` and `jyotish_short_reading`.
Presentation rules are embedded in the tool descriptions, so readings come out
as prose with every term explained — not as a data dump.

## Conventions & accuracy

Sidereal zodiac, **Lahiri** ayanamsa · **whole-sign** houses · **true** nodes ·
Swiss Ephemeris (Moshier model, no data files needed).

Verified against professional Jyotish software on independent charts: planetary
positions match to arc-seconds, dasha boundaries to the day, Ashtakavarga bindu
for bindu (SAV always sums to 337 — a built-in sanity check).

Historical timezones come from the IANA database, so Soviet decree/summer time
and similar rules are applied automatically — the single most common source of
wrong charts.

## Self-hosting

Remote (Docker / Render / any PaaS):

```bash
docker build -t jyotish-mcp . && docker run -p 8000:8000 jyotish-mcp
# endpoint: http://localhost:8000/mcp
```

Local (stdio, Claude Desktop): `pip install -r requirements.txt && python server.py`
— then add it to `claude_desktop_config.json`. See `DEPLOY.md`.

## Limitations

Shad-bala is not implemented. Rahu/Ketu are excluded from the planetary
relationship calculation (traditions differ). Divisional charts are limited to
the six listed. The public endpoint has no authentication — anyone with the URL
can use it; no birth data is stored or logged (see `PRIVACY.md`).

Charts with an ascendant in the first or last degrees of a sign are sensitive to
birth-time accuracy; the server flags this so the model can warn the user.

## Disclaimer

This is an interpretation within the Jyotish tradition, not a scientific
forecast. Nothing here should be used as medical, legal or financial advice.

## License

MIT

---

## По-русски

MCP-сервер для ведической астрологии: считает карту рождения, дроби, периоды
Вимшоттари, транзиты и аштакаваргу по швейцарским эфемеридам, а Claude делает
интерпретацию. Айанамша Лахири, дома whole sign, истинные узлы.

Подключение без установки: **Settings → Connectors → Add custom connector** и
адрес `https://jyotish-mcp-h6px.onrender.com/mcp`. Дальше достаточно написать
в чат: «Разбери карту: 15 августа 1975, 06:30, Дели» — город, исторический
часовой пояс и все расчёты подставятся сами.

Точность сверена с профессиональным джйотиш-софтом на независимых картах:
позиции до угловых секунд, даты периодов день в день, аштакаварга бинду в бинду.

Разбор — интерпретация в рамках традиции, а не научный прогноз.
