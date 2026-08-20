#!/usr/bin/env python3
"""Manage isolated, versioned, and branchable v3 narrative save slots."""

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


SLOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_LEASE_SECONDS = 120


class SaveError(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def slot_name(value: str) -> str:
    if not SLOT_RE.fullmatch(value):
        raise SaveError("slot must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    return value


def yaml_text(data: Any) -> str:
    if yaml is None:
        raise SaveError("PyYAML is required; run: python -m pip install PyYAML")
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def load_yaml(path: Path) -> Any:
    if yaml is None:
        raise SaveError("PyYAML is required; run: python -m pip install PyYAML")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SaveError(f"cannot read YAML {path}: {exc}") from exc


def write_atomic(path: Path, text: str) -> None:
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


class FileLock:
    """Cross-platform advisory lock on one byte in a slot lock file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0)
        self.handle.write(b"0")
        self.handle.flush()
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - exercised on POSIX CI
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
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
        self.index_path = root / "index.yaml"

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
        return manifest

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
    def state_hash(state: dict[str, Any]) -> str:
        payload = yaml_text(state).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _new_manifest(
        slot: str,
        state: dict[str, Any],
        *,
        access_mode: str,
        session_id: str | None,
        parent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if access_mode not in {"isolated", "shared"}:
            raise SaveError("access_mode must be isolated or shared")
        state_hash = SaveStore.state_hash(state)
        manifest: dict[str, Any] = {
            "manifest_version": 1,
            "archive_id": f"adult-tension-{slot}",
            "slot": slot,
            "branch_id": slot,
            "revision": 0,
            "state_sha256": state_hash,
            "parent_revision": None,
            "parent_archive": None,
            "access_mode": access_mode,
            "created_at": iso_now(),
            "updated_at": iso_now(),
            "writer_session_id": session_id,
            "lease": {"owner": None, "expires_at": None},
        }
        if parent:
            manifest["parent_archive"] = parent["archive_id"]
            manifest["parent_revision"] = parent["revision"]
        return manifest

    def _write_index(self) -> None:
        with FileLock(self.root / ".index.lock"):
            entries: list[dict[str, Any]] = []
            if self.slots.exists():
                for path in sorted(self.slots.iterdir()):
                    if not path.is_dir() or not (path / "manifest.yaml").exists():
                        continue
                    try:
                        manifest = self._read_manifest(path.name)
                    except SaveError:
                        continue
                    entries.append({
                        "slot": path.name,
                        "archive_id": manifest.get("archive_id"),
                        "branch_id": manifest.get("branch_id"),
                        "revision": manifest.get("revision"),
                        "access_mode": manifest.get("access_mode"),
                        "updated_at": manifest.get("updated_at"),
                    })
            write_atomic(self.index_path, yaml_text({"index_version": 1, "slots": entries}))

    def init_slot(
        self,
        slot: str,
        source: Path,
        *,
        access_mode: str = "isolated",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        slot = slot_name(slot)
        if self.slot_dir(slot).exists():
            raise SaveError(f"slot already exists: {slot}")
        state = load_yaml(source)
        if not isinstance(state, dict):
            raise SaveError("source state must be a mapping")
        self._validate_state(state)
        manifest = self._new_manifest(slot, state, access_mode=access_mode, session_id=session_id)
        self.state_path(slot).parent.mkdir(parents=True, exist_ok=False)
        write_atomic(self.state_path(slot), yaml_text(state))
        write_atomic(self.manifest_path(slot), yaml_text(manifest))
        self._write_index()
        return manifest

    def list_slots(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not self.slots.exists():
            return result
        for path in sorted(self.slots.iterdir()):
            if path.is_dir() and (path / "manifest.yaml").exists():
                result.append(self._read_manifest(path.name))
        return result

    def load_slot(self, slot: str) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = self._read_manifest(slot)
        state = self._read_state(slot)
        actual_hash = self.state_hash(state)
        if actual_hash != manifest.get("state_sha256"):
            raise SaveError(f"state hash mismatch for slot {slot}; refuse to load")
        self._validate_state(state)
        return state, manifest

    @staticmethod
    def _lease_active(manifest: dict[str, Any], now: dt.datetime | None = None) -> bool:
        lease = manifest.get("lease")
        if not isinstance(lease, dict) or not lease.get("owner"):
            return False
        expiry = parse_time(lease.get("expires_at"))
        return expiry is not None and expiry > (now or utc_now())

    def _check_writer(self, manifest: dict[str, Any], session_id: str | None) -> None:
        if manifest.get("access_mode") != "shared":
            return
        if not session_id:
            raise SaveError("shared slot writes require --session-id")
        lease = manifest.get("lease")
        if not self._lease_active(manifest) or not isinstance(lease, dict) or lease.get("owner") != session_id:
            raise SaveError("shared slot is not leased to this session; acquire it first")

    def save_slot(
        self,
        slot: str,
        state_source: Path,
        *,
        expected_revision: int,
        expected_hash: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        candidate = load_yaml(state_source)
        if not isinstance(candidate, dict):
            raise SaveError("candidate state must be a mapping")
        self._validate_state(candidate)
        with FileLock(self.lock_path(slot)):
            manifest = self._read_manifest(slot)
            current_revision = manifest.get("revision")
            current_hash = manifest.get("state_sha256")
            if current_revision != expected_revision:
                raise SaveError(f"write conflict: expected revision {expected_revision}, current revision {current_revision}")
            if expected_hash is not None and current_hash != expected_hash:
                raise SaveError("write conflict: expected state hash does not match current state")
            self._check_writer(manifest, session_id)
            new_hash = self.state_hash(candidate)
            next_revision = expected_revision + 1
            updated = dict(manifest)
            updated.update({
                "revision": next_revision,
                "state_sha256": new_hash,
                "parent_revision": expected_revision,
                "updated_at": iso_now(),
                "writer_session_id": session_id,
            })
            write_atomic(self.state_path(slot), yaml_text(candidate))
            write_atomic(self.manifest_path(slot), yaml_text(updated))
            self._write_index()
            return updated

    def set_access_mode(self, slot: str, access_mode: str) -> dict[str, Any]:
        if access_mode not in {"isolated", "shared"}:
            raise SaveError("access_mode must be isolated or shared")
        with FileLock(self.lock_path(slot)):
            manifest = self._read_manifest(slot)
            if self._lease_active(manifest):
                raise SaveError("cannot change access mode while a shared lease is active")
            manifest["access_mode"] = access_mode
            manifest["updated_at"] = iso_now()
            if access_mode == "isolated":
                manifest["lease"] = {"owner": None, "expires_at": None}
            write_atomic(self.manifest_path(slot), yaml_text(manifest))
            self._write_index()
            return manifest

    def acquire(self, slot: str, session_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> dict[str, Any]:
        if not session_id.strip():
            raise SaveError("session_id must not be empty")
        if lease_seconds <= 0:
            raise SaveError("lease_seconds must be positive")
        with FileLock(self.lock_path(slot)):
            manifest = self._read_manifest(slot)
            if manifest.get("access_mode") != "shared":
                raise SaveError("only shared slots use leases")
            lease = manifest.setdefault("lease", {"owner": None, "expires_at": None})
            if self._lease_active(manifest) and lease.get("owner") != session_id:
                raise SaveError(f"shared slot is leased to session {lease.get('owner')}")
            lease["owner"] = session_id
            lease["expires_at"] = (utc_now() + dt.timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
            manifest["updated_at"] = iso_now()
            manifest["writer_session_id"] = session_id
            write_atomic(self.manifest_path(slot), yaml_text(manifest))
            self._write_index()
            return manifest

    def release(self, slot: str, session_id: str) -> dict[str, Any]:
        with FileLock(self.lock_path(slot)):
            manifest = self._read_manifest(slot)
            lease = manifest.get("lease")
            if not isinstance(lease, dict) or lease.get("owner") != session_id:
                raise SaveError("session does not own the shared slot lease")
            lease["owner"] = None
            lease["expires_at"] = None
            manifest["updated_at"] = iso_now()
            write_atomic(self.manifest_path(slot), yaml_text(manifest))
            self._write_index()
            return manifest

    def branch(self, source_slot: str, new_slot: str, *, access_mode: str = "isolated", session_id: str | None = None) -> dict[str, Any]:
        new_slot = slot_name(new_slot)
        if self.slot_dir(new_slot).exists():
            raise SaveError(f"slot already exists: {new_slot}")
        with FileLock(self.lock_path(source_slot)):
            state, parent = self.load_slot(source_slot)
            self._validate_state(state)
            manifest = self._new_manifest(new_slot, state, access_mode=access_mode, session_id=session_id, parent=parent)
            self.state_path(new_slot).parent.mkdir(parents=True, exist_ok=False)
            write_atomic(self.state_path(new_slot), yaml_text(state))
            write_atomic(self.manifest_path(new_slot), yaml_text(manifest))
            self._write_index()
            return manifest


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1] / "saves")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a slot from a v3 state")
    init.add_argument("slot")
    init.add_argument("source", type=Path)
    init.add_argument("--access-mode", choices=["isolated", "shared"], default="isolated")
    init.add_argument("--session-id")

    sub.add_parser("list", help="list slots")

    load = sub.add_parser("load", help="validate and print a slot manifest")
    load.add_argument("slot")

    save = sub.add_parser("save", help="CAS-save a candidate v3 state")
    save.add_argument("slot")
    save.add_argument("state_source", type=Path)
    save.add_argument("--expected-revision", type=int, required=True)
    save.add_argument("--expected-hash")
    save.add_argument("--session-id")

    branch = sub.add_parser("branch", help="create a slot from the current source slot")
    branch.add_argument("source_slot")
    branch.add_argument("new_slot")
    branch.add_argument("--access-mode", choices=["isolated", "shared"], default="isolated")
    branch.add_argument("--session-id")

    mode = sub.add_parser("mode", help="set isolated or shared access mode")
    mode.add_argument("slot")
    mode.add_argument("access_mode", choices=["isolated", "shared"])

    acquire = sub.add_parser("acquire", help="acquire or renew a shared-slot lease")
    acquire.add_argument("slot")
    acquire.add_argument("session_id")
    acquire.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)

    release = sub.add_parser("release", help="release a shared-slot lease")
    release.add_argument("slot")
    release.add_argument("session_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    if yaml is None:
        print("ERROR: PyYAML is required; run: python -m pip install PyYAML", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    store = SaveStore(args.root)
    try:
        if args.command == "init":
            print_json(store.init_slot(args.slot, args.source, access_mode=args.access_mode, session_id=args.session_id))
        elif args.command == "list":
            print_json(store.list_slots())
        elif args.command == "load":
            _, manifest = store.load_slot(args.slot)
            print_json(manifest)
        elif args.command == "save":
            print_json(store.save_slot(args.slot, args.state_source, expected_revision=args.expected_revision, expected_hash=args.expected_hash, session_id=args.session_id))
        elif args.command == "branch":
            print_json(store.branch(args.source_slot, args.new_slot, access_mode=args.access_mode, session_id=args.session_id))
        elif args.command == "mode":
            print_json(store.set_access_mode(args.slot, args.access_mode))
        elif args.command == "acquire":
            print_json(store.acquire(args.slot, args.session_id, args.lease_seconds))
        elif args.command == "release":
            print_json(store.release(args.slot, args.session_id))
        return 0
    except SaveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
