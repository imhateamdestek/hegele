import sqlite3
from datetime import datetime
from typing import Optional, List, Dict


class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self._create_tables()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT DEFAULT '',
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    gender TEXT NOT NULL,
                    looking_for TEXT NOT NULL,
                    city TEXT NOT NULL,
                    bio TEXT NOT NULL,
                    photo_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    is_banned INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user INTEGER NOT NULL,
                    to_user INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_user, to_user)
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user1 INTEGER NOT NULL,
                    user2 INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user INTEGER NOT NULL,
                    reported_user INTEGER NOT NULL,
                    reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    # ─── KULLANICI İŞLEMLERİ ───

    def create_user(self, telegram_id, username, name, age, gender,
                    looking_for, city, bio, photo_id=None):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO users
                (telegram_id, username, name, age, gender, looking_for, city, bio, photo_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (telegram_id, username, name, age, gender, looking_for, city, bio, photo_id))

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ? AND is_banned = 0",
                (telegram_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_user(self, telegram_id: int, **kwargs):
        """Dinamik güncelleme: update_user(id, bio='yeni bio', photo_id='xxx')"""
        if not kwargs:
            return
        cols = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [telegram_id]
        with self._conn() as conn:
            conn.execute(f"UPDATE users SET {cols} WHERE telegram_id = ?", vals)

    def delete_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            conn.execute("DELETE FROM likes WHERE from_user = ? OR to_user = ?",
                         (telegram_id, telegram_id))

    def ban_user(self, telegram_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,))

    # ─── KEŞFET / EŞLEŞTİRME ───

    def get_candidates(self, user_id: int, looking_for: str, city: str) -> List[Dict]:
        """
        Kullanıcının daha önce beğenmediği / görüp geçmediği,
        aynı şehirden, aradığı cinsiyetteki kişileri döndürür.
        """
        with self._conn() as conn:
            # Daha önce beğenilen/atlanan kişiler
            seen = conn.execute(
                "SELECT to_user FROM likes WHERE from_user = ?", (user_id,)
            ).fetchall()
            seen_ids = [r[0] for r in seen] + [user_id]
            placeholders = ",".join("?" * len(seen_ids))

            gender_filter = "" if looking_for == "Herkes" else "AND gender = ?"
            params = seen_ids[:]
            if looking_for != "Herkes":
                params.append(looking_for)
            params.append(city)

            rows = conn.execute(f"""
                SELECT * FROM users
                WHERE telegram_id NOT IN ({placeholders})
                AND is_active = 1 AND is_banned = 0
                {gender_filter}
                AND city = ?
                ORDER BY RANDOM()
                LIMIT 20
            """, params).fetchall()

            # Şehirde kimse kalmadıysa tüm Türkiye'ye genişlet
            if not rows:
                rows = conn.execute(f"""
                    SELECT * FROM users
                    WHERE telegram_id NOT IN ({placeholders})
                    AND is_active = 1 AND is_banned = 0
                    {gender_filter}
                    ORDER BY RANDOM()
                    LIMIT 20
                """, seen_ids + ([looking_for] if looking_for != "Herkes" else [])).fetchall()

            return [dict(r) for r in rows]

    def add_like(self, from_user: int, to_user: int) -> bool:
        """Beğeni ekler. Karşılıklıysa True döner (eşleşme!)"""
        with self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO likes (from_user, to_user) VALUES (?, ?)",
                    (from_user, to_user)
                )
            except sqlite3.IntegrityError:
                pass  # Zaten beğenmiş

            # Karşı taraf da beğenmiş mi?
            mutual = conn.execute(
                "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?",
                (to_user, from_user)
            ).fetchone()

            if mutual:
                # Eşleşme kaydet (tekrar kaydetme)
                existing = conn.execute(
                    "SELECT 1 FROM matches WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
                    (from_user, to_user, to_user, from_user)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO matches (user1, user2) VALUES (?, ?)",
                        (from_user, to_user)
                    )
                return True
            return False

    def get_matches(self, user_id: int) -> List[Dict]:
        """Kullanıcının tüm eşleşmelerini döndürür."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT u.* FROM matches m
                JOIN users u ON (
                    CASE WHEN m.user1 = ? THEN m.user2 ELSE m.user1 END = u.telegram_id
                )
                WHERE (m.user1 = ? OR m.user2 = ?)
                AND u.is_banned = 0
                ORDER BY m.created_at DESC
            """, (user_id, user_id, user_id)).fetchall()
            return [dict(r) for r in rows]

    # ─── RAPORLAMA ───

    def report_user(self, from_user: int, reported_user: int, reason: str = ""):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO reports (from_user, reported_user, reason) VALUES (?, ?, ?)",
                (from_user, reported_user, reason)
            )

    def get_reports(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT r.*, u.name as reported_name
                FROM reports r
                JOIN users u ON u.telegram_id = r.reported_user
                ORDER BY r.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    # ─── İSTATİSTİKLER ───

    def get_stats(self) -> Dict:
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=0").fetchone()[0]
            likes = conn.execute("SELECT COUNT(*) FROM likes").fetchone()[0]
            matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            return {"users": users, "likes": likes, "matches": matches}

    def get_all_users(self) -> List[int]:
        """Admin broadcast için tüm aktif kullanıcıların telegram_id'leri"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT telegram_id FROM users WHERE is_active=1 AND is_banned=0"
            ).fetchall()
            return [r[0] for r in rows]
