import os
import pathlib
from http.cookiejar import MozillaCookieJar, Cookie
from typing import Optional

import requests
from bs4 import BeautifulSoup
from cachetools import cached, TTLCache

DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def get_wallet_balance_from_parsed(parsed):
    raw_wallet_balance = parsed.find("div", {"class": "content-header__balance"}).find("p").find(
        "span").text.strip()
    wallet_balance = float(raw_wallet_balance.split("€")[0].replace(".", "").replace(",", "."))
    return wallet_balance


class WecityAPIClient:
    BASE_URL = "https://www.wecity.com/"

    def __init__(self):
        self.__session = requests.Session()

        cookies_file = os.environ["WC_COOKIES_PATH"]
        self._cookies_file = pathlib.Path(cookies_file)

        agent = (
            "Mozilla/5.0 (Linux; Android 11; moto g(20)) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/95.0.4638.74 Mobile Safari/537.36"
        )
        self.__session.headers["User-Agent"] = agent

        if not self._cookies_file.parent.exists():
            self._cookies_file.parent.mkdir(parents=True, exist_ok=True)
        self.__session.cookies = MozillaCookieJar(self._cookies_file)

    def __get_request(self, path: str, raw: bool = False) -> requests.Response:
        response = self.__session.request("GET", self.BASE_URL + path)

        if response.status_code == 200:
            if raw:
                return response.text
            return response.json()

        print("Error Status Code:", response.status_code)
        print("Error Response Body:", response.text)
        raise Exception("There was an error during the request")

    def login(self,
              username: str,
              password: str,
              avoid_new_login: bool = False,
              process_id: str = None,
              code: str = None) -> Optional[dict]:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._resume_web_session():
            print("Web session resumed")
            return None

        if code and process_id:
            if len(code) != 6:
                return {"success": False, "message": "Invalid code"}

            body = ""
            for pos in range(len(code)):
                body += f"sms_{pos + 1}={code[pos]}&"

            body += "sms_code=&boton-2factor="

            session_cookie = Cookie(0, name="PHPSESSID", value=process_id, port=None, port_specified=False,
                                    domain="www.wecity.com", domain_specified=True, domain_initial_dot=True,
                                    path="/", path_specified=True, secure=False, expires=None, discard=False,
                                    comment=None, comment_url=None, rest={})
            self.__session.cookies.set_cookie(session_cookie)
            response = self.__session.request("POST", self.BASE_URL + "/login", data=body, headers=headers)

            if response.status_code != 200:
                return {"success": False, "message": "Unknown error"}

            response_text = response.text
            if "Entrar en mi cuenta" in response_text:
                return {"success": False, "message": "Unknown error"}

            self.__session.cookies.save(ignore_discard=True, ignore_expires=True)
            return None

        elif not process_id and not code:
            if not avoid_new_login:
                body = f"usuario={username}&password={password}&boton-login="
                response = self.__session.request("POST", self.BASE_URL + "/login", data=body, headers=headers)

                if response.status_code != 200:
                    return {"success": False, "message": "Unknown error"}

                response_text = response.text
                if "Tu usuario o contraseña no son correctos" in response_text:
                    return {"success": False, "message": "Invalid credentials"}

                if "Doble Factor de Autenticación" in response_text:
                    process_id = requests.utils.dict_from_cookiejar(self.__session.cookies)["PHPSESSID"]
                    return {"success": True, "processId": process_id}

            else:
                return {"success": False}

        else:
            raise ValueError("Invalid params")

        return {"success": False, "message": "Unknown error"}

    def _resume_web_session(self):
        if self._cookies_file.exists():
            self.__session.cookies.load(ignore_discard=True, ignore_expires=True)
            try:
                if self.get_user():
                    return True
                else:
                    return False
            except requests.exceptions.HTTPError:
                return False
        return False

    def get_user(self):
        return self.__get_request("/ajax/ajax.php?option=checkuser")["data"]

    @cached(cache=TTLCache(maxsize=1, ttl=600))
    def get_wallet_and_transactions(self):
        html_body = self.__get_request("/mi-cuenta/mi-wallet", raw=True)
        parsed = BeautifulSoup(html_body, "html.parser")

        wallet_balance = get_wallet_balance_from_parsed(parsed)

        movements_list_div = parsed.find("div", {"class": "wallet-movimientos__listado"})
        movements_list = movements_list_div.find("ul").find_all("li")

        txs = []
        for movement in movements_list:
            date = movement.find("p", {"class": "wallet-movimientos__fecha"}).text.strip()
            details_div = movement.find("div", {"class": "wallet-movimientos__movimiento"})
            category = details_div.find("p").text.strip()
            name = details_div.find("p").find("span").text.strip()
            raw_amount = details_div.find("p", {"class": "movimiento__importe"}).text.strip()
            amount = float(raw_amount.split("€")[0].replace(".", "").replace(",", "."))

            txs.append(
                {
                    "date": date,
                    "category": category,
                    "name": name,
                    "amount": amount
                }
            )

        return wallet_balance, txs

    def get_wallet_and_investments_overview(self):
        html_body = self.__get_request("/mi-cuenta/my-city/", raw=True)
        parsed = BeautifulSoup(html_body, "html.parser")

        wallet_balance = get_wallet_balance_from_parsed(parsed)

        active_investments_table = parsed.find("table", {"id": "option1"})
        active_investments_rows = active_investments_table.find("tbody").find_all("tr")

        active_investments = []
        for row in active_investments_rows:
            columns = row.find_all("td")
            a_element = columns[0].find("a")
            name = a_element["title"].strip()
            project_id = int(a_element["href"].strip().split("/")[-1])
            amount = columns[1].text.strip()
            active_investments.append({
                "name": name,
                "amount": float(amount.split("€")[0].replace(".", "").replace(",", ".")),
                "id": project_id
            })

        return wallet_balance, active_investments

    @cached(cache=TTLCache(maxsize=1, ttl=600))
    def get_all_projects(self):
        return self.__get_request("/ajax/ajax.php?option=opportunities")["data"]

    @cached(cache=TTLCache(maxsize=50, ttl=600))
    def get_investment_details(self, project_id: int):
        html_body = self.__get_request(f"/mi-cuenta/my-city/{project_id}", raw=True)
        parsed = BeautifulSoup(html_body, "html.parser")

        info_divs = parsed.find_all("div", {"class": "ficha-oportunidad__status"})
        raw_details = {}
        for div in info_divs:
            prop = div.find("p").text.strip()
            value = div.find("span").text.strip()
            raw_details[prop] = value

        return {
            "interestRate": float(raw_details["Tipo de interés anual"].split("%")[0].replace(",", ".")),
            "months": int(raw_details["Plazo estimado"].split(" ")[0]),
            "potentialExtension": int(raw_details["Posible prórroga"].split(" ")[0]),
            "type": raw_details["Tipo de inmueble"],
            "businessType": raw_details["Tipo de inversión"],
        }
