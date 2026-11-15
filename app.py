import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from trailguide.agents import orchestrate
from trailguide.catalog import LINES, seed_products

ROOT = Path(__file__).resolve().parent
DB = ROOT / "trailguide.sqlite3"
app = FastAPI(title="Trailguide")
templates = Jinja2Templates(directory=ROOT / "templates")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


with closing(connect()) as db, db:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, category TEXT NOT NULL,
            stock INTEGER NOT NULL, details TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS product_search ON products(category, stock);
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT 'New session',
            state TEXT NOT NULL DEFAULT '{}', pending TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS turns (
            session_id TEXT NOT NULL REFERENCES sessions(id),
            number INTEGER NOT NULL, message TEXT NOT NULL, result TEXT NOT NULL,
            PRIMARY KEY(session_id, number)
        );
    """)
    db.executemany("INSERT INTO products VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET category = excluded.category, stock = excluded.stock, details = excluded.details", (
        (item["id"], item["category"], item["stock"], json.dumps(item))
        for item in seed_products()
    ))


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    focus: int | None = None
    source: Literal["text", "voice"] = "text"


def get_session(db, session_id):
    session = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise HTTPException(404, "Session not found")
    return session


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/catalog/categories")
def categories():
    return list(LINES)


@app.get("/api/catalog/download")
def download_catalog():
    with closing(connect()) as db:
        products = [json.loads(row[0]) for row in db.execute("SELECT details FROM products ORDER BY id")]
    return JSONResponse(
        {"currency": "INR", "synthetic": True, "listing_count": len(products), "products": products},
        headers={"Content-Disposition": 'attachment; filename="trailguide-catalog.json"'},
    )


@app.get("/api/sessions")
def sessions():
    with closing(connect()) as db:
        return [dict(row) for row in db.execute(
            "SELECT id, title FROM sessions ORDER BY updated_at DESC, rowid DESC"
        )]


@app.post("/api/sessions", status_code=201)
def new_session():
    session_id = uuid4().hex
    with closing(connect()) as db, db:
        db.execute("INSERT INTO sessions(id) VALUES (?)", (session_id,))
    return {"id": session_id}


@app.get("/api/sessions/{session_id}")
def history(session_id: str):
    with closing(connect()) as db:
        get_session(db, session_id)
        return [
            {"message": row["message"], **json.loads(row["result"])}
            for row in db.execute("SELECT message, result FROM turns WHERE session_id = ? ORDER BY number", (session_id,))
        ]


@app.post("/api/sessions/{session_id}/turns")
def chat(session_id: str, message: Message):
    query = message.text.strip()
    if not query:
        raise HTTPException(422, "Enter a shopping request")
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        session = get_session(db, session_id)
        turn = db.execute("SELECT coalesce(max(number), 0) + 1 FROM turns WHERE session_id = ?", (session_id,)).fetchone()[0]
        previous = json.loads(session["state"])
        recent = []
        focused = None
        rows = db.execute("SELECT result FROM turns WHERE session_id = ? ORDER BY number DESC", (session_id,))
        for row in rows:
            saved = json.loads(row["result"])
            products = saved.get("products", [])
            if not recent and products and saved.get("state") == previous:
                recent = products
            if message.focus and focused is None:
                focused = next((item for item in products if item["id"] == message.focus), None)
            if recent and (message.focus is None or focused):
                break
        if focused and all(item["id"] != focused["id"] for item in recent):
            recent = [focused]
        hydrated = []
        for snapshot in recent:
            catalog = db.execute("SELECT details FROM products WHERE id = ?", (snapshot["id"],)).fetchone()
            if catalog:
                hydrated.append(snapshot | json.loads(catalog[0]))
        result = orchestrate(db, query, previous, session["pending"], turn, session_id, hydrated, message.focus, message.source)
        db.execute("INSERT INTO turns VALUES (?, ?, ?, ?)", (session_id, turn, query, json.dumps(result)))
        db.execute("UPDATE sessions SET state = ?, pending = ?, title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (json.dumps(result["state"]), result["pending"], query[:46] if turn == 1 else session["title"], session_id))
    return {"message": query, **result}
