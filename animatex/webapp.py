from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import AppConfig
from .db import JobStore
from .media import duration_seconds, sha256_file
from .modes import POSE_RETARGET, MODES, mode_label
from .planning import first_frame_label, processing_label
from .profiles import profile_names
from .runner import run_due_batch


def serve(config: AppConfig, store: JobStore, host: str, port: int) -> None:
    config.ensure_dirs()
    store.init()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._html(self._page())
            elif parsed.path == "/api/jobs":
                self._json([dict(row) for row in store.list_jobs()])
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = {key: values[0] for key, values in parse_qs(body).items()}

            if parsed.path == "/api/jobs":
                try:
                    video = Path(data["video"]).expanduser().resolve()
                    reference = Path(data["reference"]).expanduser().resolve()
                    job_id = store.add_job(
                        character=data.get("character", "Ari").strip() or "Ari",
                        mode=data.get("mode", POSE_RETARGET),
                        source_path=video,
                        reference_path=reference,
                        source_hash=sha256_file(video),
                        reference_hash=sha256_file(reference),
                        profile=data.get("profile", "TikTok Standard"),
                        schedule=data.get("schedule", "Tonight"),
                        duration_seconds=duration_seconds(video),
                    )
                    self._redirect(f"/?added={job_id}")
                except Exception as exc:
                    self._html(self._page(error=str(exc)), status=400)
            elif parsed.path == "/api/run":
                thread = threading.Thread(target=run_due_batch, args=(config, store), daemon=True)
                thread.start()
                self._redirect("/?running=1")
            else:
                self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _page(self, error: str | None = None) -> str:
            rows = store.list_jobs()
            counts = store.dashboard_counts()
            queued = counts.get("QUEUED", 0) + counts.get("FAILED", 0)
            completed = counts.get("COMPLETED", 0)
            failed = counts.get("FAILED", 0)
            processing = sum(
                counts.get(s, 0)
                for s in ("UPLOADING", "READY", "FIRST FRAME", "GENERATING", "UPSCALING", "ENCODING", "UPLOADING TO DRIVE")
            )
            options = "\n".join(f'<option value="{html.escape(p)}">{html.escape(p)}</option>' for p in profile_names())
            mode_options = "\n".join(
                f'<option value="{html.escape(mode.key)}">{html.escape(mode.label)}</option>'
                for mode in MODES.values()
            )
            job_rows = "\n".join(
                f"""
                <tr>
                  <td>{html.escape(row['character'])}</td>
                  <td>{html.escape(mode_label(row['mode']))}</td>
                  <td>{html.escape(Path(row['source_path']).name)}</td>
                  <td>{html.escape(row['profile'])}</td>
                  <td>{row['duration_seconds']:.1f}s</td>
                  <td>{html.escape(processing_label(row['processing_mode']))} x{row['window_count']}</td>
                  <td>{html.escape(first_frame_label(row['first_frame_strategy']))}</td>
                  <td><span class="state">{html.escape(row['status'])}</span></td>
                  <td>{html.escape(str(row['drive_path'] or ''))}</td>
                </tr>
                """
                for row in rows
            )
            err = f'<div class="error">{html.escape(error)}</div>' if error else ""
            return f"""
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>Animate-X</title>
              <style>
                body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #f6f7f9; color: #17202a; }}
                header {{ background: #111827; color: white; padding: 18px 28px; }}
                main {{ max-width: 1160px; margin: 0 auto; padding: 24px; }}
                .grid {{ display: grid; grid-template-columns: 360px 1fr; gap: 24px; align-items: start; }}
                section {{ background: white; border: 1px solid #d8dee8; border-radius: 8px; padding: 18px; }}
                label {{ display: block; font-size: 13px; font-weight: 600; margin-top: 12px; }}
                input, select {{ box-sizing: border-box; width: 100%; padding: 9px; border: 1px solid #b8c1cc; border-radius: 6px; margin-top: 5px; }}
                button {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 10px 14px; margin-top: 16px; cursor: pointer; }}
                button.secondary {{ background: #374151; }}
                .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }}
                .stat {{ background: #eef2ff; border-radius: 8px; padding: 12px; }}
                .stat strong {{ display: block; font-size: 24px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
                th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
                .state {{ font-size: 12px; font-weight: 700; background: #e8f0fe; padding: 4px 8px; border-radius: 999px; white-space: nowrap; }}
                .error {{ background: #fee2e2; color: #991b1b; border-radius: 6px; padding: 10px; margin-bottom: 12px; }}
                @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
              </style>
            </head>
            <body>
              <header><h1>WAN DAILY</h1></header>
              <main>
                {err}
                <div class="stats">
                  <div class="stat"><span>Queued</span><strong>{queued}</strong></div>
                  <div class="stat"><span>Processing</span><strong>{processing}</strong></div>
                  <div class="stat"><span>Completed</span><strong>{completed}</strong></div>
                  <div class="stat"><span>Failed</span><strong>{failed}</strong></div>
                </div>
                <div class="grid">
                  <section>
                    <h2>New Job</h2>
                    <form method="post" action="/api/jobs">
                      <label>Video path<input name="video" placeholder="C:\\path\\dance_01.mp4" required></label>
                      <label>Reference image path<input name="reference" placeholder="C:\\path\\ari_reference.png" required></label>
                      <label>Character<input name="character" value="Ari" required></label>
                      <label>Job type<select name="mode">{mode_options}</select></label>
                      <label>Profile<select name="profile">{options}</select></label>
                      <label>Schedule<input name="schedule" value="Tonight"></label>
                      <button type="submit">Add To Queue</button>
                    </form>
                    <form method="post" action="/api/run">
                      <button class="secondary" type="submit">Run Batch Now</button>
                    </form>
                  </section>
                  <section>
                    <h2>Today's Queue</h2>
                    <table>
                      <thead><tr><th>Character</th><th>Job Type</th><th>Video</th><th>Profile</th><th>Duration</th><th>Plan</th><th>First Frame</th><th>Status</th><th>Drive Path</th></tr></thead>
                      <tbody>{job_rows}</tbody>
                    </table>
                  </section>
                </div>
              </main>
            </body>
            </html>
            """

        def _html(self, body: str, status: int = 200) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _json(self, data: object) -> None:
            encoded = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _redirect(self, target: str) -> None:
            self.send_response(303)
            self.send_header("Location", target)
            self.end_headers()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Animate-X control panel: http://{host}:{port}")
    server.serve_forever()
