"""Verification of the installed (compiled) content, used by doctor."""

from ..errors import AppError, detail


def verify_installed(store):
    """Return (problems, summary) for the compiled content directory."""
    problems = []
    index = store.index()
    worlds = index.get("worlds")
    if not isinstance(worlds, list):
        problems.append(detail("content/index.json $.worlds", "缺少世界列表", "重新编译内容"))
        worlds = []
    released = 0
    for position, entry in enumerate(worlds):
        world_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(world_id, str):
            problems.append(detail("content/index.json $.worlds[%d].id" % position, "缺少世界 ID", "重新编译内容"))
            continue
        try:
            store.world(world_id)
        except AppError as err:
            problems.extend(err.details)
            continue
        if entry.get("status") == "released":
            released += 1
    summary = {"content_version": index.get("content_version"), "worlds": len(worlds), "released_worlds": released}
    return problems, summary
