"""Stable error codes, exit codes and the structured application error."""

INVALID_INPUT = "INVALID_INPUT"
STALE_REVISION = "STALE_REVISION"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
INVARIANT_VIOLATION = "INVARIANT_VIOLATION"
SAFETY_BLOCK = "SAFETY_BLOCK"
CONTENT_ERROR = "CONTENT_ERROR"
NOT_FOUND = "NOT_FOUND"
SLOT_CONFLICT = "SLOT_CONFLICT"
UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
RUNTIME_UNSUPPORTED = "RUNTIME_UNSUPPORTED"
DATA_DIR_UNAVAILABLE = "DATA_DIR_UNAVAILABLE"
STORAGE_BUSY = "STORAGE_BUSY"
NO_MATCH = "NO_MATCH"
MIGRATION_FAILED = "MIGRATION_FAILED"
INTERNAL_ERROR = "INTERNAL_ERROR"

EXIT_OK = 0
EXIT_INPUT = 10  # input and domain errors: the caller can fix the request
EXIT_ENVIRONMENT = 20  # environment errors: Python, data directory, storage, versions
EXIT_INTERNAL = 30  # unexpected errors; state is unchanged

EXIT_CODES = {
    INVALID_INPUT: EXIT_INPUT,
    STALE_REVISION: EXIT_INPUT,
    IDEMPOTENCY_CONFLICT: EXIT_INPUT,
    INVARIANT_VIOLATION: EXIT_INPUT,
    SAFETY_BLOCK: EXIT_INPUT,
    CONTENT_ERROR: EXIT_INPUT,
    NOT_FOUND: EXIT_INPUT,
    SLOT_CONFLICT: EXIT_INPUT,
    NO_MATCH: EXIT_INPUT,
    UNSUPPORTED_VERSION: EXIT_ENVIRONMENT,
    RUNTIME_UNSUPPORTED: EXIT_ENVIRONMENT,
    DATA_DIR_UNAVAILABLE: EXIT_ENVIRONMENT,
    STORAGE_BUSY: EXIT_ENVIRONMENT,
    MIGRATION_FAILED: EXIT_ENVIRONMENT,
    INTERNAL_ERROR: EXIT_INTERNAL,
}

# When one request produces details with several codes, the envelope reports
# the most important one. Safety first: the model must tell the player.
CODE_PRIORITY = (
    SAFETY_BLOCK,
    INVARIANT_VIOLATION,
    NOT_FOUND,
    CONTENT_ERROR,
    INVALID_INPUT,
)

ERROR_DESCRIPTIONS = {
    INVALID_INPUT: "输入格式或字段错误",
    STALE_REVISION: "expected_revision 过期；错误中附当前 revision 与简要上下文",
    IDEMPOTENCY_CONFLICT: "同一 request_id 携带了不同的内容",
    INVARIANT_VIOLATION: "违反领域规则（冷却、知识边界、授权、幅度等）",
    SAFETY_BLOCK: "与硬边界冲突、暂停中、年龄问题",
    CONTENT_ERROR: "内容包或自定义世界校验失败",
    NOT_FOUND: "会话、存档、角色、事件不存在",
    SLOT_CONFLICT: "存档名已被占用（exists），或本局当前槽已在别的对话里被写过（changed_elsewhere）",
    UNSUPPORTED_VERSION: "存档、数据库或内容版本不受支持",
    RUNTIME_UNSUPPORTED: "Python 版本过低或缺少 SQLite 等必要能力",
    DATA_DIR_UNAVAILABLE: "数据目录不可写；附尝试过的路径与建议",
    STORAGE_BUSY: "数据库被其他进程短暂占用；用同一 request_id 重试",
    NO_MATCH: "开局约束在所选世界中无法满足；附冲突的约束与可放宽项",
    MIGRATION_FAILED: "数据库迁移失败，已恢复迁移前的备份",
    INTERNAL_ERROR: "未预期错误；附日志位置，状态不变",
}


def detail(path, reason, hint=None, code=None):
    item = {"path": path, "reason": reason, "hint": hint}
    if code is not None:
        item["code"] = code
    return item


def top_code(details, default=INVALID_INPUT):
    codes = {d.get("code") for d in details if d.get("code")}
    for code in CODE_PRIORITY:
        if code in codes:
            return code
    return default


class AppError(Exception):
    """A structured, user-fixable (or environment) error."""

    def __init__(self, code, message, details=None, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = list(details or [])
        self.extra = extra

    def to_dict(self):
        body = {"code": self.code, "message": self.message, "details": self.details}
        for key, value in self.extra.items():
            body[key] = value
        return body


def fail(details, message=None, default=INVALID_INPUT, **extra):
    """Raise an AppError summarising a list of details."""
    code = top_code(details, default)
    if message is None:
        message = "有 %d 处错误" % len(details) if len(details) != 1 else details[0]["reason"]
    raise AppError(code, message, details, **extra)


def exit_code_for(code):
    return EXIT_CODES.get(code, EXIT_INTERNAL)
