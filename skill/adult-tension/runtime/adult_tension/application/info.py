"""Read-only informational commands."""

import platform

from .. import DB_SCHEMA_VERSION, RNG_VERSION, SAVE_FORMAT, SKILL_VERSION, STATE_SCHEMA_VERSION
from ..errors import AppError


def version(ctx, payload):
    try:
        content_version = ctx.content().index().get("content_version")
    except AppError:
        content_version = None
    return {
        "skill_version": SKILL_VERSION,
        "content_version": content_version,
        "db_schema_version": DB_SCHEMA_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "save_format": SAVE_FORMAT,
        "rng_version": RNG_VERSION,
        "python": platform.python_version(),
        "skill_root": ctx.skill_root,
    }
