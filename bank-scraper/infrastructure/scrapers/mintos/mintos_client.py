from typing import Union, Optional

import requests
from cachetools import TTLCache, cached


class MintosAPIClient:
    BASE_URL = "https://www.mintos.com"
    BASE_API_URL = f"{BASE_URL}/webapp/api"
    USER_PATH = f"{BASE_API_URL}/en/webapp-api/user"

    def __init__(self):
        self.__session = requests.Session()

    def __execute_request(
            self,
            path: str,
            method: str,
            body: Optional[dict] = None,
            params: Optional[dict] = None,
    ) -> Union[dict, str]:
        response = self.__session.request(
            method, self.BASE_API_URL + path, json=body, params=params
        )

        if response.ok:
            return response.json()

        print("Error Status Code:", response.status_code)
        print("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def __get_request(
            self, path: str, params: dict = None
    ) -> Union[dict, str]:
        return self.__execute_request(path, "GET", params=params)

    def __post_request(
            self, path: str, body: dict
    ) -> Union[dict, requests.Response]:
        return self.__execute_request(path, "POST", body=body)

    async def login(self, username: str, password: str) -> dict:
        from infrastructure.scrapers.mintos.mintos_selenium_login_client import login
        return await login(self.__session, username, password)

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_user(self) -> dict:
        return self.__get_request("/en/webapp-api/user")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_overview(self, wallet_currency_id) -> dict:
        return self.__get_request(f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_net_annual_returns(self, wallet_currency_id) -> dict:
        return self.__get_request(
            f"/en/webapp-api/user/overview-net-annual-returns?currencyIsoCode={wallet_currency_id}")

    @cached(cache=TTLCache(maxsize=1, ttl=120))
    def get_portfolio(self, wallet_currency_id) -> dict:
        return self.__get_request(f"/marketplace-api/v1/user/overview/currency/{wallet_currency_id}/portfolio-data")
