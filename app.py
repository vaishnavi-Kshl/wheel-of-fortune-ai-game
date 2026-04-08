from __future__ import annotations

import json
import random
import re
import sqlite3
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "game.db"
LEGACY_STORE_PATH = DATA_DIR / "store.json"

DEFAULT_WHEEL_SEGMENTS = [
    {"label": "500", "type": "cash", "value": 500, "color": "#f15c22"},
    {"label": "600", "type": "cash", "value": 600, "color": "#f2a007"},
    {"label": "700", "type": "cash", "value": 700, "color": "#87b33d"},
    {"label": "900", "type": "cash", "value": 900, "color": "#2ea96c"},
    {"label": "450", "type": "cash", "value": 450, "color": "#2a9d8f"},
    {"label": "LOSE TURN", "type": "lose_turn", "value": 0, "color": "#6b7280"},
    {"label": "800", "type": "cash", "value": 800, "color": "#2f7ec1"},
    {"label": "300", "type": "cash", "value": 300, "color": "#3f63bf"},
    {"label": "1000", "type": "cash", "value": 1000, "color": "#274c9f"},
    {"label": "BANKRUPT", "type": "bankrupt", "value": 0, "color": "#1f2937"},
    {"label": "550", "type": "cash", "value": 550, "color": "#da5b5b"},
    {"label": "650", "type": "cash", "value": 650, "color": "#d97706"},
]

DEFAULT_PUZZLES = [
    {"id": "p1", "category": "Phrase", "phrase": "BREAK A LEG", "difficulty": "easy"},
    {"id": "p2", "category": "Movie", "phrase": "BACK TO THE FUTURE", "difficulty": "medium"},
    {"id": "p3", "category": "Food", "phrase": "SPICY VEGETABLE CURRY", "difficulty": "medium"},
    {
        "id": "p4",
        "category": "Thing",
        "phrase": "WIRELESS NOISE CANCELLING HEADPHONES",
        "difficulty": "hard",
    },
    {"id": "p5", "category": "Place", "phrase": "GOLDEN GATE BRIDGE", "difficulty": "easy"},
    {"id": "p6", "category": "Event", "phrase": "INTERNATIONAL SPACE CONFERENCE", "difficulty": "hard"},
    {"id": "p7", "category": "Song", "phrase": "HERE COMES THE SUN", "difficulty": "easy"},
    {
        "id": "p8",
        "category": "Person",
        "phrase": "ARTIFICIAL INTELLIGENCE ENGINEER",
        "difficulty": "hard",
    },
    {"id": "p9", "category": "Phrase", "phrase": "NEVER STOP LEARNING", "difficulty": "easy"},
    {"id": "p10", "category": "Title", "phrase": "SENIOR SOFTWARE ARCHITECT", "difficulty": "medium"},
]

DEFAULT_STORE = {
    "config": {
        "wheelSegments": DEFAULT_WHEEL_SEGMENTS,
        "puzzles": DEFAULT_PUZZLES,
        "vowelCost": 250,
        "solveBonus": 1500,
        "autoRevealBonus": 1000,
        "penalties": {"failedSolve": 500},
    },
    "sessions": {},
    "leaderboard": [],
}

VOWELS = {"A", "E", "I", "O", "U"}
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]+$")
store_lock = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def format_coin(value: int) -> str:
    return f"{int(value)} coin"


def normalize_wheel_currency_labels(store: dict[str, Any]) -> bool:
    changed = False
    segments = store.get("config", {}).get("wheelSegments", [])
    for segment in segments:
        if segment.get("type") == "cash" and isinstance(segment.get("value"), int):
            expected = str(segment["value"])
            if segment.get("label") != expected:
                segment["label"] = expected
                changed = True
    return changed


def ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                wheel_segments_json TEXT NOT NULL,
                puzzles_json TEXT NOT NULL,
                vowel_cost INTEGER NOT NULL,
                solve_bonus INTEGER NOT NULL,
                auto_reveal_bonus INTEGER NOT NULL,
                penalties_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                player_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                score INTEGER NOT NULL,
                spins INTEGER NOT NULL,
                wrong_guesses INTEGER NOT NULL,
                guessed_letters_json TEXT NOT NULL,
                used_letters_json TEXT NOT NULL,
                pending_consonant_value INTEGER,
                last_spin_json TEXT,
                puzzle_json TEXT NOT NULL,
                masked_phrase TEXT NOT NULL,
                action_log_json TEXT NOT NULL,
                leaderboard_posted INTEGER NOT NULL DEFAULT 0,
                replay_of TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                puzzle_category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                spins INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL,
                completed_at TEXT NOT NULL
            )
            """
        )

        has_config = conn.execute("SELECT 1 FROM config WHERE id = 1").fetchone() is not None
        if not has_config:
            seed_store = deepcopy(DEFAULT_STORE)
            if LEGACY_STORE_PATH.exists():
                try:
                    parsed = json.loads(LEGACY_STORE_PATH.read_text(encoding="utf-8"))
                    if (
                        isinstance(parsed, dict)
                        and isinstance(parsed.get("config"), dict)
                        and isinstance(parsed.get("sessions"), dict)
                        and isinstance(parsed.get("leaderboard"), list)
                    ):
                        seed_store = parsed
                except Exception:
                    seed_store = deepcopy(DEFAULT_STORE)

            normalize_wheel_currency_labels(seed_store)
            _write_store_to_db(conn, seed_store)
            conn.commit()
            return

        store = _read_store_from_db(conn)
        if normalize_wheel_currency_labels(store):
            _write_store_to_db(conn, store)
            conn.commit()


def read_store() -> dict[str, Any]:
    if not DB_PATH.exists():
        ensure_store()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return _read_store_from_db(conn)
    except sqlite3.Error:
        ensure_store()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return _read_store_from_db(conn)


def write_store(store: dict[str, Any]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        _write_store_to_db(conn, store)
        conn.commit()


def _read_store_from_db(conn: sqlite3.Connection) -> dict[str, Any]:
    cfg_row = conn.execute(
        """
        SELECT wheel_segments_json, puzzles_json, vowel_cost, solve_bonus, auto_reveal_bonus, penalties_json
        FROM config
        WHERE id = 1
        """
    ).fetchone()

    if cfg_row is None:
        return deepcopy(DEFAULT_STORE)

    config = {
        "wheelSegments": json.loads(cfg_row["wheel_segments_json"]),
        "puzzles": json.loads(cfg_row["puzzles_json"]),
        "vowelCost": int(cfg_row["vowel_cost"]),
        "solveBonus": int(cfg_row["solve_bonus"]),
        "autoRevealBonus": int(cfg_row["auto_reveal_bonus"]),
        "penalties": json.loads(cfg_row["penalties_json"]),
    }

    sessions: dict[str, Any] = {}
    for row in conn.execute(
        """
        SELECT
            id, player_name, created_at, updated_at, status, score, spins, wrong_guesses,
            guessed_letters_json, used_letters_json, pending_consonant_value, last_spin_json,
            puzzle_json, masked_phrase, action_log_json, leaderboard_posted, replay_of
        FROM sessions
        """
    ):
        session = {
            "id": row["id"],
            "playerName": row["player_name"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "status": row["status"],
            "score": int(row["score"]),
            "spins": int(row["spins"]),
            "wrongGuesses": int(row["wrong_guesses"]),
            "guessedLetters": json.loads(row["guessed_letters_json"]),
            "usedLetters": json.loads(row["used_letters_json"]),
            "pendingConsonantValue": row["pending_consonant_value"],
            "lastSpin": json.loads(row["last_spin_json"]) if row["last_spin_json"] else None,
            "puzzle": json.loads(row["puzzle_json"]),
            "maskedPhrase": row["masked_phrase"],
            "actionLog": json.loads(row["action_log_json"]),
            "leaderboardPosted": bool(row["leaderboard_posted"]),
            "replayOf": row["replay_of"],
        }
        sessions[session["id"]] = session

    leaderboard: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT
            session_id, player_name, score, puzzle_category, difficulty, spins, duration_seconds, completed_at
        FROM leaderboard
        ORDER BY score DESC, duration_seconds ASC, id ASC
        """
    ):
        leaderboard.append(
            {
                "sessionId": row["session_id"],
                "playerName": row["player_name"],
                "score": int(row["score"]),
                "puzzleCategory": row["puzzle_category"],
                "difficulty": row["difficulty"],
                "spins": int(row["spins"]),
                "durationSeconds": int(row["duration_seconds"]),
                "completedAt": row["completed_at"],
            }
        )

    return {"config": config, "sessions": sessions, "leaderboard": leaderboard}


