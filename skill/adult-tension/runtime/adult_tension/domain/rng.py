"""Deterministic randomness (DESIGN_DECISIONS.md D10, ARCHITECTURE.md section 5).

Every draw is derived from structured coordinates only: the session seed,
the RNG version, a purpose, and ids / turn numbers / indexes. Free text
written by the model never enters the derivation, so rewording cannot reroll.
"""

import hashlib
import json

from .. import RNG_VERSION


def unit(seed, purpose, *coords, version=RNG_VERSION):
    """A uniform number in [0, 1) derived from the coordinates."""
    material = json.dumps([version, seed, purpose] + list(coords), ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") / 18446744073709551616.0


def randint(seed, purpose, lo, hi, *coords):
    """An integer in [lo, hi] inclusive."""
    return lo + int(unit(seed, purpose, *coords) * (hi - lo + 1))


def pick(seed, purpose, items, *coords):
    """Pick one item from a list whose order the caller fixed (e.g. sorted by id)."""
    if not items:
        raise ValueError("pick from empty list")
    return items[int(unit(seed, purpose, *coords) * len(items))]


def weighted(seed, purpose, items, weights, *coords):
    total = float(sum(weights))
    if total <= 0:
        raise ValueError("weights must be positive")
    point = unit(seed, purpose, *coords) * total
    acc = 0.0
    for item, weight in zip(items, weights):
        acc += weight
        if point < acc:
            return item
    return items[-1]


def shuffled(seed, purpose, items, *coords):
    """A deterministic permutation (sort by derived keys)."""
    keyed = [(unit(seed, purpose, index, *coords), index, item) for index, item in enumerate(items)]
    keyed.sort(key=lambda entry: (entry[0], entry[1]))
    return [item for _key, _index, item in keyed]
