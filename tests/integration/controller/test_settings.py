import pytest

SIGNUP_URL = "/api/v1/signup"
LOGOUT_URL = "/api/v1/logout"
SETTINGS_URL = "/api/v1/settings"

USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup_and_stay_logged_in(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _build_settings(
    currency="EUR",
    weight_unit="g",
    auto_refresh_mode="NO_2FA",
    stablecoins=None,
    hide_unknown_tokens=False,
):
    return {
        "lastUpdate": "2025-01-01T00:00:00+00:00",
        "version": 6,
        "general": {
            "defaultCurrency": currency,
            "defaultCommodityWeightUnit": weight_unit,
        },
        "data": {
            "autoRefresh": {
                "mode": auto_refresh_mode,
                "max_outdated": "TWELVE_HOURS",
                "entities": [],
            },
        },
        "export": {},
        "importing": {},
        "assets": {
            "crypto": {
                "stablecoins": stablecoins or ["USDT", "USDC"],
                "hideUnknownTokens": hide_unknown_tokens,
            },
        },
    }


class TestGetSettings:
    @pytest.mark.asyncio
    async def test_returns_200_with_default_settings(self, client):
        await _signup_and_stay_logged_in(client)
        response = await client.get(SETTINGS_URL)
        assert response.status_code == 200
        body = await response.get_json()
        assert body["general"]["defaultCurrency"] == "EUR"
        assert body["version"] == 6
        assert "lastUpdate" in body

    @pytest.mark.asyncio
    async def test_returns_default_crypto_stablecoins(self, client):
        await _signup_and_stay_logged_in(client)
        response = await client.get(SETTINGS_URL)
        body = await response.get_json()
        stablecoins = body["assets"]["crypto"]["stablecoins"]
        assert "USDT" in stablecoins
        assert "USDC" in stablecoins

    @pytest.mark.asyncio
    async def test_returns_401_when_not_logged_in(self, client):
        response = await client.get(SETTINGS_URL)
        assert response.status_code == 401


class TestUpdateSettings:
    @pytest.mark.asyncio
    async def test_update_and_get_reflects_changes(self, client):
        await _signup_and_stay_logged_in(client)
        new_settings = _build_settings(currency="USD")
        update_resp = await client.post(SETTINGS_URL, json=new_settings)
        assert update_resp.status_code == 204

        get_resp = await client.get(SETTINGS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()
        assert body["general"]["defaultCurrency"] == "USD"

    @pytest.mark.asyncio
    async def test_update_currency_persists(self, client):
        await _signup_and_stay_logged_in(client)
        new_settings = _build_settings(currency="GBP")
        await client.post(SETTINGS_URL, json=new_settings)

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["general"]["defaultCurrency"] == "GBP"

    @pytest.mark.asyncio
    async def test_update_auto_refresh_mode(self, client):
        await _signup_and_stay_logged_in(client)
        new_settings = _build_settings(auto_refresh_mode="OFF")
        await client.post(SETTINGS_URL, json=new_settings)

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["data"]["autoRefresh"]["mode"] == "OFF"

    @pytest.mark.asyncio
    async def test_update_crypto_stablecoins(self, client):
        await _signup_and_stay_logged_in(client)
        new_settings = _build_settings(stablecoins=["DAI", "BUSD"])
        await client.post(SETTINGS_URL, json=new_settings)

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["assets"]["crypto"]["stablecoins"] == ["DAI", "BUSD"]

    @pytest.mark.asyncio
    async def test_update_hide_unknown_tokens(self, client):
        await _signup_and_stay_logged_in(client)
        new_settings = _build_settings(hide_unknown_tokens=True)
        await client.post(SETTINGS_URL, json=new_settings)

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["assets"]["crypto"]["hideUnknownTokens"] is True

    @pytest.mark.asyncio
    async def test_returns_400_on_invalid_body(self, client):
        await _signup_and_stay_logged_in(client)
        response = await client.post(SETTINGS_URL, json={"invalid": "data"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_401_when_not_logged_in(self, client):
        response = await client.post(SETTINGS_URL, json=_build_settings())
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_last_update_is_refreshed_on_save(self, client):
        await _signup_and_stay_logged_in(client)

        get_resp = await client.get(SETTINGS_URL)
        original = await get_resp.get_json()
        original_timestamp = original["lastUpdate"]

        new_settings = _build_settings(currency="JPY")
        await client.post(SETTINGS_URL, json=new_settings)

        get_resp = await client.get(SETTINGS_URL)
        updated = await get_resp.get_json()
        assert updated["lastUpdate"] != original_timestamp


class TestSettingsLifecycle:
    @pytest.mark.asyncio
    async def test_settings_persist_across_logout_login(self, client):
        await _signup_and_stay_logged_in(client)

        new_settings = _build_settings(currency="CHF")
        await client.post(SETTINGS_URL, json=new_settings)

        await client.post(LOGOUT_URL)
        await client.post(
            "/api/v1/login",
            json={"username": USERNAME, "password": PASSWORD},
        )

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["general"]["defaultCurrency"] == "CHF"

    @pytest.mark.asyncio
    async def test_multiple_updates_last_write_wins(self, client):
        await _signup_and_stay_logged_in(client)

        await client.post(SETTINGS_URL, json=_build_settings(currency="USD"))
        await client.post(SETTINGS_URL, json=_build_settings(currency="GBP"))
        await client.post(SETTINGS_URL, json=_build_settings(currency="JPY"))

        body = await (await client.get(SETTINGS_URL)).get_json()
        assert body["general"]["defaultCurrency"] == "JPY"
