"""Command registry: the single table of CLI commands.

Every entry names its handler lazily (module, function) so a cold process
imports only what the command needs. `input` is one of:
  none      - takes no input (an empty object is accepted)
  optional  - input only from --input-file (use `--input-file -` for stdin)
  required  - input from --input-file, or stdin when stdin is not a terminal
`category` follows RUNTIME_PROTOCOL.md section 2.1.
"""


class Command:
    __slots__ = ("name", "module", "func", "input", "category", "summary", "flags")

    def __init__(self, name, module, func, input, category, summary, flags=None):
        self.name = name
        self.module = module
        self.func = func
        self.input = input
        self.category = category
        self.summary = summary
        self.flags = flags or {}


# flag name -> (payload key, type) ; type is "bool", "int" or "str"
COMMANDS = {}


def _register(*args, **kwargs):
    command = Command(*args, **kwargs)
    COMMANDS[command.name] = command


_register("doctor", "adult_tension.application.doctor", "run", "none", "diagnostic", "检查环境并完成首次初始化（幂等）")
_register("version", "adult_tension.application.info", "version", "none", "read", "Skill、内容、存档格式、RNG 版本")


def get(name):
    return COMMANDS.get(name)
