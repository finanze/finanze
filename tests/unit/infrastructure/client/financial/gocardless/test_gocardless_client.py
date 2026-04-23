import time
from unittest.mock import MagicMock

import pytest

from infrastructure.client.financial.gocardless.gocardless_client import (
    GoCardlessClient,
)

CACHED_METHODS = [
    "list_institutions",
    "get_institution",
    "list_agreements",
    "get_agreement",
    "get_requisitions",
    "get_account_balances",
    "get_account_metadata",
    "get_account_details",
    "get_account_transactions",
]


@pytest.fixture(autouse=True)
def clear_gocardless_caches():
    for method_name in CACHED_METHODS:
        getattr(GoCardlessClient, method_name).cache.clear()
    yield
    for method_name in CACHED_METHODS:
        getattr(GoCardlessClient, method_name).cache.clear()


def _make_client():
    client = GoCardlessClient(port=8080)

    institution_api = MagicMock()
    institution_api.get_institutions = MagicMock(
        return_value=[{"id": "bank-1", "name": "Bank 1"}]
    )

    account_resource = MagicMock()
    account_resource.get_details = MagicMock(return_value={"account": "acc-1"})

    nordigen_client = MagicMock()
    nordigen_client.institution = institution_api
    nordigen_client.account_api = MagicMock(return_value=account_resource)

    client._client = nordigen_client
    client._credentials = {"secret_id": "secret-id", "secret_key": "secret-key"}
    client._access_expires_at = time.time() + 3600
    client._refresh_expires_at = time.time() + 7200

    return client, institution_api, nordigen_client, account_resource


class TestListInstitutionsCache:
    def test_reuses_cached_result_for_same_instance_and_arguments(self):
        client, institution_api, _, _ = _make_client()

        first = client.list_institutions("ES")
        second = client.list_institutions("ES")

        assert first == second
        institution_api.get_institutions.assert_called_once_with("ES")

    def test_different_arguments_bypass_cache(self):
        client, institution_api, _, _ = _make_client()

        client.list_institutions("ES")
        client.list_institutions("IT")

        assert institution_api.get_institutions.call_count == 2

    def test_cache_key_is_scoped_per_instance(self):
        client_a, institution_api_a, _, _ = _make_client()
        client_b, institution_api_b, _, _ = _make_client()

        result_a = client_a.list_institutions("ES")
        result_b = client_b.list_institutions("ES")

        assert result_a == result_b
        institution_api_a.get_institutions.assert_called_once_with("ES")
        institution_api_b.get_institutions.assert_called_once_with("ES")


class TestAccountDetailsCache:
    def test_reuses_cached_account_details_for_same_account(self):
        client, _, nordigen_client, account_resource = _make_client()

        first = client.get_account_details("acc-1")
        second = client.get_account_details("acc-1")

        assert first == second
        nordigen_client.account_api.assert_called_once_with(id="acc-1")
        account_resource.get_details.assert_called_once_with()
