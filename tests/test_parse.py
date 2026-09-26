"""Unit tests for the pure parsing / tide detection helpers."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import FIXTURES

from custom_components.met_tides.sensor import (
    find_next_tides,
    interpolate_current_height,
    parse_tides,
)
from tide_helpers import M2_PERIOD, make_forecast


def _points(heights, start=datetime(2026, 1, 1, tzinfo=UTC), step=10):
    return [{"datetime": start + timedelta(minutes=i * step), "height": h} for i, h in enumerate(heights)]


def _assert_near(actual: datetime, expected: datetime, tol=timedelta(minutes=10)):
    assert abs(actual - expected) <= tol, f"{actual} not within {tol} of {expected}"


class TestParseTides:
    def test_documented_example_output(self):
        """Example response from the API documentation (Bergen)."""
        text = (FIXTURES / "bergen.txt").read_text()
        result = parse_tides(text, now=datetime(2024, 10, 24, 12, 5, tzinfo=UTC))
        points = result["tide_points"]
        assert len(points) == 16
        assert points[0] == {"datetime": datetime(2024, 10, 24, 12, 0, tzinfo=UTC), "height": 0.26}
        assert points[-1] == {"datetime": datetime(2024, 10, 24, 14, 30, tzinfo=UTC), "height": 0.54}
        # TOTAL, not SURGE/TIDE/percentiles, and midway between 0.26 and 0.28
        assert result["current_height"] == pytest.approx(0.27)
        # A rising-tide excerpt contains no turning points
        assert result["next_high"]["datetime"] is None
        assert result["next_low"]["datetime"] is None

    def test_skips_header_and_malformed_lines(self, forecast_start):
        text = "\n".join(
            [
                "MET forecast. Water level for OSLO",
                " AAR MND DAG TIM MIN SURGE TIDE TOTAL 0p 25p 50p 75p 100p",
                " 2026 1 1 0 0 0.0 0.1 0.10 0 0 0 0 0",
                " 2026 1 1 0 10 0.0 0.1 not-a-number 0 0 0 0 0",
                " 2026 13 1 0 20 0.0 0.1 0.30 0 0 0 0 0",  # invalid month
                " 2026 1 1",  # truncated
                "",
                " 2026 1 1 0 30 0.0 0.1 0.40 0 0 0 0 0",
            ]
        )
        result = parse_tides(text, now=forecast_start)
        assert [p["height"] for p in result["tide_points"]] == [0.10, 0.40]

    def test_uses_total_column(self, forecast_start):
        line = " 2026 1 1 0 0 0.25 1.00 1.25 9 9 9 9 9"
        result = parse_tides(line, now=forecast_start)
        assert result["tide_points"][0]["height"] == 1.25

    def test_timestamps_are_utc(self, forecast_start):
        result = parse_tides(" 2026 1 1 6 30 0 0 0.5 0 0 0 0 0", now=forecast_start)
        assert result["tide_points"][0]["datetime"] == datetime(2026, 1, 1, 6, 30, tzinfo=UTC)

    def test_empty_input(self, forecast_start):
        result = parse_tides("", now=forecast_start)
        assert result["tide_points"] == []
        assert result["current_height"] is None
        assert result["next_high"] == {"datetime": None, "height": None}
        assert result["next_low"] == {"datetime": None, "height": None}

    def test_unsorted_input_is_sorted(self, forecast_start):
        text = "\n".join(
            [
                " 2026 1 1 0 20 0 0 0.3 0 0 0 0 0",
                " 2026 1 1 0 0 0 0 0.1 0 0 0 0 0",
                " 2026 1 1 0 10 0 0 0.2 0 0 0 0 0",
            ]
        )
        result = parse_tides(text, now=forecast_start)
        times = [p["datetime"] for p in result["tide_points"]]
        assert times == sorted(times)

    def test_next_tides_from_sinusoid(self, forecast_start, forecast_text):
        result = parse_tides(forecast_text, now=forecast_start)
        # sin() starting at 0 going up: high at T/4, low at 3T/4
        _assert_near(result["next_high"]["datetime"], forecast_start + M2_PERIOD / 4)
        _assert_near(result["next_low"]["datetime"], forecast_start + 3 * M2_PERIOD / 4)
        assert result["next_high"]["height"] == pytest.approx(1.0, abs=0.01)
        assert result["next_low"]["height"] == pytest.approx(-1.0, abs=0.01)

    def test_next_low_can_precede_next_high(self, forecast_start, forecast_text):
        # Just after the first high the next event is a low, then a high a cycle later
        now = forecast_start + M2_PERIOD / 4 + timedelta(minutes=30)
        result = parse_tides(forecast_text, now=now)
        assert result["next_low"]["datetime"] < result["next_high"]["datetime"]
        _assert_near(result["next_low"]["datetime"], forecast_start + 3 * M2_PERIOD / 4)
        _assert_near(result["next_high"]["datetime"], forecast_start + 5 * M2_PERIOD / 4)

    @pytest.mark.parametrize("hours_in", [0, 1, 5, 11, 17, 23, 30, 40])
    def test_next_tides_always_in_future_and_within_one_cycle(self, forecast_start, forecast_text, hours_in):
        now = forecast_start + timedelta(hours=hours_in)
        result = parse_tides(forecast_text, now=now)
        for key in ("next_high", "next_low"):
            event = result[key]["datetime"]
            if event is None:  # near the end of the forecast window
                continue
            assert now < event <= now + M2_PERIOD + timedelta(minutes=10)

    def test_no_future_events_past_forecast_end(self, forecast_start, forecast_text):
        result = parse_tides(forecast_text, now=forecast_start + timedelta(days=5))
        assert result["next_high"]["datetime"] is None
        assert result["next_low"]["datetime"] is None


class TestFindNextTides:
    NOW = datetime(2025, 12, 31, tzinfo=UTC)

    def test_too_few_points(self):
        assert find_next_tides(_points([0, 1, 2, 1]), self.NOW) == (None, None)

    def test_monotonic_series_has_no_events(self):
        assert find_next_tides(_points([0, 1, 2, 3, 4, 5, 6]), self.NOW) == (None, None)

    def test_two_sample_plateau_yields_single_event(self):
        points = _points([0.0, 0.5, 1.0, 1.0, 0.5, 0.0, -0.5, -1.0, -0.5, 0.0])
        high, low = find_next_tides(points, self.NOW)
        assert high["datetime"] == points[2]["datetime"]
        assert low["datetime"] == points[7]["datetime"]

    def test_three_sample_plateau_yields_middle(self):
        points = _points([0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0])
        high, _ = find_next_tides(points, self.NOW)
        assert high["datetime"] == points[3]["datetime"]

    def test_event_exactly_at_now_is_not_next(self):
        points = _points([0.0, 0.5, 1.0, 0.5, 0.0, 0.5, 1.0, 0.5, 0.0])
        high, _ = find_next_tides(points, points[2]["datetime"])
        assert high["datetime"] == points[6]["datetime"]

    def test_constant_series_has_no_events(self):
        assert find_next_tides(_points([1.0] * 20), self.NOW) == (None, None)


class TestInterpolateCurrentHeight:
    def test_empty(self):
        assert interpolate_current_height([], datetime.now(UTC)) is None

    def test_linear_midpoint(self):
        points = _points([0.0, 1.0])
        now = points[0]["datetime"] + timedelta(minutes=5)
        assert interpolate_current_height(points, now) == pytest.approx(0.5)

    def test_exact_sample(self):
        points = _points([0.0, 1.0, 2.0])
        assert interpolate_current_height(points, points[1]["datetime"]) == pytest.approx(1.0)

    def test_before_forecast_uses_first_point(self):
        points = _points([0.3, 1.0])
        assert interpolate_current_height(points, points[0]["datetime"] - timedelta(hours=1)) == 0.3

    def test_after_forecast_uses_last_point(self):
        points = _points([0.3, 0.7])
        assert interpolate_current_height(points, points[-1]["datetime"] + timedelta(hours=1)) == 0.7

    def test_duplicate_timestamps_do_not_divide_by_zero(self):
        points = _points([0.0, 1.0])
        points.insert(1, dict(points[0]))
        now = points[0]["datetime"] + timedelta(minutes=5)
        assert interpolate_current_height(points, now) == pytest.approx(0.5)

    def test_matches_sinusoid(self, forecast_start):
        text = make_forecast(forecast_start, hours=24)
        points = parse_tides(text, now=forecast_start)["tide_points"]
        now = forecast_start + M2_PERIOD / 4
        assert interpolate_current_height(points, now) == pytest.approx(1.0, abs=0.01)
