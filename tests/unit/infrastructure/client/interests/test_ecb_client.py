from domain.dezimal import Dezimal
from domain.euribor import EuriborHistory
from infrastructure.client.interests.ecb_client import ECBClient


def _ecb_response(observations: dict, time_periods: list[dict]) -> dict:
    return {
        "dataSets": [
            {
                "series": {
                    "0:0:0:0:0:0:0": {
                        "observations": observations,
                    }
                }
            }
        ],
        "structure": {
            "dimensions": {
                "observation": [
                    {
                        "values": time_periods,
                    }
                ]
            }
        },
    }


class TestECBClientParsing:
    def test_parses_valid_response(self):
        observations = {
            "0": [2.1434],
            "1": [2.0806],
            "2": [2.0809],
        }
        time_periods = [
            {"id": "2025-04"},
            {"id": "2025-05"},
            {"id": "2025-06"},
        ]
        data = _ecb_response(observations, time_periods)

        client = ECBClient()
        result = client._parse_response(data)

        assert isinstance(result, EuriborHistory)
        assert len(result.rates) == 3
        assert result.rates[0].period == "2025-06"
        assert result.rates[0].rate == Dezimal("2.0809")
        assert result.rates[1].period == "2025-05"
        assert result.rates[2].period == "2025-04"
        assert result.rates[2].rate == Dezimal("2.1434")

    def test_returns_rates_sorted_newest_first(self):
        observations = {
            "0": [1.0],
            "1": [2.0],
            "2": [3.0],
        }
        time_periods = [
            {"id": "2025-01"},
            {"id": "2025-02"},
            {"id": "2025-03"},
        ]
        data = _ecb_response(observations, time_periods)

        client = ECBClient()
        result = client._parse_response(data)

        periods = [r.period for r in result.rates]
        assert periods == ["2025-03", "2025-02", "2025-01"]

    def test_returns_empty_history_on_missing_datasets(self):
        client = ECBClient()
        result = client._parse_response({})
        assert result.rates == []

    def test_returns_empty_history_on_missing_series(self):
        client = ECBClient()
        result = client._parse_response({"dataSets": [{"series": {}}]})
        assert result.rates == []

    def test_skips_observations_beyond_time_periods(self):
        observations = {
            "0": [2.14],
            "1": [2.08],
            "5": [9.99],
        }
        time_periods = [
            {"id": "2025-04"},
            {"id": "2025-05"},
        ]
        data = _ecb_response(observations, time_periods)

        client = ECBClient()
        result = client._parse_response(data)

        assert len(result.rates) == 2
        periods = [r.period for r in result.rates]
        assert "2025-04" in periods
        assert "2025-05" in periods

    def test_skips_empty_observation_values(self):
        observations = {
            "0": [2.14],
            "1": [],
        }
        time_periods = [
            {"id": "2025-04"},
            {"id": "2025-05"},
        ]
        data = _ecb_response(observations, time_periods)

        client = ECBClient()
        result = client._parse_response(data)

        assert len(result.rates) == 1
        assert result.rates[0].period == "2025-04"

    def test_handles_twelve_month_response(self):
        observations = {str(i): [2.0 + i * 0.01] for i in range(12)}
        time_periods = [{"id": f"2025-{m:02d}"} for m in range(1, 13)]
        data = _ecb_response(observations, time_periods)

        client = ECBClient()
        result = client._parse_response(data)

        assert len(result.rates) == 12
        assert result.rates[0].period == "2025-12"
        assert result.rates[-1].period == "2025-01"
