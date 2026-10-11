"""Sprint 5: work-unit generation math (exit condition: 1000/100 → 10 units)."""

from app.services.jobs import plan_units, unit_count


def test_thousand_by_hundred_makes_ten_units():
    ranges = plan_units(1000, 100)
    assert len(ranges) == 10
    assert unit_count(1000, 100) == 10
    assert ranges[0] == (1, 100)
    assert ranges[-1] == (901, 1000)


def test_uneven_split_clamps_last_chunk():
    ranges = plan_units(1000, 300)
    assert ranges == [(1, 300), (301, 600), (601, 900), (901, 1000)]
    assert unit_count(1000, 300) == 4


def test_ranges_are_contiguous_and_complete():
    total, chunk = 997, 50
    ranges = plan_units(total, chunk)
    assert ranges[0][0] == 1
    assert ranges[-1][1] == total
    for (s1, e1), (s2, _e2) in zip(ranges, ranges[1:]):
        assert s2 == e1 + 1  # contiguous, no gaps/overlaps
    assert sum(e - s + 1 for s, e in ranges) == total


def test_single_unit_when_chunk_covers_all():
    assert plan_units(10, 25) == [(1, 10)]
    assert unit_count(10, 25) == 1


def test_exact_multiple():
    assert plan_units(12, 3) == [(1, 3), (4, 6), (7, 9), (10, 12)]
