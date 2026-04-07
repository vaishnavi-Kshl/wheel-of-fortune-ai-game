# Fortune Spin Arena (Wheel of Fortune Style)

A full Wheel-of-Fortune-inspired spin wheel game built with a **Python backend** and a browser frontend.

## What is included

- Fully playable browser game
- Wheel spin animation + segment logic (`cash`, `BANKRUPT`, `LOSE TURN`)
- Puzzle board with category-based phrases
- Consonant guessing (requires spin), vowel purchase system
- Solve-the-puzzle flow with bonuses/penalties
- Persistent backend scoring + sessions (JSON storage)
- Resume session via session ID
- Replay support (create a new round from an existing session)
- Leaderboard for completed rounds
- Session timeline/history of actions

## Tech stack

- Frontend: Vanilla JavaScript + HTML/CSS
- Backend: Python + FastAPI
- Persistence: Local JSON file (`data/store.json`)

## Project structure

- `app.py` - FastAPI backend + game/state APIs + static file hosting
- `public/index.html` - UI markup
- `public/styles.css` - responsive styling
- `public/app.js` - game logic + API integration + wheel rendering/animation
- `requirements.txt` - Python dependencies
- `docs/PROMPT_HISTORY.md` - prompt and iteration history
- `docs/DEMO_SCRIPT.md` - 2-3 minute demo flow

## Run locally

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start server:

```bash
uvicorn app:app --reload --port 3000
```

Then open:

```text
http://localhost:3000
```

## API overview

- `GET /api/config` - wheel config + puzzle metadata
- `POST /api/session` - create session
- `GET /api/session/:id` - load/resume session
- `POST /api/session/:id/spin` - spin wheel
- `POST /api/session/:id/guess` - guess consonant or buy vowel
- `POST /api/session/:id/solve` - solve puzzle
- `POST /api/session/:id/replay` - start replay round
- `GET /api/session/:id/history` - full action log
- `GET /api/leaderboard` - top scores

## Mapping to challenge requirements

### Part 1 - Basic implementation

- Playable, no-crash core gameplay loop
- Functional UI and controls
- Correct core mechanics for spin/guess/solve

### Part 2 - System expansion

- Persistent scoring and leaderboard
- Session creation and tracking
- Backend-driven game configuration
- Frontend/backend synchronized state transitions
- Resume and replay session features

## Notes

- Data is stored in `data/store.json`.
- For production use, migrate JSON storage to PostgreSQL/MongoDB and add authentication.
