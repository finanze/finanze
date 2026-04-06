import logging

from aiocache import cached
from aiocache.serializers import PickleSerializer

from application.ports.euribor_provider import EuriborProvider
from domain.dezimal import Dezimal
from domain.euribor import EuriborHistory, EuriborRate
from infrastructure.client.http.http_session import get_http_session

ECB_BASE_URL = "https://data-api.ecb.europa.eu/service/data/FM"
EURIBOR_1Y_SERIES = "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"
OBSERVATIONS_COUNT = 14


class ECBClient(EuriborProvider):
    CACHE_TTL = 24 * 60 * 60
    TIMEOUT = 15

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = get_http_session()

    @cached(
        ttl=CACHE_TTL,
        key_builder=lambda f, self: "ecb_euribor_1y",
        serializer=PickleSerializer(),
    )
    async def get_yearly_euribor_rates(self) -> EuriborHistory:
        url = f"{ECB_BASE_URL}/{EURIBOR_1Y_SERIES}"
        params = {
            "lastNObservations": str(OBSERVATIONS_COUNT),
            "detail": "dataonly",
            "format": "jsondata",
        }

        response = await self._session.get(url, params=params, timeout=self.TIMEOUT)
        if not response.ok:
            body = await response.text()
            self._log.error(f"ECB API error ({response.status}): {body}")
            response.raise_for_status()
            return EuriborHistory()

        data = await response.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict) -> EuriborHistory:
        try:
            observations = data["dataSets"][0]["series"]["0:0:0:0:0:0:0"][
                "observations"
            ]
            time_periods = data["structure"]["dimensions"]["observation"][0]["values"]
        except (KeyError, IndexError, TypeError) as e:
            self._log.error(f"Unexpected ECB response structure: {e}")
            return EuriborHistory()

        rates: list[EuriborRate] = []
        for idx_str, values in observations.items():
            idx = int(idx_str)
            if idx >= len(time_periods) or not values:
                continue
            period = time_periods[idx]["id"]
            rate_value = values[0]
            rates.append(EuriborRate(period=period, rate=Dezimal(rate_value)))

        rates.sort(key=lambda r: r.period, reverse=True)
        return EuriborHistory(rates=rates)
