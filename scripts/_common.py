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

import importlib.util
import os
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


def load_yaml_file(path: Path) -> Any:
    if yaml is None:
        raise CommonError("PyYAML is required; run: python -m pip install PyYAML")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CommonError(f"cannot read YAML {path}: {exc}") from exc


def yaml_text(data: Any) -> str:
    if yaml is None:
        raise CommonError("PyYAML is required; run: python -m pip install PyYAML")
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def write_atomic(path: Path, text: str) -> None:
    """同目录临时文件 + fsync + os.replace 的原子写入。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
