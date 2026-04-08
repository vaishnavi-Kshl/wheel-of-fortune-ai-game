# Fortune Spin Arena (Wheel of Fortune Style)

A full Wheel-of-Fortune-inspired spin wheel game built with a **Python backend** and a browser frontend.

## What is included

- Fully playable browser game
- Wheel spin animation + segment logic (`cash`, `BANKRUPT`, `LOSE TURN`)
- Puzzle board with category-based phrases
- Consonant guessing (requires spin), vowel purchase system
- Solve-the-puzzle flow with bonuses/penalties
- Persistent backend scoring + sessions (SQLite database)
- Resume session via session ID
- Replay support (create a new round from an existing session)
- Leaderboard for completed rounds
- Session timeline/history of actions

## Tech stack

- Frontend: Vanilla JavaScript + HTML/CSS
- Backend: Python + FastAPI
- Persistence: SQLite (`data/game.db`)

## Project structure

- `app.py` - FastAPI backend + game/state APIs + static file hosting
- `public/index.html` - UI markup
- `public/styles.css` - responsive styling
- `public/app.js` - game logic + API integration + wheel rendering/animation
- `requirements.txt` - Python dependencies
- `PROMPT_HISTORY.md` - prompt and iteration history
- `DEMO_SCRIPT.md` - 2-3 minute demo flow

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

## Get One Public Link (Anyone Can Access)

### Option A: Deploy to Render (recommended)

1. Push this project to a GitHub repository.
2. Go to Render dashboard and click `New +` -> `Blueprint`.
3. Select your repo (this project includes `render.yaml`).
4. Click deploy.
5. Render will give you a public URL like:
   `https://fortune-spin-arena.onrender.com`

Notes:
- The app is already configured for Render with:
  - `render.yaml`
  - `Procfile`
- SQLite on free hosting may be ephemeral, so data can reset after restarts.

### Option B: Temporary public link from your laptop (quick demo)

Start your app locally:

```bash
uvicorn app:app --reload --port 3000
```

Then run:

```bash
ssh -R 80:localhost:3000 nokey@localhost.run
```

This gives a public URL instantly, but it is temporary (good for sharing demos).

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

- Data is stored in `data/game.db`.
- On startup, legacy `data/store.json` data is auto-migrated into SQLite if present.
- For production use, consider PostgreSQL and add authentication.