def _write_store_to_db(conn: sqlite3.Connection, store: dict[str, Any]) -> None:
    config = store.get("config") or deepcopy(DEFAULT_STORE["config"])
    sessions = store.get("sessions") or {}
    leaderboard = store.get("leaderboard") or []

    conn.execute(
        """
        INSERT INTO config (
            id, wheel_segments_json, puzzles_json, vowel_cost, solve_bonus, auto_reveal_bonus, penalties_json
        )
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            wheel_segments_json = excluded.wheel_segments_json,
            puzzles_json = excluded.puzzles_json,
            vowel_cost = excluded.vowel_cost,
            solve_bonus = excluded.solve_bonus,
            auto_reveal_bonus = excluded.auto_reveal_bonus,
            penalties_json = excluded.penalties_json
        """,
        (
            json.dumps(config.get("wheelSegments", [])),
            json.dumps(config.get("puzzles", [])),
            int(config.get("vowelCost", 250)),
            int(config.get("solveBonus", 1500)),
            int(config.get("autoRevealBonus", 1000)),
            json.dumps(config.get("penalties", {"failedSolve": 500})),
        ),
    )

    conn.execute("DELETE FROM sessions")
    for session in sessions.values():
        conn.execute(
            """
            INSERT INTO sessions (
                id, player_name, created_at, updated_at, status, score, spins, wrong_guesses,
                guessed_letters_json, used_letters_json, pending_consonant_value, last_spin_json,
                puzzle_json, masked_phrase, action_log_json, leaderboard_posted, replay_of
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["id"],
                session["playerName"],
                session["createdAt"],
                session["updatedAt"],
                session["status"],
                int(session["score"]),
                int(session["spins"]),
                int(session["wrongGuesses"]),
                json.dumps(session.get("guessedLetters", [])),
                json.dumps(session.get("usedLetters", [])),
                session.get("pendingConsonantValue"),
                json.dumps(session.get("lastSpin")) if session.get("lastSpin") is not None else None,
                json.dumps(session.get("puzzle", {})),
                session.get("maskedPhrase", ""),
                json.dumps(session.get("actionLog", [])),
                1 if session.get("leaderboardPosted") else 0,
                session.get("replayOf"),
            ),
        )

    conn.execute("DELETE FROM leaderboard")
    for row in leaderboard:
        conn.execute(
            """
            INSERT INTO leaderboard (
                session_id, player_name, score, puzzle_category, difficulty, spins, duration_seconds, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["sessionId"],
                row["playerName"],
                int(row["score"]),
                row["puzzleCategory"],
                row["difficulty"],
                int(row["spins"]),
                int(row["durationSeconds"]),
                row["completedAt"],
            ),
        )


def error_response(status: int, message: str, session: dict[str, Any] | None = None) -> JSONResponse:
    payload: dict[str, Any] = {"error": message}
    if session is not None:
        payload["session"] = sanitize_session(session)
    return JSONResponse(status_code=status, content=payload)


def is_letter(char: str) -> bool:
    return bool(re.match(r"^[A-Z]$", char))


