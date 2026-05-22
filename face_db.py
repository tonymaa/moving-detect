import os
import sqlite3
import numpy as np
from datetime import datetime

DB_PATH = 'faces.db'
FACES_DIR = './faces'

os.makedirs(FACES_DIR, exist_ok=True)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            created_at TEXT NOT NULL,
            photo_path TEXT
        );
        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            encoding BLOB NOT NULL,
            detected_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS video_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_filename TEXT NOT NULL,
            person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            detected_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def match_face(encoding: np.ndarray, tolerance: float = 0.5) -> int | None:
    conn = _conn()
    rows = conn.execute("SELECT person_id, encoding FROM face_encodings").fetchall()
    conn.close()
    encoding = encoding.astype(np.float32)
    for row in rows:
        known = np.frombuffer(row['encoding'], dtype=np.float32)
        sim = np.dot(known, encoding) / (np.linalg.norm(known) * np.linalg.norm(encoding) + 1e-5)
        if sim >= tolerance:
            return row['person_id']
    return None


def add_unknown_face(encoding: np.ndarray, crop_image_bytes: bytes) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conn()
    cursor = conn.execute(
        "INSERT INTO persons (name, created_at, photo_path) VALUES (NULL, ?, NULL)",
        (now,)
    )
    person_id = cursor.lastrowid
    photo_path = os.path.join(FACES_DIR, f"{person_id}.jpg")
    with open(photo_path, 'wb') as f:
        f.write(crop_image_bytes)
    conn.execute("UPDATE persons SET photo_path = ? WHERE id = ?", (photo_path, person_id))
    conn.execute(
        "INSERT INTO face_encodings (person_id, encoding, detected_at) VALUES (?, ?, ?)",
        (person_id, encoding.astype(np.float32).tobytes(), now)
    )
    conn.commit()
    conn.close()
    return person_id


def add_encoding(person_id: int, encoding: np.ndarray):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conn()
    conn.execute(
        "INSERT INTO face_encodings (person_id, encoding, detected_at) VALUES (?, ?, ?)",
        (person_id, encoding.astype(np.float32).tobytes(), now)
    )
    conn.commit()
    conn.close()


def add_video_face(video_filename: str, person_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _conn()
    existing = conn.execute(
        "SELECT id FROM video_faces WHERE video_filename = ? AND person_id = ?",
        (video_filename, person_id)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO video_faces (video_filename, person_id, detected_at) VALUES (?, ?, ?)",
            (video_filename, person_id, now)
        )
        conn.commit()
    conn.close()


def get_all_persons() -> list[dict]:
    conn = _conn()
    rows = conn.execute("""
        SELECT p.id, p.name, p.photo_path, p.created_at,
               COUNT(DISTINCT vf.id) as video_count,
               COUNT(DISTINCT fe.id) as encoding_count
        FROM persons p
        LEFT JOIN video_faces vf ON vf.person_id = p.id
        LEFT JOIN face_encodings fe ON fe.person_id = p.id
        GROUP BY p.id
        ORDER BY p.name IS NULL, p.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_person(person_id: int) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_person_name(person_id: int, name: str):
    conn = _conn()
    conn.execute("UPDATE persons SET name = ? WHERE id = ?", (name, person_id))
    conn.commit()
    conn.close()


def get_videos_with_faces() -> dict[str, list[dict]]:
    conn = _conn()
    rows = conn.execute("""
        SELECT vf.video_filename, p.id as person_id, p.name, p.photo_path
        FROM video_faces vf
        JOIN persons p ON p.id = vf.person_id
        ORDER BY vf.video_filename
    """).fetchall()
    conn.close()
    result: dict[str, list[dict]] = {}
    for r in rows:
        filename = r['video_filename']
        if filename not in result:
            result[filename] = []
        result[filename].append({
            'id': r['person_id'],
            'name': r['name'],
            'photo_url': f"/api/persons/{r['person_id']}/photo"
        })
    return result


def delete_person(person_id: int):
    conn = _conn()
    person = conn.execute("SELECT photo_path FROM persons WHERE id = ?", (person_id,)).fetchone()
    if person and person['photo_path'] and os.path.exists(person['photo_path']):
        os.remove(person['photo_path'])
    conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()


init_db()
