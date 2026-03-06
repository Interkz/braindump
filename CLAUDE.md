# Braindump — The Well

## Vision
A place where thoughts fall into a well and disappear. You dump text, links, ideas — they animate down into darkness and are gone. Behind the scenes, an LLM silently groups, tags, connects, and summarizes everything. When you want to see what's in the well, you get organized findings — not your messy notes.

## Pain Point
Notes scattered across Google Tasks, Apple Notes, physical notebooks, Google Docs. User hates organizing but wants organization.

## Design Philosophy
- Input is dead simple: one field, type/paste, hit enter, it falls away
- No visible lists, folders, categories, or tags in the input view
- The "well" is a dark animated void — things fall in and vanish
- Behind the scenes: Obsidian-like linking + NotebookLM-style summaries
- User only sees organization when they ask for it ("What do I know about X?")

## Stack
- **Backend:** Python FastAPI + SQLite
- **Frontend:** Plain HTML/CSS/JS (no build tools)
- **LLM:** Claude API (background processing)
- **Deploy:** Vercel
- **Design:** Dark, minimal, the well is the hero element

## File Structure
```
braindump/
├── CLAUDE.md           # This file
├── requirements.txt    # Python deps
├── vercel.json         # Vercel config
├── src/
│   ├── main.py         # FastAPI app
│   ├── database.py     # SQLite models
│   ├── processor.py    # LLM categorization/summarization
│   └── templates/
│       ├── base.html   # Base template
│       ├── well.html   # Main input page (the well)
│       └── findings.html # Organized findings view
└── static/
    ├── style.css       # Dark theme + well animation
    └── well.js         # Drop animation + input handling
```

## Key Commands
```bash
pip install -r requirements.txt
uvicorn src.main:app --port 8080 --reload
```

## API Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /` | The well (input page) |
| `POST /api/drop` | Drop something into the well |
| `GET /api/findings` | Get organized findings |
| `GET /api/findings/{topic}` | Get findings for a topic |
| `GET /findings` | Findings page (HTML) |
| `POST /api/process` | Trigger LLM processing |

## Database Schema

### drops
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| content | TEXT | Raw text/link/idea |
| content_type | TEXT | 'text', 'link', 'idea' |
| dropped_at | DATETIME | When it was dropped |
| processed | BOOLEAN | Has LLM processed it |

### topics
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Topic name (LLM-generated) |
| summary | TEXT | Rolling summary |
| updated_at | DATETIME | Last updated |

### drop_topics
| Column | Type | Description |
|--------|------|-------------|
| drop_id | INTEGER | FK to drops |
| topic_id | INTEGER | FK to topics |
| relevance | REAL | 0-1 relevance score |
