from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .modes import POSE_RETARGET
from .planning import plan_generation
from . import states


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    character TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'pose_retarget',
                    source_path TEXT NOT NULL,
                    reference_path TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    reference_hash TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    processing_mode TEXT NOT NULL DEFAULT 'single_window',
                    target_fps INTEGER NOT NULL DEFAULT 30,
                    estimated_frames INTEGER NOT NULL DEFAULT 1,
                    window_count INTEGER NOT NULL DEFAULT 1,
                    overlap_frames INTEGER NOT NULL DEFAULT 1,
                    first_frame_strategy TEXT NOT NULL DEFAULT 'direct_reference',
                    batch_id TEXT,
                    output_path TEXT,
                    drive_path TEXT,
                    error TEXT,
                    gpu_seconds REAL NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    manifest_path TEXT,
                    r2_manifest_uri TEXT,
                    runpod_job_id TEXT,
                    remote_status TEXT,
                    gpu_seconds REAL NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
                """
            )
            self._ensure_column(conn, "jobs", "mode", f"TEXT NOT NULL DEFAULT '{POSE_RETARGET}'")
            self._ensure_column(conn, "jobs", "processing_mode", "TEXT NOT NULL DEFAULT 'single_window'")
            self._ensure_column(conn, "jobs", "target_fps", "INTEGER NOT NULL DEFAULT 30")
            self._ensure_column(conn, "jobs", "estimated_frames", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "jobs", "window_count", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "jobs", "overlap_frames", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "jobs", "first_frame_strategy", "TEXT NOT NULL DEFAULT 'direct_reference'")
            self._ensure_column(conn, "batches", "r2_manifest_uri", "TEXT")
            self._ensure_column(conn, "batches", "runpod_job_id", "TEXT")
            self._ensure_column(conn, "batches", "remote_status", "TEXT")

    def add_job(
        self,
        *,
        character: str,
        mode: str,
        source_path: Path,
        reference_path: Path,
        source_hash: str,
        reference_hash: str,
        profile: str,
        schedule: str,
        duration_seconds: float,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = utc_now()
        plan = plan_generation(duration_seconds, mode)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, created_at, updated_at, character, mode, source_path, reference_path,
                    source_hash, reference_hash, profile, schedule, status, duration_seconds,
                    processing_mode, target_fps, estimated_frames, window_count, overlap_frames,
                    first_frame_strategy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    now,
                    now,
                    character,
                    mode,
                    str(source_path),
                    str(reference_path),
                    source_hash,
                    reference_hash,
                    profile,
                    schedule,
                    states.QUEUED,
                    duration_seconds,
                    plan.processing_mode,
                    plan.target_fps,
                    plan.estimated_frames,
                    plan.window_count,
                    plan.overlap_frames,
                    plan.first_frame_strategy,
                ),
            )
            self._event(conn, job_id, states.QUEUED, "Job queued", None)
        return job_id

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_batch(self, job_ids: list[str], manifest_path: Path) -> str:
        batch_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO batches (id, created_at, status, manifest_path) VALUES (?, ?, ?, ?)",
                (batch_id, now, "CREATED", str(manifest_path)),
            )
            conn.executemany(
                "UPDATE jobs SET batch_id = ?, updated_at = ? WHERE id = ?",
                [(batch_id, now, job_id) for job_id in job_ids],
            )
        return batch_id

    def mark_batch_started(self, batch_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE batches SET started_at = ?, status = ? WHERE id = ?",
                (utc_now(), "RUNNING", batch_id),
            )

    def mark_batch_done(self, batch_id: str, gpu_seconds: float, estimated_cost: float) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batches
                SET completed_at = ?, status = ?, gpu_seconds = ?, estimated_cost = ?
                WHERE id = ?
                """,
                (utc_now(), "COMPLETED", gpu_seconds, estimated_cost, batch_id),
            )

    def mark_batch_staged(self, batch_id: str, manifest_uri: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE batches SET r2_manifest_uri = ?, remote_status = ?, status = ? WHERE id = ?",
                (manifest_uri, "STAGED", "STAGED", batch_id),
            )

    def mark_batch_submitted(self, batch_id: str, runpod_job_id: str, remote_status: str = "SUBMITTED") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batches
                SET runpod_job_id = ?, remote_status = ?, status = ?
                WHERE id = ?
                """,
                (runpod_job_id, remote_status, "SUBMITTED", batch_id),
            )

    def mark_batch_remote_status(self, batch_id: str, remote_status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE batches SET remote_status = ? WHERE id = ?",
                (remote_status, batch_id),
            )

    def update_job(
        self,
        job_id: str,
        status: str,
        message: str,
        *,
        output_path: Path | None = None,
        drive_path: Path | None = None,
        error: str | None = None,
        gpu_seconds: float | None = None,
        estimated_cost: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        sets = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, utc_now()]
        if output_path is not None:
            sets.append("output_path = ?")
            values.append(str(output_path))
        if drive_path is not None:
            sets.append("drive_path = ?")
            values.append(str(drive_path))
        if error is not None:
            sets.append("error = ?")
            values.append(error)
        if gpu_seconds is not None:
            sets.append("gpu_seconds = ?")
            values.append(gpu_seconds)
        if estimated_cost is not None:
            sets.append("estimated_cost = ?")
            values.append(estimated_cost)
        values.append(job_id)

        with self.connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", values)
            self._event(conn, job_id, status, message, payload)

    def queued_jobs(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status IN (?, ?)
                    ORDER BY created_at, id
                    """,
                    (states.QUEUED, states.FAILED),
                )
            )

    def list_jobs(self, limit: int = 100) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT ?",
                    (limit,),
                )
            )

    def dashboard_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
        return {row["status"]: row["count"] for row in rows}

    def events_for_job(self, job_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute("SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)))

    def _event(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        status: str,
        message: str,
        payload: dict[str, Any] | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO job_events (job_id, ts, status, message, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, utc_now(), status, message, json.dumps(payload) if payload else None),
        )
