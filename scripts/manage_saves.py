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
import hashlib
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
# 新 manifest 只保留这五个字段；旧版 manifest 的 revision/
# access_mode/lease 等历史字段在读取时被剥离，保存后不再写回。
MANIFEST_KEYS = ("manifest_version", "slot", "created_at", "updated_at", "state_sha256")


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
        return _COMMON.load_yaml_file(path)
    except _COMMON.CommonError as exc:
        raise SaveError(f"cannot read YAML {path}: {exc}") from exc


def write_atomic(path: Path, text: str) -> None:
    _COMMON.write_atomic(path, text)


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

    def _read_manifest(self, slot: str, snapshot: bytes | None = None) -> dict[str, Any]:
        path = self.manifest_path(slot)
        if not path.exists():
            raise SaveError(f"slot does not exist or has no manifest: {slot}")
        try:
            manifest = load_yaml(path) if snapshot is None else _COMMON.load_yaml_bytes(snapshot, path)
        except _COMMON.CommonError as exc:
            raise SaveError(str(exc)) from exc
        if not isinstance(manifest, dict):
            raise SaveError(f"manifest is not a mapping: {path}")
        result = {key: manifest.get(key) for key in MANIFEST_KEYS}
        if result["manifest_version"] not in (1, 2):
            raise SaveError(f"unsupported manifest version: {result['manifest_version']}")
        if result["slot"] not in (None, slot):
            raise SaveError(f"manifest slot does not match directory: {slot}")
        for key in ("created_at", "updated_at"):
            value = result[key]
            if not isinstance(value, str) or not value.strip():
                raise SaveError(f"manifest field {key} is missing or invalid: {path}")
            try:
                dt.datetime.fromisoformat(value)
            except ValueError as exc:
                raise SaveError(f"manifest field {key} is not ISO datetime: {value}") from exc
        if result["manifest_version"] >= 2:
            digest = result["state_sha256"]
            if not isinstance(digest, str) or len(digest) != 64:
                raise SaveError(f"manifest state_sha256 is missing or invalid: {path}")
        return result

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
    def _state_sha256(text: str | bytes) -> str:
        return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()

    @classmethod
    def _new_manifest(cls, slot: str, state_text: str) -> dict[str, Any]:
        now = iso_now()
        return {
            "manifest_version": 2,
            "slot": slot,
            "created_at": now,
            "updated_at": now,
            "state_sha256": cls._state_sha256(state_text),
        }

    def init_slot(self, slot: str, source: Path) -> dict[str, Any]:
        slot = slot_name(slot)
        state = load_yaml(source)
        if not isinstance(state, dict):
            raise SaveError("source state must be a mapping")
        self._validate_state(state)
        state_text = yaml_text(state)
        try:
            self.state_path(slot).parent.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise SaveError(f"slot already exists: {slot}") from exc
        try:
            with _COMMON.FileLock(self.lock_path(slot)):
                try:
                    manifest = self._new_manifest(slot, state_text)
                    write_atomic(self.state_path(slot), state_text)
                    write_atomic(self.manifest_path(slot), yaml_text(manifest))
                except Exception:
                    self.manifest_path(slot).unlink(missing_ok=True)
                    self.state_path(slot).unlink(missing_ok=True)
                    raise
        except Exception as exc:
            self.lock_path(slot).unlink(missing_ok=True)
            self.slot_dir(slot).rmdir()
            raise SaveError(f"cannot initialize slot {slot}: {exc}") from exc
        return manifest

    def list_slots(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not self.slots.exists():
            return result
        for path in sorted(self.slots.iterdir()):
            if path.is_dir() and (path / "manifest.yaml").exists():
                try:
                    state, item = self.load_slot(path.name)
                except SaveError:
                    continue
                meta = state.get("meta") if isinstance(state, dict) else {}
                node = state.get("current_node") if isinstance(state, dict) else {}
                if isinstance(meta, dict) and isinstance(meta.get("turn"), int):
                    item["turn"] = meta["turn"]
                if isinstance(node, dict) and isinstance(node.get("unresolved_action"), str):
                    item["summary"] = node["unresolved_action"].strip()[:80]
                result.append(item)
        return result

    def _read_pair(self, slot: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        """Caller holds the slot lock; parse and checksum the exact same bytes."""
        try:
            manifest_bytes = self.manifest_path(slot).read_bytes()
            state_bytes = self.state_path(slot).read_bytes()
            manifest = self._read_manifest(slot, manifest_bytes)
            state = _COMMON.load_yaml_bytes(state_bytes, self.state_path(slot))
        except (OSError, _COMMON.CommonError) as exc:
            raise SaveError(f"cannot read slot {slot}: {exc}") from exc
        if manifest["manifest_version"] >= 2:
            if self._state_sha256(state_bytes) != manifest["state_sha256"]:
                raise SaveError(f"manifest/state checksum mismatch: {slot}")
        if not isinstance(state, dict):
            raise SaveError(f"state is not a mapping: {self.state_path(slot)}")
        self._validate_state(state)
        return state, manifest, state_bytes, manifest_bytes

    def load_slot(self, slot: str) -> tuple[dict[str, Any], dict[str, Any]]:
        slot = slot_name(slot)
        if not self.manifest_path(slot).exists():
            raise SaveError(f"slot does not exist or has no manifest: {slot}")
        try:
            with _COMMON.FileLock(self.lock_path(slot)):
                state, manifest, _, _ = self._read_pair(slot)
        except _COMMON.CommonError as exc:
            raise SaveError(str(exc)) from exc
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
        slot = slot_name(slot)
        candidate = load_yaml(state_source)
        if not isinstance(candidate, dict):
            raise SaveError("candidate state must be a mapping")
        self._validate_state(candidate)
        # 槽不存在时先拒绝，避免为拼错的槽名留下只含 .write.lock 的垃圾目录。
        if not self.manifest_path(slot).exists():
            raise SaveError(f"slot does not exist or has no manifest: {slot} (init it first)")
        try:
            lock = _COMMON.FileLock(self.lock_path(slot))
            lock.__enter__()
        except _COMMON.CommonError as exc:
            raise SaveError(str(exc)) from exc
        try:
            _, manifest, prior_state, prior_manifest = self._read_pair(slot)
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
            state_text = yaml_text(candidate)
            updated["manifest_version"] = 2
            updated["state_sha256"] = self._state_sha256(state_text)
            try:
                write_atomic(self.state_path(slot), state_text)
                write_atomic(self.manifest_path(slot), yaml_text(updated))
            except Exception as exc:
                try:
                    _COMMON.write_atomic_bytes(self.state_path(slot), prior_state)
                    _COMMON.write_atomic_bytes(self.manifest_path(slot), prior_manifest)
                except OSError as rollback_exc:
                    raise SaveError(f"slot write and rollback failed: {rollback_exc}") from exc
                raise SaveError(f"slot write failed; prior pair restored: {exc}") from exc
            return updated
        finally:
            lock.__exit__(None, None, None)


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
