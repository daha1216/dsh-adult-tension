# -*- coding: utf-8 -*-
"""Adult Tension runtime entry point.

Usage: python scripts/adult_tension.py <command> --json [--input-file PATH] [--data-dir PATH]

This file must stay parseable by old Python versions, so that a too-old
interpreter receives a RUNTIME_UNSUPPORTED envelope instead of a SyntaxError.
Keep it free of f-strings, annotations, the walrus operator and any other
modern syntax. Everything else lives in runtime/adult_tension/.
"""
import sys

MIN_PYTHON = (3, 10)
EXIT_ENVIRONMENT = 20


def _write_bytes(data):
    stream = getattr(sys.stdout, "buffer", sys.stdout)
    stream.write(data)
    stream.flush()


def _unsupported(version_info):
    import json

    found = ".".join([str(part) for part in version_info[:3]])
    need = ".".join([str(part) for part in MIN_PYTHON])
    envelope = {
        "ok": False,
        "data": None,
        "error": {
            "code": "RUNTIME_UNSUPPORTED",
            "message": u"需要 Python " + need + u" 或更高版本，当前是 " + found,
            "details": [
                {
                    "path": "$.python",
                    "reason": "Python " + found + " < " + need,
                    "hint": u"换用 Python " + need + u"+ 运行（依次试 python3、python、py -3）；不要自动安装或修改系统环境",
                }
            ],
            "required": need,
            "found": found,
        },
    }
    _write_bytes(json.dumps(envelope, ensure_ascii=True).encode("ascii"))
    return EXIT_ENVIRONMENT


def main():
    if tuple(sys.version_info[:2]) < MIN_PYTHON:
        return _unsupported(sys.version_info)
    import os

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.dirname(scripts_dir)
    runtime_dir = os.path.join(skill_root, "runtime")
    # The Skill directory must stay free of caches: nothing is compiled into it
    # until the launcher has moved the bytecode cache to the data directory.
    sys.dont_write_bytecode = True
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from adult_tension.launcher import launch

    return launch(sys.argv[1:], skill_root)


if __name__ == "__main__":
    sys.exit(main())
