"""Users: accounts, roles, login, lockout, and the audit trail for logins."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.database.db import get_connection
from app.utils.security import hash_password, verify_password

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@dataclass
class User:
    user_id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[str]

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class LoginResult:
    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_INACTIVE = "account_inactive"


def _row_to_user(row) -> User:
    return User(
        user_id=row["user_id"],
        username=row["username"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        last_login_at=row["last_login_at"],
    )


def any_users_exist() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return row["count"] > 0


def create_user(
    username: str, full_name: str, plain_password: str, role: str, actor: Optional[User] = None
) -> User:
    conn = get_connection()
    password_hash = hash_password(plain_password)
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO users (username, password_hash, full_name, role, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, ?)
        """,
        (username.strip(), password_hash, full_name.strip(), role, now),
    )
    conn.commit()
    if actor is not None:
        _log_audit(actor.user_id, actor.username, "user_created", f"Created user '{username.strip()}'")
    return get_user_by_id(cursor.lastrowid)


def get_user_by_id(user_id: int) -> Optional[User]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def _get_user_row_by_username(username: str):
    conn = get_connection()
    return conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()


def list_users() -> list[User]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return [_row_to_user(row) for row in rows]


def username_exists(username: str, exclude_user_id: Optional[int] = None) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id FROM users WHERE username = ? AND user_id != ?",
        (username.strip(), exclude_user_id or -1),
    ).fetchone()
    return row is not None


def count_active_admins(exclude_user_id: Optional[int] = None) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM users "
        "WHERE role = 'admin' AND is_active = 1 AND user_id != ?",
        (exclude_user_id or -1,),
    ).fetchone()
    return row["count"]


def update_user(user_id: int, username: str, full_name: str, role: str, actor: Optional[User] = None) -> User:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET username = ?, full_name = ?, role = ? WHERE user_id = ?",
        (username.strip(), full_name.strip(), role, user_id),
    )
    conn.commit()
    if actor is not None:
        _log_audit(actor.user_id, actor.username, "user_updated", f"Updated user '{username.strip()}'")
    return get_user_by_id(user_id)


def set_user_active(user_id: int, is_active: bool, actor: Optional[User] = None) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if is_active else 0, user_id))
    conn.commit()
    if actor is not None:
        action = "user_activated" if is_active else "user_deactivated"
        target = get_user_by_id(user_id)
        target_name = target.username if target else str(user_id)
        _log_audit(actor.user_id, actor.username, action, f"Target user '{target_name}'")


def delete_user(user_id: int, actor: Optional[User] = None) -> None:
    conn = get_connection()
    target = get_user_by_id(user_id)
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    if actor is not None:
        target_name = target.username if target else str(user_id)
        _log_audit(actor.user_id, actor.username, "user_deleted", f"Deleted user '{target_name}'")


def reset_password(user_id: int, new_plain_password: str, actor: Optional[User] = None) -> None:
    conn = get_connection()
    password_hash = hash_password(new_plain_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
        (password_hash, user_id),
    )
    conn.commit()
    if actor is not None:
        target = get_user_by_id(user_id)
        target_name = target.username if target else str(user_id)
        _log_audit(actor.user_id, actor.username, "password_reset", f"Target user '{target_name}'")


def attempt_login(username: str, plain_password: str):
    """Returns (LoginResult, User | None, remaining_lockout_time | None)."""
    conn = get_connection()
    row = _get_user_row_by_username(username)

    if row is None:
        _log_audit(None, username, "login_failed", "Unknown username")
        return LoginResult.INVALID_CREDENTIALS, None, None

    if row["locked_until"]:
        locked_until = datetime.fromisoformat(row["locked_until"])
        if datetime.utcnow() < locked_until:
            return LoginResult.ACCOUNT_LOCKED, None, locked_until - datetime.utcnow()
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
            (row["user_id"],),
        )
        conn.commit()

    if not row["is_active"]:
        _log_audit(row["user_id"], username, "login_failed", "Account inactive")
        return LoginResult.ACCOUNT_INACTIVE, None, None

    if not verify_password(plain_password, row["password_hash"]):
        new_failed = row["failed_attempts"] + 1
        locked_until_value = None
        if new_failed >= MAX_FAILED_ATTEMPTS:
            locked_until_value = (datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        conn.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE user_id = ?",
            (new_failed, locked_until_value, row["user_id"]),
        )
        conn.commit()
        _log_audit(row["user_id"], username, "login_failed", f"Attempt {new_failed}")
        if locked_until_value:
            return LoginResult.ACCOUNT_LOCKED, None, timedelta(minutes=LOCKOUT_MINUTES)
        return LoginResult.INVALID_CREDENTIALS, None, None

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE user_id = ?",
        (now, row["user_id"]),
    )
    conn.commit()
    _log_audit(row["user_id"], username, "login_success", None)
    return LoginResult.SUCCESS, get_user_by_id(row["user_id"]), None


def log_logout(user: User) -> None:
    _log_audit(user.user_id, user.username, "logout", None)


def _log_audit(user_id: Optional[int], username: str, action: str, details: Optional[str]) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, action, details, datetime.utcnow().isoformat()),
    )
    conn.commit()