def normalize_letter(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().upper()[:1]


def normalize_phrase(value: Any) -> str:
    phrase = str(value or "").upper()
    phrase = re.sub(r"[^A-Z0-9 ]+", "", phrase)
    phrase = re.sub(r"\s+", " ", phrase)
    return phrase.strip()


def mask_phrase(phrase: str, guessed_letters: list[str]) -> str:
    guessed = set(guessed_letters)
    output: list[str] = []
    for char in phrase:
        upper = char.upper()
        if not re.match(r"[A-Z]", upper):
            output.append(char)
        else:
            output.append(upper if upper in guessed else "_")
    return "".join(output)


def count_letters(phrase: str) -> int:
    return sum(1 for ch in phrase if re.match(r"[A-Z]", ch))


def count_revealed(masked_phrase: str) -> int:
    return sum(1 for ch in masked_phrase if re.match(r"[A-Z]", ch))


def is_solved(masked_phrase: str) -> bool:
    return "_" not in masked_phrase


def add_action(session: dict[str, Any], action_type: str, details: dict[str, Any]) -> None:
    session["actionLog"].append({"timestamp": utc_now_iso(), "type": action_type, "details": details})


def sanitize_session(session: dict[str, Any]) -> dict[str, Any]:
    phrase = session["puzzle"]["phrase"]
    return {
        "id": session["id"],
        "playerName": session["playerName"],
        "createdAt": session["createdAt"],
        "updatedAt": session["updatedAt"],
        "status": session["status"],
        "score": session["score"],
        "spins": session["spins"],
        "wrongGuesses": session["wrongGuesses"],
        "usedLetters": session["usedLetters"],
        "guessedLetters": session["guessedLetters"],
        "pendingConsonantValue": session["pendingConsonantValue"],
        "lastSpin": session["lastSpin"],
        "replayOf": session["replayOf"],
        "puzzle": {
            "category": session["puzzle"]["category"],
            "difficulty": session["puzzle"]["difficulty"],
            "maskedPhrase": session["maskedPhrase"],
            "totalLetters": count_letters(phrase),
            "revealedLetters": count_revealed(session["maskedPhrase"]),
            "phrase": phrase if session["status"] == "won" else None,
        },
        "actionLog": session["actionLog"][-20:],
    }


def pick_puzzle(config: dict[str, Any], difficulty: str) -> dict[str, Any]:
    puzzles = config["puzzles"]
    if not difficulty or difficulty == "any":
        return deepcopy(random.choice(puzzles))

    filtered = [p for p in puzzles if p.get("difficulty") == difficulty]
    if not filtered:
        return deepcopy(random.choice(puzzles))

    return deepcopy(random.choice(filtered))


def create_session(store: dict[str, Any], body: dict[str, Any], replay_of: str | None = None) -> dict[str, Any]:
    player_name = str(body.get("playerName") or "").strip()[:32]
    if not player_name:
        player_name = "Player 1"
    difficulty = str(body.get("difficulty") or "any").lower()
    puzzle = pick_puzzle(store["config"], difficulty)
    now = utc_now_iso()

    session = {
        "id": str(uuid4()),
        "playerName": player_name,
        "createdAt": now,
        "updatedAt": now,
        "status": "active",
        "score": 0,
        "spins": 0,
        "wrongGuesses": 0,
        "guessedLetters": [],
        "usedLetters": [],
        "pendingConsonantValue": None,
        "lastSpin": None,
        "puzzle": puzzle,
        "maskedPhrase": mask_phrase(puzzle["phrase"], []),
        "actionLog": [],
        "leaderboardPosted": False,
        "replayOf": replay_of,
    }

    add_action(
        session,
        "session_started",
        {"playerName": player_name, "difficulty": difficulty, "category": puzzle["category"]},
    )

    store["sessions"][session["id"]] = session
    return session


def update_leaderboard(store: dict[str, Any], session: dict[str, Any]) -> None:
    if session["status"] != "won":
        return

    if session.get("leaderboardPosted"):
        return

    duration_seconds = max(
        1,
        round(
            (
                datetime.fromisoformat(session["updatedAt"].replace("Z", "+00:00"))
                - datetime.fromisoformat(session["createdAt"].replace("Z", "+00:00"))
            ).total_seconds()
        ),
    )

    store["leaderboard"].append(
        {
            "sessionId": session["id"],
            "playerName": session["playerName"],
            "score": session["score"],
            "puzzleCategory": session["puzzle"]["category"],
            "difficulty": session["puzzle"]["difficulty"],
            "spins": session["spins"],
            "durationSeconds": duration_seconds,
            "completedAt": session["updatedAt"],
        }
    )

    store["leaderboard"].sort(key=lambda row: (-row["score"], row["durationSeconds"]))
    store["leaderboard"] = store["leaderboard"][:50]
    session["leaderboardPosted"] = True


def get_session_or_response(store: dict[str, Any], session_id: str) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    if not SESSION_ID_PATTERN.match(session_id):
        return None, error_response(404, "Session not found")

    session = store["sessions"].get(session_id)
    if not session:
        return None, error_response(404, "Session not found")

    return session, None


ensure_store()
app = FastAPI(title="Fortune Spin Arena API")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "wheel-of-fortune-api"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    with store_lock:
        store = read_store()

    categories = sorted({p["category"] for p in store["config"]["puzzles"]})
    difficulties = sorted({p["difficulty"] for p in store["config"]["puzzles"]})
    return {
        "wheelSegments": store["config"]["wheelSegments"],
        "vowelCost": store["config"]["vowelCost"],
        "solveBonus": store["config"]["solveBonus"],
        "autoRevealBonus": store["config"]["autoRevealBonus"],
        "categories": categories,
        "difficulties": difficulties,
        "puzzleCount": len(store["config"]["puzzles"]),
    }


@app.get("/api/leaderboard")
def leaderboard(limit: int = Query(default=10)) -> dict[str, Any]:
    bounded_limit = max(1, min(50, int(limit)))
    with store_lock:
        store = read_store()
    return {"leaderboard": store["leaderboard"][:bounded_limit]}


@app.post("/api/session", status_code=201)
def start_session(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    player_name = str(body.get("playerName") or "").strip()
    if not player_name:
        return error_response(400, "Player name is required")

    with store_lock:
        store = read_store()
        session = create_session(store, {**body, "playerName": player_name})
        write_store(store)
    return {"message": "Session created", "session": sanitize_session(session)}


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    with store_lock:
        store = read_store()
        session, error = get_session_or_response(store, session_id)
        if error:
            return error
        return {"session": sanitize_session(session)}


@app.get("/api/session/{session_id}/history")
def history(session_id: str):
    with store_lock:
        store = read_store()
        session, error = get_session_or_response(store, session_id)
        if error:
            return error
        return {"sessionId": session["id"], "actionLog": session["actionLog"]}


@app.post("/api/session/{session_id}/spin")
def spin(session_id: str):
    with store_lock:
        store = read_store()
        session, error = get_session_or_response(store, session_id)
        if error:
            return error

        if session["status"] != "active":
            return error_response(409, "Session is not active", session)

        if session["pendingConsonantValue"] is not None:
            return error_response(409, "Guess a consonant before spinning again", session)

        segments = store["config"]["wheelSegments"]
        segment_index = random.randrange(len(segments))
        segment = segments[segment_index]

        session["lastSpin"] = segment
        session["spins"] += 1
        session["updatedAt"] = utc_now_iso()

        message = (
            f"Wheel landed on {format_coin(segment['value'])}."
            if segment["type"] == "cash"
            else f"Wheel landed on {segment['label']}."
        )
        if segment["type"] == "cash":
            session["pendingConsonantValue"] = segment["value"]
            message = f"{format_coin(segment['value'])}! Guess a consonant."
        elif segment["type"] == "bankrupt":
            session["score"] = 0
            session["pendingConsonantValue"] = None
            message = "BANKRUPT! Score reset to 0."
        elif segment["type"] == "lose_turn":
            session["pendingConsonantValue"] = None
            message = "LOSE TURN! Spin again."

        add_action(session, "spin", {"segment": segment, "segmentIndex": segment_index, "scoreAfter": session["score"]})
        write_store(store)

        return {
            "message": message,
            "spin": {"segment": segment, "segmentIndex": segment_index},
            "session": sanitize_session(session),
        }


@app.post("/api/session/{session_id}/guess")
def guess(session_id: str, body: dict[str, Any] = Body(default={})):
    with store_lock:
        store = read_store()
        session, error = get_session_or_response(store, session_id)
        if error:
            return error

        if session["status"] != "active":
            return error_response(409, "Session is not active", session)

        letter = normalize_letter(body.get("letter"))
        guess_type = str(body.get("type") or "consonant").lower()
        is_vowel = letter in VOWELS

        if guess_type not in {"consonant", "vowel"}:
            return error_response(400, "Guess type must be 'consonant' or 'vowel'")

        if not is_letter(letter):
            return error_response(400, "Enter a valid single letter (A-Z)")

        if letter in session["usedLetters"]:
            return error_response(409, "Letter already used", session)

        if guess_type == "consonant":
            if is_vowel:
                return error_response(400, "Consonant guess cannot be a vowel")
            if session["pendingConsonantValue"] is None:
                return error_response(409, "Spin the wheel before guessing a consonant", session)

        if guess_type == "vowel":
            if not is_vowel:
                return error_response(400, "Vowel action accepts A, E, I, O, U only")
            if session["pendingConsonantValue"] is not None:
                return error_response(409, "Complete your consonant guess from the current spin first", session)
            if session["score"] < store["config"]["vowelCost"]:
                return error_response(
                    409, f"Need at least {format_coin(store['config']['vowelCost'])} to buy a vowel", session
                )
            session["score"] -= store["config"]["vowelCost"]

        found_count = sum(1 for char in session["puzzle"]["phrase"] if char == letter)

        session["usedLetters"].append(letter)
        if found_count > 0:
            session["guessedLetters"].append(letter)
        else:
            session["wrongGuesses"] += 1

        if guess_type == "consonant" and found_count > 0:
            session["score"] += session["pendingConsonantValue"] * found_count

        session["maskedPhrase"] = mask_phrase(session["puzzle"]["phrase"], session["guessedLetters"])
        session["pendingConsonantValue"] = None
        session["updatedAt"] = utc_now_iso()

        if found_count > 0:
            message = f"{letter} appears {found_count} time{'s' if found_count != 1 else ''}."
        else:
            message = f"No {letter} in the puzzle."

        if is_solved(session["maskedPhrase"]):
            session["status"] = "won"
            session["score"] += store["config"]["autoRevealBonus"]
            message = f"Puzzle solved by revealing letters. Bonus +{format_coin(store['config']['autoRevealBonus'])}."
            add_action(session, "auto_solve", {"scoreAfter": session["score"]})

        add_action(
            session,
            "guess",
            {"type": guess_type, "letter": letter, "foundCount": found_count, "scoreAfter": session["score"]},
        )

        update_leaderboard(store, session)
        write_store(store)

        return {
            "message": message,
            "result": {"letter": letter, "foundCount": found_count, "type": guess_type},
            "session": sanitize_session(session),
        }


@app.post("/api/session/{session_id}/solve")
def solve(session_id: str, body: dict[str, Any] = Body(default={})):
    with store_lock:
        store = read_store()
        session, error = get_session_or_response(store, session_id)
        if error:
            return error

        if session["status"] != "active":
            return error_response(409, "Session is not active", session)

        attempt = str(body.get("attempt") or "").strip()
        if len(attempt) < 2:
            return error_response(400, "Enter a full phrase to solve")

        session["pendingConsonantValue"] = None
        normalized_attempt = normalize_phrase(attempt)
        normalized_answer = normalize_phrase(session["puzzle"]["phrase"])

        if normalized_attempt == normalized_answer:
            session["status"] = "won"
            session["maskedPhrase"] = session["puzzle"]["phrase"]
            session["score"] += store["config"]["solveBonus"]
            session["updatedAt"] = utc_now_iso()

            add_action(
                session,
                "solve",
                {
                    "correct": True,
                    "attempt": attempt,
                    "bonus": store["config"]["solveBonus"],
                    "scoreAfter": session["score"],
                },
            )

            update_leaderboard(store, session)
            write_store(store)
            return {
                "message": f"Correct! Puzzle solved. Bonus +{format_coin(store['config']['solveBonus'])}.",
                "session": sanitize_session(session),
            }

        penalty = store["config"]["penalties"]["failedSolve"]
        session["score"] = max(0, session["score"] - penalty)
        session["wrongGuesses"] += 1
        session["updatedAt"] = utc_now_iso()

        add_action(
            session,
            "solve",
            {"correct": False, "attempt": attempt, "penalty": penalty, "scoreAfter": session["score"]},
        )

        write_store(store)
        return {
            "message": f"Incorrect solve. Penalty -{format_coin(penalty)}.",
            "session": sanitize_session(session),
        }


@app.post("/api/session/{session_id}/replay", status_code=201)
def replay(session_id: str, body: dict[str, Any] = Body(default={})):
    with store_lock:
        store = read_store()
        existing, error = get_session_or_response(store, session_id)
        if error:
            return error

        replay_session = create_session(
            store,
            {
                "playerName": body.get("playerName") or existing["playerName"],
                "difficulty": body.get("difficulty") or existing["puzzle"]["difficulty"],
            },
            existing["id"],
        )
        add_action(replay_session, "replay_started", {"previousSessionId": existing["id"]})
        write_store(store)

    return {"message": "Replay session created", "session": sanitize_session(replay_session)}


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
