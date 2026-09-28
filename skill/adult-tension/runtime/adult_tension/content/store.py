"""Read-only access to the compiled content in <skill>/content/.

The runtime never parses content sources; it reads compiled JSON only and
loads lazily: list-worlds reads index.json, an opening reads one world.
A world is validated when it is first loaded (SKILL_PACKAGING 7, 10): a
compiled file changed after the build is reported with its location instead
of producing a broken opening.
"""

import os

from ..errors import CONTENT_ERROR, AppError, detail
from ..jsonio import decode_bytes, loads_strict, plain


class ContentStore:
    def __init__(self, content_dir):
        self.content_dir = content_dir
        self._index = None
        self._tags = None
        self._worlds = {}

    def _read(self, rel):
        path = os.path.join(self.content_dir, rel)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise AppError(
                CONTENT_ERROR,
                "内容文件缺失或不可读：content/%s" % rel,
                [detail("content/%s" % rel, str(exc.strerror or exc), "重新安装 Skill 目录")],
            )
        try:
            return plain(loads_strict(decode_bytes(raw, "content/%s" % rel), "content/%s" % rel))
        except AppError as err:
            raise AppError(
                CONTENT_ERROR,
                "内容文件损坏：content/%s" % rel,
                [dict(d, path="content/%s %s" % (rel, d["path"])) for d in err.details],
            )

    def index(self):
        if self._index is None:
            self._index = self._read("index.json")
        return self._index

    def tags(self):
        if self._tags is None:
            self._tags = self._read("tags.json")
        return self._tags

    def world_raw(self, world_id):
        """The compiled file as parsed, without validation (verify-content validates it itself)."""
        return self._read(os.path.join("worlds", world_id + ".json"))

    def world(self, world_id):
        if world_id not in self._worlds:
            from ..domain.worldpack import validate_world

            rel = "worlds/%s.json" % world_id
            raw = self._read(os.path.join("worlds", world_id + ".json"))
            _pack, problems = validate_world(raw, custom=False, tag_ids=[t["id"] for t in self.tags()["tags"]])
            if problems:
                raise AppError(
                    CONTENT_ERROR,
                    "内容文件校验失败：content/%s" % rel,
                    [dict(p, path="content/%s %s" % (rel, p["path"]), hint=p.get("hint") or "重新安装 Skill 目录") for p in problems],
                )
            self._worlds[world_id] = raw
        return self._worlds[world_id]

    def files(self):
        """Relative paths of every compiled content file, sorted."""
        found = []
        for root, _dirs, names in os.walk(self.content_dir):
            for name in names:
                rel = os.path.relpath(os.path.join(root, name), self.content_dir)
                found.append(rel.replace(os.sep, "/"))
        return sorted(found)

    def stamp(self):
        """Cheap change detector for doctor's fast path: (path, size, mtime)."""
        stamp = []
        for rel in self.files():
            info = os.stat(os.path.join(self.content_dir, rel))
            stamp.append([rel, info.st_size, info.st_mtime_ns])
        return stamp
