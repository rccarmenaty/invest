"""Behavior of seeded slot-cap admission (Phase 2 portfolio structure)."""

from datetime import date


def test_under_cap_admits_all_candidates_in_stable_symbol_order() -> None:
    from invest.application.admission import select_seeded_slot_admissions

    admitted = select_seeded_slot_admissions(
        ("ZZZ", "AAA", "MMM"),
        free_slots=5,
        seed=7,
        day=date(2024, 6, 1),
    )

    assert admitted == ("AAA", "MMM", "ZZZ")


def test_zero_free_slots_admits_none() -> None:
    from invest.application.admission import select_seeded_slot_admissions

    admitted = select_seeded_slot_admissions(
        ("AAA", "BBB"),
        free_slots=0,
        seed=1,
        day=date(2024, 6, 1),
    )

    assert admitted == ()


def test_oversubscribe_same_seed_and_candidates_is_deterministic() -> None:
    from invest.application.admission import select_seeded_slot_admissions

    candidates = ("E", "D", "C", "B", "A")
    kwargs = dict(free_slots=2, seed=42, day=date(2024, 3, 15))

    first = select_seeded_slot_admissions(candidates, **kwargs)
    second = select_seeded_slot_admissions(candidates, **kwargs)

    assert first == second
    assert len(first) == 2
    assert set(first) <= set(candidates)


def test_oversubscribe_different_seed_can_change_admission_set() -> None:
    from invest.application.admission import select_seeded_slot_admissions

    candidates = tuple(f"S{i:02d}" for i in range(12))
    day = date(2024, 3, 15)
    sets = {
        frozenset(
            select_seeded_slot_admissions(candidates, free_slots=3, seed=seed, day=day)
        )
        for seed in range(50)
    }

    assert len(sets) > 1


def test_admission_size_never_exceeds_free_slots() -> None:
    from invest.application.admission import select_seeded_slot_admissions

    admitted = select_seeded_slot_admissions(
        tuple(f"X{i}" for i in range(20)),
        free_slots=4,
        seed=99,
        day=date(2025, 1, 2),
    )

    assert len(admitted) == 4
