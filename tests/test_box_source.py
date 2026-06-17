from datetime import date

from max_pf.box_bref import BoxScoreStatSource, PlayerBox
from max_pf.models import PlayerLine


class FakePlatform:
    """Minimal platform surface BoxScoreStatSource needs."""

    def matchup_period_days(self, period):
        return [10, 11]  # two daily periods

    def scoring_dates(self):
        return {10: date(2025, 11, 10), 11: date(2025, 11, 11)}

    def roster_membership(self, team_id, daily_period):
        return {
            "s_tatum": ("Jayson Tatum", ("SF", "PF", "F")),
            "s_claxton": ("Nicolas Claxton", ("C",)),   # alias -> "nic claxton"
            "s_ghost": ("Never Plays", ("PG",)),
        }


class FakeClient:
    def __init__(self):
        self._days = {
            date(2025, 11, 10): {
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS",
                                       PlayerLine(pts=30, reb=8, fgm=10, fga=20)),
                "claxtni01": PlayerBox("claxtni01", "Nic Claxton", "BRK",
                                       PlayerLine(pts=12, reb=11, blk=3, fgm=6, fga=8)),
            },
            date(2025, 11, 11): {
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS",
                                       PlayerLine(pts=25, reb=6, fgm=9, fga=19)),
            },
        }

    def day_lines(self, on):
        return self._days[on]


class ExpectedFakePlatform:
    """Platform surface for the A-expected (season-to-date) path."""

    def matchup_period_days(self, period):
        return [20, 21]  # the period's two daily periods

    def scoring_dates(self):
        return {  # two prior dates (accumulation) + the two period dates
            18: date(2025, 11, 8), 19: date(2025, 11, 9),
            20: date(2025, 11, 10), 21: date(2025, 11, 11),
        }

    def roster_membership(self, team_id, daily_period):
        return {
            "s_tatum": ("Jayson Tatum", ("SF", "PF", "F")),
            "s_claxton": ("Nicolas Claxton", ("C",)),   # alias -> "nic claxton"
            "s_ghost": ("Never Plays", ("PG",)),
        }


class ExpectedFakeClient:
    def __init__(self):
        self._days = {
            # --- season-to-date (before the period) ---
            date(2025, 11, 8): {
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS",
                                       PlayerLine(pts=20, fgm=8, fga=16)),
                "claxtni01": PlayerBox("claxtni01", "Nic Claxton", "BRK",
                                       PlayerLine(pts=10, reb=10, fgm=5, fga=5)),
            },
            date(2025, 11, 9): {
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS",
                                       PlayerLine(pts=30, fgm=12, fga=24)),
            },
            # --- the period: who is scheduled (teams that played) ---
            date(2025, 11, 10): {  # BOS and BRK both play
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS", PlayerLine()),
                "claxtni01": PlayerBox("claxtni01", "Nic Claxton", "BRK", PlayerLine()),
            },
            date(2025, 11, 11): {  # only BOS plays
                "tatumja01": PlayerBox("tatumja01", "Jayson Tatum", "BOS", PlayerLine()),
            },
        }

    def day_lines(self, on):
        return self._days[on]


def test_expected_candidates_use_season_to_date_rates_on_scheduled_days():
    src = BoxScoreStatSource(ExpectedFakePlatform(), ExpectedFakeClient())
    per_day = src.expected_candidates("team", period=7)
    assert len(per_day) == 2

    day1 = {c.player_id: c for c in per_day[0]}
    # Both teams play day 1: Tatum (2 games -> 25 ppg, .500 FG) + Claxton (alias).
    assert set(day1) == {"s_tatum", "s_claxton"}
    assert day1["s_tatum"].line.pts == 25            # (20+30)/2, a per-game rate
    assert day1["s_tatum"].line.fg_pct == 0.5        # (8+12)/(16+24), exact, no estimator
    assert day1["s_claxton"].line.pts == 10          # single game so far

    day2 = {c.player_id: c for c in per_day[1]}
    assert set(day2) == {"s_tatum"}                  # only BOS plays day 2
    # The ghost never played before the period -> no rate -> never projected.
    assert all("s_ghost" not in {c.player_id for c in day} for day in per_day)


def test_hindsight_candidates_use_realized_lines_and_alias():
    src = BoxScoreStatSource(FakePlatform(), FakeClient())
    per_day = src.hindsight_candidates("team", period=4)
    assert len(per_day) == 2

    day1 = {c.player_id: c for c in per_day[0]}
    # Tatum + Claxton (matched via alias) play day 1; the ghost never appears.
    assert set(day1) == {"s_tatum", "s_claxton"}
    assert day1["s_tatum"].line.pts == 30           # realized line, not a projection
    assert day1["s_claxton"].positions == ("C",)

    day2 = {c.player_id: c for c in per_day[1]}
    assert set(day2) == {"s_tatum"}                  # only Tatum played day 2
    assert day2["s_tatum"].line.pts == 25
