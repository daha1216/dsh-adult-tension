"""Command registry: the single table of CLI commands.

Every entry names its handler lazily (module, function) so a cold process
imports only what the command needs. `input` is one of:
  none      - takes no input (an empty object is accepted)
  optional  - input only from --input-file (use `--input-file -` for stdin)
  required  - input from --input-file, or stdin when stdin is not a terminal
`category` follows RUNTIME_PROTOCOL.md section 2.1. `spec` names the input
spec in application/specs.py (for the generated references).
"""


class Command:
    __slots__ = ("name", "module", "func", "input", "category", "summary", "flags", "spec")

    def __init__(self, name, module, func, input, category, summary, flags=None, spec=None):
        self.name = name
        self.module = module
        self.func = func
        self.input = input
        self.category = category
        self.summary = summary
        self.flags = flags or {}
        self.spec = spec


COMMANDS = {}
APP = "adult_tension.application."


def _register(*args, **kwargs):
    command = Command(*args, **kwargs)
    COMMANDS[command.name] = command


_register("doctor", APP + "doctor", "run", "none", "diagnostic", "检查环境并完成首次初始化（幂等）")
_register("version", APP + "info", "version", "none", "read", "Skill、内容、存档格式、RNG 版本")
_register(
    "list-worlds",
    APP + "service",
    "list_worlds",
    "optional",
    "read",
    "世界列表、一句话介绍、支持的模式",
    {"--include-drafts": ("include_drafts", "bool")},
    "LIST_WORLDS",
)
_register("new-game", APP + "service", "new_game", "required", "create", "开局", {"--include-drafts": ("include_drafts", "bool")}, "NEW_GAME")
_register("get-context", APP + "service", "get_context", "required", "read", "当前上下文（brief / full）；可带快进预览 preview_time 与转折候选 want_twist", spec="GET_CONTEXT")
_register("commit-turn", APP + "service", "commit_turn", "required", "session_write", "叙事回合：提交操作，返回结果与下一回合上下文", spec="COMMIT_TURN")
_register("undo-turn", APP + "service", "undo_turn", "required", "session_write", "撤销上一回合（最多退到本次读档或开局）", spec="UNDO_TURN")
_register("save-slot", APP + "service", "save_slot", "required", "session_write", "存档（省略名字时存到当前槽或自动命名）", spec="SAVE_SLOT")
_register("load-slot", APP + "service", "load_slot", "required", "create", "读档：创建新的会话副本，原存档不变", spec="LOAD_SLOT")
_register("list-slots", APP + "service", "list_slots", "none", "read", "存档列表")
_register("set-boundary", APP + "service", "set_boundary", "required", "session_write", "登记或撤销硬边界", spec="SET_BOUNDARY")
_register("set-safety", APP + "service", "set_safety", "required", "session_write", "暂停、恢复、换个场景", spec="SET_SAFETY")
_register("set-preferences", APP + "service", "set_preferences", "required", "session_write", "内心可见、叙事助手、离屏推演、语态、人称、配对偏好", spec="SET_PREFERENCES")
_register("status", APP + "service", "status", "required", "read", "状态：brief 六行 / detail 状态+ / debug 调试", spec="STATUS")
_register(
    "verify-content",
    APP + "verify",
    "run",
    "optional",
    "dev",
    "校验全部内容（结构、语义、时代、固定种子开局、多样性）",
    {"--world": ("world", "str"), "--stats": ("stats", "bool"), "--skip-diversity": ("skip_diversity", "bool")},
    "VERIFY_CONTENT",
)
_register(
    "smoke",
    APP + "smoke",
    "run",
    "optional",
    "dev",
    "在临时数据目录用假叙述者跑一条短局",
    {"--seed": ("seed", "int"), "--turns": ("turns", "int")},
    "SMOKE",
)


def get(name):
    return COMMANDS.get(name)
