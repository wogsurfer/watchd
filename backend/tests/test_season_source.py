"""A season's Watched box: its plays by source, and setting a source on them all."""

import pytest
from pydantic import ValidationError

from routers.history import SeasonSourceUpdate, SeasonWatchRequest


def test_only_missing_is_the_default():
    body = SeasonSourceUpdate(series_tmdb_id=1, season_number=2, watch_source="Netflix")
    assert body.only_missing is True


def test_a_source_can_be_cleared():
    assert SeasonSourceUpdate(series_tmdb_id=1, season_number=2, watch_source=None).watch_source is None


def test_an_unknown_source_is_refused():
    with pytest.raises(ValidationError):
        SeasonSourceUpdate(series_tmdb_id=1, season_number=2, watch_source="Betamax")


def test_marking_a_season_can_carry_a_source():
    assert SeasonWatchRequest(series_tmdb_id=1, season_number=2, watch_source="Blu-ray").watch_source == "Blu-ray"
    assert SeasonWatchRequest(series_tmdb_id=1, season_number=2).watch_source is None
