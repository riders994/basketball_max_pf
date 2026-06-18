from max_pf.models import PlayerLine
from max_pf.optimize import Candidate, Slot, best_response, can_assign, objective_catwins


def cand(pid, positions, **kw):
    return Candidate(pid, PlayerLine(**kw), tuple(positions))


FLEX2 = [Slot("Flx"), Slot("Flx")]


def test_can_assign_eligibility_and_capacity():
    # Two PG-only players, one PG slot -> over capacity.
    assert not can_assign([("PG",), ("PG",)], [Slot("PG", frozenset({"PG"}))])
    # A combo G slot plus a PG slot can seat a PG and an SG.
    assert can_assign([("PG",), ("SG",)],
                      [Slot("G", frozenset({"PG", "SG"})), Slot("PG", frozenset({"PG"}))])
    # A center has no eligible slot among guard slots.
    assert not can_assign([("C",)], [Slot("PG", frozenset({"PG"}))])
    # Flex seats anyone.
    assert can_assign([("C",), ("PG",)], FLEX2)


def test_no_slot_binding_starts_everyone():
    a = cand("A", ("PG",), pts=20, reb=5, ast=5)
    b = cand("B", ("SG",), pts=10, reb=3, ast=2)
    days = [[a, b], [a]]  # day 2 only A has a game
    res = best_response(days, FLEX2, target=PlayerLine())
    assert sorted(res.started[0]) == ["A", "B"]
    assert res.started[1] == ["A"]
    assert res.line.pts == 20 + 10 + 20  # A twice + B once


def test_slot_capacity_picks_highest_value():
    a = cand("A", ("PG",), pts=30, reb=8, ast=8, tpm=3)
    b = cand("B", ("SG",), pts=20, reb=5, ast=4, tpm=2)
    c = cand("C", ("SF",), pts=4, reb=1, ast=1)
    res = best_response([[a, b, c]], FLEX2, target=PlayerLine())  # capacity 2
    assert set(res.started[0]) == {"A", "B"}  # C (lowest value) benched


def test_local_search_punts_to_flip_fg_pct():
    # A is efficient; B is a high-volume brick. Starting both tanks team FG%
    # below the target; benching B flips FG% and wins one more category.
    a = cand("A", ("PG",), pts=12, reb=5, ast=3, stl=1, blk=1, tpm=2, fgm=6, fga=10)
    b = cand("B", ("SG",), pts=4, reb=2, ast=1, tpm=1, fgm=2, fga=20)
    target = PlayerLine(pts=1, reb=1, ast=1, tpm=1, fgm=5, fga=10)  # FG% target = .50
    res = best_response([[a, b]], FLEX2, target=target)
    assert set(res.started[0]) == {"A"}            # B dropped
    assert res.line.fg_pct > target.fg_pct          # FG% now won
    # A alone wins the 6 counting cats + FG%, with FT% and TO as draws (0/0).
    assert res.result.wins == 7


def test_pluggable_objective_can_override_default():
    # A custom objective that maximizes raw points (ignoring the target) starts
    # the high scorer; the default catwins objective is the explicit default.
    a = cand("A", ("PG",), pts=40)
    b = cand("B", ("SG",), pts=5)
    pts_only = lambda line, target: line.pts
    res = best_response([[a, b]], [Slot("Flx")], target=PlayerLine(), objective=pts_only)
    assert res.started[0] == ["A"]
    # Default objective path still works unchanged.
    res_default = best_response([[a, b]], [Slot("Flx")], target=PlayerLine(),
                                objective=objective_catwins)
    assert res_default.started[0] == ["A"]
