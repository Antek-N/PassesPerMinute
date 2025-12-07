# PassesPerMinute

A Python analytical toolkit that computes the **average number of passes per minute by player position** using data from **StatsBomb Open Data** (2009–2024).  
The project focuses on automated data fetching, positional event aggregation, and visual reporting (bar charts and football pitch maps).

> **License:** `CC0-1.0`  
> **Requirements:** `Python 3.12–3.14`, `requests`, `matplotlib`

---

## Features

- **StatsBomb Open Data Integration**
  - Fetches event-level match data (passes, substitutions, lineups).
  - Supports filtering by competition and season.

- **Parallel Processing**
  - Uses `concurrent.futures` for efficient batch data processing.

- **Positional Analysis**
  - Tracks minutes and passes per player position across competitions.

- **Visualization**
  - Generates bar charts and football pitch heatmaps via `matplotlib`.

- **Structured Logging**
  - Unified logging configuration for all modules.

---

## Requirements & Dependencies

- **Python:** 3.12–3.14  
- **Runtime libraries:**  
  `requests`, `matplotlib`
- **Dev (optional):**  
  `pytest`, `black`, `ruff`, `mypy`, `pre-commit`, `mkdocs`, `mkdocstrings`

---

## Installation

### Using Poetry

**Users:**
```bash
poetry install --without dev
poetry run passesperminute
```

**Developers:**  (runtime + dev dependencies):
```bash
poetry install
poetry run passesperminute
```

### Using pip

**Users:**
```bash
pip install -r requirements.txt
pip install -e .
passesperminute
```

**Developers (runtime + dev dependencies):**
```bash
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

---

## Run (Quick Start)

```bash
python -m passes_per_minute
```

or

```bash
poetry run passesperminute
```

---

## Project Structure

```
src/passes_per_minute/
├─ __main__.py                # Entry point
├─ app.py                     # Core execution script (CLI)
├─ logging_config.py          # Logging setup
│
├─ passes_counter/            # Core analytical pipeline
│  ├─ competition_manager.py   # Competition & season selection
│  ├─ competition_processor.py # Parallel competition processing
│  ├─ http_client.py           # StatsBomb Open Data client
│  ├─ match_processor.py       # Match-level event aggregation
│  └─ player_position_stats.py # Position tracking and pass stats
│
└─ plotter/                   # Visualization components
   ├─ bar_chart.py             # Bar chart visualization
   └─ football_pitch_chart.py  # Football pitch heatmap
```

---

## Documentation

Full API reference:  
Full project documentation: **[API Reference -
passes_per_minute](reference/passes_per_minute/index.md)**.

To build or preview documentation locally:

```bash
mkdocs serve      # http://127.0.0.1:8000
mkdocs build      # build static site
```

---

## License

This project is released under **CC0-1.0** (public domain). You may
copy, modify, distribute, and use it commercially without additional
permissions.
