#!/usr/bin/env python3
"""脚本共享小工具：隔壁脚本加载、yaml 读写、原子写文件。

各脚本在导入时按路径加载本模块（不依赖 sys.path）：

    def _load_common() -> Any:
        spec = importlib.util.spec_from_file_location(
            "adult_tension_common", Path(__file__).with_name("_common.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    _COMMON = _load_common()
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"


class CommonError(RuntimeError):
    """共享工具失败（缺 PyYAML、脚本加载失败、读写失败）。"""


class FileLock:
    """Cross-platform advisory lock backed by a one-byte lock file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.handle = self.path.open("a+b")
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
            else:  # pragma: no cover - exercised on POSIX CI
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
            raise CommonError(f"cannot acquire write lock {self.path}: {exc}") from exc
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - exercised on POSIX CI
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


def load_sibling(name: str) -> Any:
    """按文件名加载同目录脚本，如 load_sibling("roll_opening")。"""
    script = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"adult_tension_{name}", script)
    if spec is None or spec.loader is None:
        raise CommonError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_yaml_module() -> Any:
    if yaml is None:
        raise CommonError("PyYAML is required; run: python -m pip install PyYAML")
    return yaml


def load_yaml_bytes(snapshot: bytes, source: Any = "<bytes>") -> Any:
    """Parse one byte snapshot, rejecting duplicate keys at every depth."""
    if yaml is None:
        raise CommonError("PyYAML is required; run: python -m pip install PyYAML")

    class StrictLoader(yaml.SafeLoader):
        def construct_mapping(self, node: Any, deep: bool = False) -> Any:
            if not isinstance(node, yaml.MappingNode):
                return super().construct_mapping(node, deep=deep)
            self.flatten_mapping(node)
            seen = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    duplicate = key in seen
                    seen.add(key)
                except TypeError as exc:
                    raise yaml.constructor.ConstructorError(
                        None, None, "unhashable mapping key", key_node.start_mark) from exc
                if duplicate:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"duplicate key: {key!r}", key_node.start_mark)
            return super().construct_mapping(node, deep=deep)

    try:
        return yaml.load(snapshot.decode("utf-8"), Loader=StrictLoader)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise CommonError(f"cannot read YAML {source}: {exc}") from exc


def load_yaml_file(path: Path) -> Any:
    try:
        snapshot = path.read_bytes()
    except OSError as exc:
        raise CommonError(f"cannot read YAML {path}: {exc}") from exc
    return load_yaml_bytes(snapshot, path)


def load_data_yaml(name: str) -> Any:
    """读取 scripts/data/<name>——全部脚本的数据本体唯一加载入口。

    空文件或顶层非映射按 CommonError 报错；调用方负责翻译成自己的错误类型。
    """
    data = load_yaml_file(DATA_DIR / name)
    if not isinstance(data, dict) or not data:
        raise CommonError(f"data file is empty or not a mapping: {name}")
    return data


def yaml_text(data: Any) -> str:
    if yaml is None:
        raise CommonError("PyYAML is required; run: python -m pip install PyYAML")
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def write_atomic(path: Path, text: str) -> None:
    """同目录临时文件 + fsync + os.replace 的原子写入。"""
    write_atomic_bytes(path, text.encode("utf-8"))


def write_atomic_bytes(path: Path, snapshot: bytes) -> None:
    """Write exact bytes, including when restoring a prior state/manifest pair."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(snapshot)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def lock_path(path: Path) -> Path:
    """Return the sibling lock path used for read-modify-write operations."""
    return path.with_name(f".{path.name}.write.lock")


def session_state_path(root: Path, session: str) -> Path:
    """Resolve a portable, explicit session ID without permitting path traversal."""
    if (not isinstance(session, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", session)
            or session.upper() in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9]", session.upper())):
        raise CommonError("invalid session ID: use 1-80 letters, digits, underscores or hyphens")
    sessions = (root / "sessions").resolve()
    path = (sessions / session / "state.yaml").resolve()
    if path.parent.parent != sessions:
        raise CommonError("session path escapes sessions directory")
    return path


def state_binding(path: Path, snapshot: bytes, root: Path | None = None) -> dict[str, Any]:
    path = path.resolve()
    sessions = ((root or ROOT / "saves") / "sessions").resolve()
    session = path.parent.name if path.name == "state.yaml" and path.parent.parent == sessions else None
    return {"session": session, "state_path": str(path),
            "state_token": hashlib.sha256(snapshot).hexdigest()}
