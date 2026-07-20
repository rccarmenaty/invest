"""Portfolio-layer admission: seeded random slot selection when oversubscribed.

Scanners remain pure decision producers. This module only chooses which same-day
candidates may attempt a fill under a concurrent-position cap. Ranking by
momentum / 52-week / ID is intentionally absent — Phase 2 structure control.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from datetime import date

KIND_RANKED = "ranked"
KIND_SEEDED_RANDOM = "seeded-random"
# Same-day candidate lost the seeded slot lottery (book may still have free slots).
SLOT_NOT_ADMITTED_REASON = "slot-not-admitted"


def select_seeded_slot_admissions(
    candidates: Sequence[str],
    free_slots: int,
    *,
    seed: int,
    day: date,
) -> tuple[str, ...]:
    """Return up to `free_slots` symbols admitted for `day`.

    Under the cap (len(candidates) <= free_slots): all candidates, sorted by
    symbol for stable fill order. Oversubscribed: deterministic sample of size
    free_slots using (seed, day), then sorted by symbol for stable fill order
    among the admitted set.
    """
    if free_slots <= 0:
        return ()
    ordered = tuple(sorted(candidates))
    if len(ordered) <= free_slots:
        return ordered
    # Mix seed with calendar day so same-run days are independent; int only
    # (Random rejects tuple seeds on modern CPython).
    rng = random.Random(seed ^ (day.toordinal() * 1_000_003))
    return tuple(sorted(rng.sample(list(ordered), free_slots)))


def admission_provenance(
    *,
    max_concurrent_positions: int,
    admission_seed: int | None,
) -> Mapping[str, str | int]:
    """Frozen provenance for CLI/report consumers (Phase 2 and ranked baseline)."""
    if admission_seed is None:
        payload: dict[str, str | int] = {
            "kind": KIND_RANKED,
            "max_concurrent_positions": max_concurrent_positions,
        }
    else:
        payload = {
            "kind": KIND_SEEDED_RANDOM,
            "max_concurrent_positions": max_concurrent_positions,
            "seed": admission_seed,
        }
    return {key: payload[key] for key in sorted(payload)}
