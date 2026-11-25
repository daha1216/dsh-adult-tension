"""Verification of the installed (compiled) content, used by doctor."""

from ..errors import CONTENT_ERROR, AppError, detail


def verify_installed(store):
    """Return (problems, summary) for the compiled content directory.

    A world whose bytes still match the digest the compiler recorded was
    validated when it was compiled; only the others are validated again.
    Every opening validates its world in full anyway (ContentStore.world)."""
    problems = []
    try:
        index = store.index()
    except AppError as err:
        problems.extend(err.details or [detail("content/index.json", err.message, "重新安装 Skill 目录", CONTENT_ERROR)])
        index = None
    if index is not None and not isinstance(index, dict):
        problems.append(detail("content/index.json $", "索引文件应为 JSON 对象", "重新安装 Skill 目录", CONTENT_ERROR))
        index = None
    try:
        tags_doc = store.tags()
    except AppError as err:
        problems.extend(err.details or [detail("content/tags.json", err.message, "重新安装 Skill 目录", CONTENT_ERROR)])
    else:
        if not isinstance(tags_doc, dict):
            problems.append(detail("content/tags.json $", "标签文件应为 JSON 对象", "重新安装 Skill 目录", CONTENT_ERROR))
        else:
            tags_list = tags_doc.get("tags")
            if not isinstance(tags_list, list) or not tags_list:
                problems.append(detail("content/tags.json $.tags", "缺少标签列表或列表为空", "重新安装 Skill 目录", CONTENT_ERROR))
            else:
                for pos, tag in enumerate(tags_list):
                    if not isinstance(tag, dict) or not isinstance(tag.get("id"), str) or not tag["id"]:
                        problems.append(detail("content/tags.json $.tags[%d].id" % pos, "缺少有效的标签 ID", "重新安装 Skill 目录", CONTENT_ERROR))
    worlds = index.get("worlds") if isinstance(index, dict) else []
    if isinstance(index, dict) and not isinstance(worlds, list):
        problems.append(detail("content/index.json $.worlds", "缺少世界列表", "重新安装 Skill 目录", CONTENT_ERROR))
        worlds = []
    released = 0
    validated = 0
    for position, entry in enumerate(worlds):
        world_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(world_id, str):
            problems.append(detail("content/index.json $.worlds[%d].id" % position, "缺少世界 ID", "重新安装 Skill 目录", CONTENT_ERROR))
            continue
        digest = entry.get("sha256")
        if not (isinstance(digest, str) and store.world_digest(world_id) == digest):
            validated += 1
            try:
                store.world(world_id)
            except AppError as err:
                problems.extend(err.details)
                continue
        if entry.get("status") == "released":
            released += 1
    summary = {
        "content_version": index.get("content_version") if isinstance(index, dict) else None,
        "worlds": len(worlds),
        "released_worlds": released,
        "validated_worlds": validated,
    }
    return problems, summary
