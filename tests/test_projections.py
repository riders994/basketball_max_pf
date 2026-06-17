from max_pf.platforms.fantrax import (
    DAILY_STAT_SCIP,
    DEFAULT_NBA_SLOTS,
    PERGAME_STAT_SCIP,
    decode_roster_stats,
    players_with_game,
    slot_eligibility,
)
from max_pf.projections import project_period_line


def test_slot_eligibility_parsing():
    assert slot_eligibility("C") == frozenset({"C"})
    assert slot_eligibility("G") == frozenset({"PG", "SG", "G"})
    assert slot_eligibility("F") == frozenset({"SF", "PF", "F"})
    assert slot_eligibility("Flx") == frozenset()  # flex accepts anyone
    assert slot_eligibility("G/C") == frozenset({"PG", "SG", "G", "C"})
    assert slot_eligibility("SG/SF") == frozenset({"SG", "SF"})


def test_default_nba_slots_layout():
    assert len(DEFAULT_NBA_SLOTS) == 9
    assert sum(1 for s in DEFAULT_NBA_SLOTS if not s.eligible) == 2  # two flex
    assert [s.name for s in DEFAULT_NBA_SLOTS].count("C") == 1


def _header_cell(scip: int, name: str) -> dict:
    return {"scipId": f"3010#{scip}#-1", "key": f"3010#{scip}#-1", "name": name}


# Mirrors the real STATS table shape (league wserh14rmbbpqtcg, Bogdan Bogdanovic).
STATS_TABLE = {
    "header": {"cells": [
        {"key": "age", "name": "Age"},
        {"key": "opponent", "name": "Opponent"},
        _header_cell(1350, "Games Played"),
        _header_cell(1520, "Field Goal %"),
        _header_cell(1620, "Three Pointers Made Per Game"),
        _header_cell(1550, "Free Throw %"),
        _header_cell(1590, "Points Per Game"),
        _header_cell(1600, "Rebounds Per Game"),
        _header_cell(1470, "Assists Per Game"),
        _header_cell(1610, "Steals Per Game"),
        _header_cell(1480, "Blocks Per Game"),
        _header_cell(1650, "Turnovers Per Game"),
    ]},
    "rows": [
        {
            "scorer": {"scorerId": "bog01", "name": "Bogdan Bogdanovic", "posShortNames": "SG,G,SF,F"},
            "cells": [
                {"content": "33"}, {"content": ""}, {"content": "16"}, {"content": ".376"},
                {"content": "1.5"}, {"content": ".842"}, {"content": "8.0"}, {"content": "2.9"},
                {"content": "2.7"}, {"content": "0.5"}, {"content": "0.1"}, {"content": "1.2"},
            ],
        },
        {"posId": "307", "cells": [{"content": ""}]},  # empty slot row (no scorer) -> skipped
    ],
}


def test_daily_and_pergame_scip_maps_differ_for_counting_cats():
    # FG%/FT% share ids; counting cats use different ids across the two views.
    assert DAILY_STAT_SCIP[1520] == PERGAME_STAT_SCIP[1520] == "fg_pct"
    assert 1390 in DAILY_STAT_SCIP and 1390 not in PERGAME_STAT_SCIP  # daily PTS id
    assert 1590 in PERGAME_STAT_SCIP and 1590 not in DAILY_STAT_SCIP  # per-game PTS id


def test_decode_roster_stats_parses_per_game_line():
    rates = decode_roster_stats(STATS_TABLE)
    assert set(rates) == {"bog01"}  # the empty-slot row is skipped
    line = rates["bog01"]
    assert line.pts == 8.0 and line.reb == 2.9 and line.ast == 2.7
    assert line.tpm == 1.5 and line.stl == 0.5 and line.blk == 0.1 and line.to == 1.2
    # FG%/FT% recovered from estimated makes/attempts match the reported rates.
    assert abs(line.fg_pct - 0.376) < 1e-6
    assert abs(line.ft_pct - 0.842) < 1e-6


def test_players_with_game_reads_opponent_column():
    # Opponent column is index 1 (key "opponent"); non-empty content = has a game.
    table = {
        "header": {"cells": [{"key": "age"}, {"key": "opponent", "shortName": "Opp"},
                             _header_cell(1590, "Points Per Game")]},
        "rows": [
            {"scorer": {"scorerId": "plays"}, "cells": [{"content": "30"},
                {"content": "@NO 108 F"}, {"content": "20.0"}]},
            {"scorer": {"scorerId": "off"}, "cells": [{"content": "25"},
                {"content": ""}, {"content": "12.0"}]},
            {"posId": "307", "cells": [{"content": ""}, {"content": ""}, {"content": ""}]},
        ],
    }
    assert players_with_game(table) == {"plays"}


def test_project_period_line_scales_linearly_and_preserves_percentages():
    rates = decode_roster_stats(STATS_TABLE)["bog01"]
    proj = project_period_line(rates, games_in_period=4)
    assert proj.pts == 8.0 * 4
    assert proj.reb == 2.9 * 4
    # Percentages are scale-invariant.
    assert abs(proj.fg_pct - rates.fg_pct) < 1e-9
    assert abs(proj.ft_pct - rates.ft_pct) < 1e-9
