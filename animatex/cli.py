from __future__ import annotations

import argparse
from pathlib import Path

from .cloud_manifest import build_worker_manifest, stage_batch_to_r2
from .config import AppConfig
from .db import JobStore
from .env import load_env_file
from .media import duration_seconds, sha256_file
from .modes import POSE_RETARGET, mode_label, mode_keys
from .planning import first_frame_label, processing_label
from .profiles import profile_names
from .runpod_client import RunPodServerlessClient, RunPodServerlessConfig
from .runner import run_due_batch
from .sample import create_sample_assets
from .webapp import serve


def json_dump(payload: object) -> str:
    import json

    return json.dumps(payload, indent=2, default=str)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="animatex")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")

    sample = sub.add_parser("sample")
    sample.add_argument("--out", default="samples")

    add = sub.add_parser("add")
    add.add_argument("--video", required=True)
    add.add_argument("--reference", required=True)
    add.add_argument("--character", required=True)
    add.add_argument("--mode", default=POSE_RETARGET, choices=mode_keys())
    add.add_argument("--profile", default="TikTok Standard", choices=profile_names())
    add.add_argument("--schedule", default="Tonight")

    sub.add_parser("queue")
    sub.add_parser("run")
    sub.add_parser("cloud-manifest")
    sub.add_parser("cloud-stage")

    submit = sub.add_parser("cloud-submit")
    submit.add_argument("--manifest-url")
    submit.add_argument("--batch-id")

    status = sub.add_parser("cloud-status")
    status.add_argument("job_id")

    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8765)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    load_env_file()
    config = AppConfig.from_root()
    config.ensure_dirs()
    store = JobStore(config.db_path)
    store.init()

    if args.command == "init":
        print(f"Initialized Animate-X at {config.root}")
        print(f"Database: {config.db_path}")
        return 0

    if args.command == "sample":
        video, reference = create_sample_assets(Path(args.out))
        print(f"Sample video: {video}")
        print(f"Reference image: {reference}")
        return 0

    if args.command == "add":
        video = Path(args.video).expanduser().resolve()
        reference = Path(args.reference).expanduser().resolve()
        if not video.exists():
            raise FileNotFoundError(video)
        if not reference.exists():
            raise FileNotFoundError(reference)
        job_id = store.add_job(
            character=args.character,
            mode=args.mode,
            source_path=video,
            reference_path=reference,
            source_hash=sha256_file(video),
            reference_hash=sha256_file(reference),
            profile=args.profile,
            schedule=args.schedule,
            duration_seconds=duration_seconds(video),
        )
        print(f"Queued job: {job_id}")
        return 0

    if args.command == "queue":
        rows = store.list_jobs()
        if not rows:
            print("No jobs.")
            return 0
        for row in rows:
            print(
                f"{row['id']} | {row['character']} | {Path(row['source_path']).name} | "
                f"{mode_label(row['mode'])} | {row['profile']} | {row['duration_seconds']:.1f}s | "
                f"{processing_label(row['processing_mode'])} x{row['window_count']} | "
                f"{first_frame_label(row['first_frame_strategy'])} | {row['status']} | {row['drive_path'] or ''}"
            )
        return 0

    if args.command == "run":
        result = run_due_batch(config, store)
        print(
            "Batch {batch_id} complete: {completed} completed, {failed} failed, "
            "{gpu_seconds:.2f}s mock GPU, ${estimated_cost:.4f}".format(**result)
        )
        return 0

    if args.command == "cloud-manifest":
        batch_id, manifest_path = build_worker_manifest(config, store)
        if not batch_id or not manifest_path:
            print("No queued jobs.")
            return 0
        print(f"Worker manifest: {manifest_path}")
        print("This manifest uses __R2_BUCKET__ placeholders until R2 upload wiring is enabled.")
        return 0

    if args.command == "cloud-stage":
        try:
            batch_id, manifest_uri, manifest_path = stage_batch_to_r2(config, store)
        except RuntimeError as exc:
            print(f"Cloud stage failed: {exc}")
            return 1
        if not batch_id or not manifest_uri or not manifest_path:
            print("No queued jobs.")
            return 0
        print(f"Batch ID: {batch_id}")
        print(f"Local manifest: {manifest_path}")
        print(f"R2 manifest: {manifest_uri}")
        return 0

    if args.command == "cloud-submit":
        batch_id = args.batch_id
        manifest_url = args.manifest_url
        if not manifest_url:
            try:
                batch_id, manifest_url, _ = stage_batch_to_r2(config, store)
            except RuntimeError as exc:
                print(f"Cloud submit failed: {exc}")
                return 1
        if not batch_id or not manifest_url:
            print("No queued jobs.")
            return 0
        try:
            client = RunPodServerlessClient(RunPodServerlessConfig.from_env())
            result = client.submit(batch_id=batch_id, manifest_url=manifest_url)
        except RuntimeError as exc:
            print(f"Cloud submit failed: {exc}")
            return 1
        job_id = result.get("id") or result.get("jobId") or result.get("job_id")
        if job_id:
            store.mark_batch_submitted(batch_id, str(job_id), str(result.get("status", "SUBMITTED")))
        print(json_dump(result))
        return 0

    if args.command == "cloud-status":
        try:
            client = RunPodServerlessClient(RunPodServerlessConfig.from_env())
            print(json_dump(client.status(args.job_id)))
        except RuntimeError as exc:
            print(f"Cloud status failed: {exc}")
            return 1
        return 0

    if args.command == "serve":
        serve(config, store, args.host, args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
