"""Process bootstrap: keep bytecode caches out of the Skill directory.

The entry script disables bytecode writing before importing this module. If
the data directory can be located (and is outside the Skill directory), the
cache is redirected there so later cold starts stay fast.
"""

import os
import sys

from . import paths


def launch(argv, skill_root):
    data_dir, _source = paths.resolve(paths.data_dir_arg(argv))
    if not paths.is_inside(data_dir, skill_root):
        sys.pycache_prefix = paths.pycache_dir(data_dir)
        sys.dont_write_bytecode = False
    from .adapters.cli import run

    return run(argv, skill_root)
