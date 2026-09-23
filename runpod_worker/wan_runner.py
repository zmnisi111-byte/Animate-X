from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from media import copy_or_transcode_video


POSE_RETARGET = "pose_retarget"
CHARACTER_SWAP = "character_swap"


@dataclass(frozen=True)
class WanJob:
    id: str
    source_path: Path
    reference_path: Path
    mode: str
    profile: str
    processing_mode: str
    window_count: int


class WanRunner:
    def run(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        if os.getenv("WAN_MOCK", "1") == "1":
            return self._run_mock(job, output_path)
        return self._run_real(job, output_path)

    def _run_mock(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        started = time.perf_counter()
        copy_or_transcode_video(job.source_path, output_path)
        return {
            "engine": "mock",
            "gpu_seconds": time.perf_counter() - started,
            "note": "Smoke-test worker copied/transcoded the source video.",
        }

    def _run_real(self, job: WanJob, output_path: Path) -> dict[str, float | str]:
        started = time.perf_counter()
        repo_dir = Path(os.getenv("WAN_REPO_DIR", "/opt/Wan2.2"))
        model_dir = Path(os.getenv("WAN_MODEL_DIR", "/workspace/models/Wan2.2-Animate-14B"))
        if not repo_dir.exists():
            raise RuntimeError(f"Wan repo not found: {repo_dir}")
        self._ensure_model(model_dir)

        work_dir = output_path.parent / "wan"
        preprocess_dir = work_dir / "process_results"
        preprocess_dir.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        resolution = os.getenv("WAN_RESOLUTION_AREA", "1280 720").split()
        if len(resolution) != 2:
            raise RuntimeError("WAN_RESOLUTION_AREA must look like '1280 720'")

        is_replacement = job.mode == CHARACTER_SWAP
        preprocess_cmd = [
            "python3",
            str(repo_dir / "wan/modules/animate/preprocess/preprocess_data.py"),
            "--ckpt_path",
            str(model_dir / "process_checkpoint"),
            "--video_path",
            str(job.source_path),
            "--refer_path",
            str(job.reference_path),
            "--save_path",
            str(preprocess_dir),
            "--resolution_area",
            resolution[0],
            resolution[1],
        ]
        if is_replacement:
            preprocess_cmd.extend(["--iterations", "3", "--k", "7", "--w_len", "1", "--h_len", "1", "--replace_flag"])
        else:
            preprocess_cmd.append("--retarget_flag")
            if os.getenv("WAN_USE_FLUX", "0") == "1":
                preprocess_cmd.append("--use_flux")
        self._run(preprocess_cmd, cwd=repo_dir, timeout=self._timeout("WAN_PREPROCESS_TIMEOUT_SECONDS", 1800))

        generate_cmd = [
            "python3",
            "generate.py",
            "--task",
            "animate-14B",
            "--ckpt_dir",
            str(model_dir),
            "--src_root_path",
            str(preprocess_dir),
            "--refert_num",
            os.getenv("WAN_REFERT_NUM", "1"),
            "--save_file",
            str(output_path),
            "--offload_model",
            os.getenv("WAN_OFFLOAD_MODEL", "True"),
            "--convert_model_dtype",
        ]
        sample_steps = os.getenv("WAN_SAMPLE_STEPS")
        if sample_steps:
            generate_cmd.extend(["--sample_steps", sample_steps])
        frame_num = os.getenv("WAN_FRAME_NUM")
        if frame_num:
            generate_cmd.extend(["--frame_num", frame_num])
        if is_replacement:
            generate_cmd.extend(["--replace_flag", "--use_relighting_lora"])
        self._run(generate_cmd, cwd=repo_dir, timeout=self._timeout("WAN_GENERATE_TIMEOUT_SECONDS", 7200))

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Wan did not produce output file: {output_path}")

        return {
            "engine": "wan2.2-animate",
            "gpu_seconds": time.perf_counter() - started,
            "wan_mode": "replacement" if is_replacement else "animation",
            "model_dir": str(model_dir),
        }

    def _ensure_model(self, model_dir: Path) -> None:
        if (model_dir / "process_checkpoint").exists():
            return
        if os.getenv("WAN_AUTO_DOWNLOAD", "1") != "1":
            raise RuntimeError(f"Wan model not found and WAN_AUTO_DOWNLOAD is disabled: {model_dir}")
        model_dir.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "huggingface-cli",
            "download",
            os.getenv("WAN_MODEL_ID", "Wan-AI/Wan2.2-Animate-14B"),
            "--local-dir",
            str(model_dir),
        ]
        self._run(cmd, cwd=model_dir.parent, timeout=self._timeout("WAN_MODEL_DOWNLOAD_TIMEOUT_SECONDS", 7200))

    def _run(self, cmd: list[str], *, cwd: Path, timeout: int) -> None:
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Command failed with exit code "
                f"{result.returncode}: {' '.join(cmd)}\nSTDOUT:\n{result.stdout[-4000:]}\nSTDERR:\n{result.stderr[-4000:]}"
            )

    def _timeout(self, env_name: str, default: int) -> int:
        return int(os.getenv(env_name, str(default)))
