"""Per-invocation context: data directory, database connection, content."""

import os

from .. import paths
from ..errors import DATA_DIR_UNAVAILABLE, AppError, detail


def _suggestions(source):
    tips = [
        "用 --data-dir 指向一个可写目录（不要放在 Skill 目录里）",
        "或设置环境变量 %s 指向可写目录" % paths.ENV_VAR,
        "如果宿主在沙箱里运行，请让宿主放行该目录",
    ]
    if source == "arg":
        tips.insert(0, "检查 --data-dir 给出的路径是否存在且可写")
    elif source == "env":
        tips.insert(0, "检查环境变量 %s 的值是否正确" % paths.ENV_VAR)
    return tips


def _write_probe(directory):
    probe = os.path.join(directory, ".write-probe-%d" % os.getpid())
    fd = os.open(probe, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, b"ok")
    finally:
        os.close(fd)
    os.remove(probe)


class Context:
    def __init__(self, skill_root, data_dir_arg=None, environ=None, flags=None, debug=False):
        self.skill_root = os.path.abspath(skill_root)
        self.environ = os.environ if environ is None else environ
        self.flags = dict(flags or {})
        self.debug = debug
        self.data_dir, self.data_dir_source = paths.resolve(data_dir_arg, self.environ)
        self._prepared = False
        self._conn = None
        self._content = None
        self.schema_report = None

    def drafts_switch(self):
        """The development switch ADULT_TENSION_INCLUDE_DRAFTS=1 (set by a test
        harness): worlds not yet released can be opened."""
        return self.environ.get("ADULT_TENSION_INCLUDE_DRAFTS") == "1"

    # -- data directory ----------------------------------------------------

    def data_dir_problem(self):
        """Return (reason, hint) if the data directory is unusable, else None."""
        if paths.is_inside(self.data_dir, self.skill_root):
            return "数据目录位于 Skill 目录内部，升级时会被覆盖", "把数据目录放在 Skill 目录之外"
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            for sub in paths.SUBDIRS:
                os.makedirs(os.path.join(self.data_dir, sub), exist_ok=True)
            _write_probe(self.data_dir)
        except OSError as exc:
            return "%s: %s" % (type(exc).__name__, exc.strerror or exc), None
        return None

    def prepare_data_dir(self):
        if self._prepared:
            return
        problem = self.data_dir_problem()
        if problem is not None:
            reason, hint = problem
            tips = _suggestions(self.data_dir_source)
            if hint:
                tips.insert(0, hint)
            raise AppError(
                DATA_DIR_UNAVAILABLE,
                "数据目录不可用：%s" % self.data_dir,
                [detail("$.data_dir", reason, tips[0])],
                tried=[{"path": self.data_dir, "source": self.data_dir_source, "reason": reason}],
                suggestions=tips,
            )
        self._prepared = True

    # -- database ------------------------------------------------------------

    def db(self):
        if self._conn is None:
            from ..persistence import db

            self.prepare_data_dir()
            conn = db.connect(paths.db_path(self.data_dir))
            try:
                self.schema_report = db.ensure_schema(conn, os.path.join(self.data_dir, "backups"))
            except Exception:
                conn.close()
                raise
            self._conn = conn
        return self._conn

    # -- content -------------------------------------------------------------

    def content(self):
        if self._content is None:
            from ..content.store import ContentStore

            self._content = ContentStore(os.path.join(self.skill_root, "content"))
        return self._content

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
