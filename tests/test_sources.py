import pytest

from max_pf.platforms.fantrax import FantraxStatSource
from max_pf.sources import StatSource


class FakeSource(StatSource):
    def expected_candidates(self, team_id, period):
        return [[]]


def test_default_hindsight_is_unsupported():
    with pytest.raises(NotImplementedError):
        FakeSource().hindsight_candidates("t", 1)


def test_fantrax_source_delegates_expected_and_rejects_hindsight():
    class DummyPlatform:
        def expected_period_candidates(self, team_id, period):
            return [["sentinel"]]

    src = FantraxStatSource(DummyPlatform())
    assert src.expected_candidates("t", 1) == [["sentinel"]]
    with pytest.raises(NotImplementedError):
        src.hindsight_candidates("t", 1)
