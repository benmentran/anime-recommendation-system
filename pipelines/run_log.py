"""Lightweight run tracking (replaces MLflow): file-based, no server, no network.

Usage:
    from pipelines.run_log import start_run
    with start_run("cf_matrix", params, data_source="real") as ctx:
        ctx.log_metrics({...})
        ctx.save_table("split", df)   # parquet, deterministically sorted
        ctx.save_json("id_maps", {...})
    # -> artifacts/cf_matrix/<UTC>_<sha>/manifest.json (+ tables, jsons)

`artifacts/` is gitignored except `artifacts/**/manifest.json` (small, committed).
Stdlib + pandas/pyarrow only.
"""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "artifacts"


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=REPO, timeout=10, check=False)
        return out.stdout.strip() or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def _versions() -> dict[str, str]:
    import numpy
    import pandas

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
    }


def sha256_file(path: "os.PathLike[str] | str") -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class RunContext:
    """One tracked run. Use as context manager; manifest written on exit."""

    def __init__(self, name: str, params: dict[str, Any],
                 data_source: str = "real", seed: int | None = None):
        if data_source not in ("real", "simulated"):
            raise ValueError("data_source must be 'real' or 'simulated'")
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.dir = ARTIFACTS / name / f"{ts}_{_git_sha()}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.params = dict(params)
        self.metrics: dict[str, Any] = {}
        self.files: dict[str, str] = {}
        self.data_source = data_source
        self.seed = seed if seed is not None else params.get("seed")
        self.dataset_digest: str | None = None

    def set_dataset_file(self, path: "os.PathLike[str] | str") -> str:
        """Hash an immutable snapshot file; digest goes into the manifest."""
        digest = sha256_file(path)
        self.dataset_digest = digest
        self.files[Path(path).name] = digest
        return digest

    def log_params(self, params: dict[str, Any]) -> None:
        self.params.update(params)

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        for k, v in metrics.items():
            if isinstance(v, float):
                v = round(v, 6)
            self.metrics[k] = v

    def save_table(self, name: str, df) -> Path:
        """Save DataFrame as parquet (sorted by all columns for digest stability)."""
        import pandas as pd

        if not isinstance(df, pd.DataFrame):
            raise TypeError("save_table needs a pandas DataFrame")
        out = self.dir / f"{name}.parquet"
        ordered = df.sort_values(by=list(df.columns)).reset_index(drop=True)
        ordered.to_parquet(out, index=False)
        self.files[out.name] = sha256_file(out)
        return out

    def save_json(self, name: str, obj: Any) -> Path:
        out = self.dir / f"{name}.json"
        out.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        self.files[out.name] = sha256_file(out)
        return out

    def manifest(self) -> dict[str, Any]:
        ended = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "run": self.name,
            "data_source": self.data_source,
            "seed": self.seed,
            "git_sha": _git_sha(),
            "versions": _versions(),
            "params": self.params,
            "metrics": self.metrics,
            "dataset_digest": self.dataset_digest,
            "files": self.files,
            "start_time": self.started,
            "end_time": ended,
        }

    def close(self) -> Path:
        out = self.dir / "manifest.json"
        out.write_text(json.dumps(self.manifest(), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        return out

    def __enter__(self) -> "RunContext":  # noqa: PYI034 - runtime returns self
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def start_run(name: str, params: dict[str, Any] | None = None,
              data_source: str = "real",
              seed: int | None = None) -> RunContext:
    """Create a run dir and return its context (use as `with` block)."""
    return RunContext(name, params or {}, data_source=data_source, seed=seed)


def temp_snapshot_path(suffix: str = ".parquet") -> str:
    """Scratch path outside the repo for building a snapshot before handing it to a run."""
    fd, path = tempfile.mkstemp(prefix="snapshot_", suffix=suffix)
    os.close(fd)
    return path
