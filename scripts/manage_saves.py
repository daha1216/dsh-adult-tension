#!/usr/bin/env python3
"""Manage named v3 narrative save slots with atomic writes.

简化后的存档后端：玩家只面对「保存 <名称> / 载入 <名称> / 列出存档」三个
命令。本脚本提供命名槽位的初始化、列出、载入与原子保存；槽位目录内的
`.write.lock` 只用于保护存储提交（进程锁），不涉及回合号、事件 ID、
边界、同意或叙事主权。

冲突防护：载入时记录 manifest 的 `updated_at`，保存时携带
`--expected-updated-at`；槽位已被其他窗口写过后保存被拒绝，由上层用
自然语言给出「读取最新版本 / 另存为分支 / 取消」的提示。

已删除的历史能力（共享访问模式、租约、revision/hash CAS、分支）不再
提供；旧版 manifest 的多余字段会被忽略，不影响读取。
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


SLOT_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# 新 manifest 只保留这四个字段；旧版 manifest 的 revision/state_sha256/
# access_mode/lease 等历史字段在读取时被剥离，保存后不再写回。
MANIFEST_KEYS = ("manifest_version", "slot", "created_at", "updated_at")


class SaveError(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="microseconds")


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location(
        "adult_tension_common", Path(__file__).with_name("_common.py"))
    if spec is None or spec.loader is None:
        raise SaveError("cannot load _common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_COMMON = _load_common()


def slot_name(value: str) -> str:
    if not isinstance(value, str):
        raise SaveError("slot name must be a string")
    value = value.strip().replace(" ", "-")
    if not value:
        raise SaveError("slot name is empty")
    if SLOT_UNSAFE.search(value) or value in {".", ".."} or value.startswith("."):
        raise SaveError("slot name contains unsupported characters")
    if len(value) > 80:
        raise SaveError("slot name is too long (max 80)")
    return value


def yaml_text(data: Any) -> str:
    if yaml is None:
        raise SaveError("PyYAML is required; run: python -m pip install PyYAML")
    return _COMMON.yaml_text(data)


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise SaveError("PyYAML is required; run: python -m pip install PyYAML")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SaveError(f"cannot read YAML {path}: {exc}") from exc


def write_atomic(path: Path, text: str) -> None:
    _COMMON.write_atomic(path, text)


class FileLock:
    """Cross-platform advisory lock on one byte in a slot lock file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "FileLock":
        try:
            # w+b：文件内容无意义，截断到 0 字节即可（不再随每次加锁追加增长）。
            self.handle = self.path.open("w+b")
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
            raise SaveError(f"cannot acquire write lock {self.path}: {exc}") from exc
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


class SaveStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.slots = root / "slots"

    def slot_dir(self, slot: str) -> Path:
        return self.slots / slot_name(slot)

    def state_path(self, slot: str) -> Path:
        return self.slot_dir(slot) / "state.yaml"

    def manifest_path(self, slot: str) -> Path:
        return self.slot_dir(slot) / "manifest.yaml"

    def lock_path(self, slot: str) -> Path:
        return self.slot_dir(slot) / ".write.lock"

    def _read_manifest(self, slot: str) -> dict[str, Any]:
        path = self.manifest_path(slot)
        if not path.exists():
            raise SaveError(f"slot does not exist or has no manifest: {slot}")
        manifest = load_yaml(path)
        if not isinstance(manifest, dict):
            raise SaveError(f"manifest is not a mapping: {path}")
        return {key: manifest.get(key) for key in MANIFEST_KEYS}

    def _read_state(self, slot: str) -> dict[str, Any]:
        path = self.state_path(slot)
        if not path.exists():
            raise SaveError(f"slot has no state.yaml: {slot}")
        state = load_yaml(path)
        if not isinstance(state, dict):
            raise SaveError(f"state is not a mapping: {path}")
        return state

    def _validate_state(self, state: dict[str, Any]) -> None:
        validator_path = Path(__file__).with_name("validate_state.py")
        spec = importlib.util.spec_from_file_location("adult_tension_validate_state", validator_path)
        if spec is None or spec.loader is None:
            raise SaveError("cannot load validate_state.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        errors = module.validate_data(state, "save")
        if errors:
            raise SaveError("state validation failed: " + "; ".join(errors))

    @staticmethod
    def _new_manifest(slot: str) -> dict[str, Any]:
        now = iso_now()
        return {
            "manifest_version": 1,
            "slot": slot,
            "created_at": now,
            "updated_at": now,
        }

    def init_slot(self, slot: str, source: Path) -> dict[str, Any]:
        slot = slot_name(slot)
        try:
            self.state_path(slot).parent.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise SaveError(f"slot already exists: {slot}") from exc
        state = load_yaml(source)
        if not isinstance(state, dict):
            raise SaveError("source state must be a mapping")
        self._validate_state(state)
        write_atomic(self.state_path(slot), yaml_text(state))
        write_atomic(self.manifest_path(slot), yaml_text(self._new_manifest(slot)))
        return self._read_manifest(slot)

    def list_slots(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not self.slots.exists():
            return result
        for path in sorted(self.slots.iterdir()):
            if path.is_dir() and (path / "manifest.yaml").exists():
                try:
                    item = self._read_manifest(path.name)
                except SaveError:
                    continue
                try:
                    state = self._read_state(path.name)
                except SaveError:
                    state = {}
                meta = state.get("meta") if isinstance(state, dict) else {}
                node = state.get("current_node") if isinstance(state, dict) else {}
                if isinstance(meta, dict) and isinstance(meta.get("turn"), int):
                    item["turn"] = meta["turn"]
                if isinstance(node, dict) and isinstance(node.get("unresolved_action"), str):
                    item["summary"] = node["unresolved_action"].strip()[:80]
                result.append(item)
        return result

    def load_slot(self, slot: str) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = self._read_manifest(slot)
        state = self._read_state(slot)
        self._validate_state(state)
        meta = state.get("meta") if isinstance(state, dict) else {}
        if isinstance(meta, dict) and meta.get("turn") == 0:
            print("warning: 这是旧口径开局档（回合 0），按回合 1 接续，不重掷。", file=sys.stderr)
        return state, manifest

    def save_slot(
        self,
        slot: str,
        state_source: Path,
        *,
        expected_updated_at: str | None = None,
    ) -> dict[str, Any]:
        candidate = load_yaml(state_source)
        if not isinstance(candidate, dict):
            raise SaveError("candidate state must be a mapping")
        self._validate_state(candidate)
        # 槽不存在时先拒绝，避免为拼错的槽名留下只含 .write.lock 的垃圾目录。
        if not self.manifest_path(slot).exists():
            raise SaveError(f"slot does not exist or has no manifest: {slot} (init it first)")
        with FileLock(self.lock_path(slot)):
            manifest = self._read_manifest(slot)
            if expected_updated_at is None:
                raise SaveError(
                    "覆盖保存必须携带 --expected-updated-at（载入时记录的 manifest.updated_at）；"
                    "先用 load 查看最新值"
                )
            if manifest.get("updated_at") != expected_updated_at:
                raise SaveError(
                    "write conflict: slot was modified after load; reload the latest version "
                    "or save under a new name"
                )
            updated = dict(manifest)
            updated["updated_at"] = iso_now()
            # 先写 manifest 再写 state：两连写之间崩溃时会留下「manifest 新 / state 旧」
            # 的保守失配（下一次携带旧 expected 的保存会被冲突检测拦下），而不是
            # 「state 新 / manifest 旧」导致的静默覆盖。
            write_atomic(self.manifest_path(slot), yaml_text(updated))
            write_atomic(self.state_path(slot), yaml_text(candidate))
            return updated


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1] / "saves")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a slot from a v3 state")
    init.add_argument("slot")
    init.add_argument("source", type=Path)

    sub.add_parser("list", help="list slots")

    load = sub.add_parser("load", help="validate and print a slot manifest")
    load.add_argument("slot")

    save = sub.add_parser("save", help="atomically save a candidate v3 state")
    save.add_argument("slot")
    save.add_argument("state_source", type=Path)
    save.add_argument("--expected-updated-at", default=None,
                      help="manifest.updated_at observed at load; mismatch refuses the write")
    return parser


def main(argv: list[str] | None = None) -> int:
    if yaml is None:
        print("ERROR: PyYAML is required; run: python -m pip install PyYAML", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    store = SaveStore(args.root)
    try:
        if args.command == "init":
            print_json(store.init_slot(args.slot, args.source))
        elif args.command == "list":
            print_json(store.list_slots())
        elif args.command == "load":
            _, manifest = store.load_slot(args.slot)
            print_json(manifest)
        elif args.command == "save":
            print_json(store.save_slot(args.slot, args.state_source,
                                        expected_updated_at=args.expected_updated_at))
        return 0
    except SaveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass
    raise SystemExit(main())
