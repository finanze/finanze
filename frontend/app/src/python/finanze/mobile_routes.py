from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.controller.router import Router
    from finanze.app_core import MobileAppCore
    from finanze.app_deferred import DeferredComponents
    from finanze.app_lazy import LazyComponents


def _setup_routes(router: "Router", routes: list[tuple]):
    module_cache: dict[str, object] = {}

    def bind(module_name: str, func_name: str, *deps):
        if module_name not in module_cache:
            module_cache[module_name] = import_module(
                f"infrastructure.controller.routes.{module_name}"
            )
        func = getattr(module_cache[module_name], func_name)

        async def handler(_req):
            view_args = getattr(_req, "view_args", None) or {}
            return await func(*deps, **view_args)

        return handler

    for method, path, module_name, func_name, dep in routes:
        router.add(method, path, bind(module_name, func_name, dep))


def setup_core_routes(router: "Router", core: "MobileAppCore") -> None:
    routes = [
        ("GET", "/api/v1/status", "get_status", "status", core.status),
    ]
    _setup_routes(router, routes)


def setup_deferred_routes(router: "Router", deferred: "DeferredComponents") -> None:
    d = deferred

    routes = [
        ("POST", "/api/v1/login", "user_login", "user_login", d.login),
        ("POST", "/api/v1/signup", "register_user", "register_user", d.register),
        ("GET", "/api/v1/settings", "get_settings", "get_settings", d.get_settings),
        (
            "POST",
            "/api/v1/change-password",
            "change_user_password",
            "change_user_password",
            d.change_pw,
        ),
        ("POST", "/api/v1/logout", "logout", "logout", d.logout),
        (
            "GET",
            "/api/v1/entities",
            "get_available_sources",
            "get_available_sources",
            d.get_avail_sources,
        ),
        ("GET", "/api/v1/positions", "positions", "positions", d.get_pos),
        (
            "GET",
            "/api/v1/contributions",
            "contributions",
            "contributions",
            d.get_contrib,
        ),
        ("GET", "/api/v1/transactions", "transactions", "transactions", d.get_tx),
        (
            "GET",
            "/api/v1/exchange-rates",
            "exchange_rates",
            "exchange_rates",
            d.get_ex_rates,
        ),
        ("GET", "/api/v1/events", "get_money_events", "get_money_events", d.get_events),
        (
            "GET",
            "/api/v1/integrations",
            "get_external_integrations",
            "get_external_integrations",
            d.get_integrations,
        ),
        (
            "GET",
            "/api/v1/flows/periodic",
            "get_periodic_flows",
            "get_periodic_flows",
            d.get_periodic,
        ),
        (
            "GET",
            "/api/v1/flows/pending",
            "get_pending_flows",
            "get_pending_flows",
            d.get_pending,
        ),
        (
            "GET",
            "/api/v1/real-estate",
            "list_real_estate",
            "list_real_estate",
            d.list_re,
        ),
        (
            "POST",
            "/api/v1/data/manual/positions/update-quotes",
            "update_tracked_quotes",
            "update_tracked_quotes",
            d.up_tracked,
        ),
        (
            "POST",
            "/api/v1/data/manual/positions/update-loans",
            "update_tracked_loans",
            "update_tracked_loans",
            d.up_tracked_loans,
        ),
        ("GET", "/api/v1/cloud/backup", "get_backups", "get_backups", d.get_backups),
        (
            "POST",
            "/api/v1/cloud/auth",
            "handle_cloud_auth",
            "handle_cloud_auth",
            d.handle_cloud,
        ),
        ("GET", "/api/v1/cloud/auth", "get_cloud_auth", "get_cloud_auth", d.get_cloud),
        (
            "GET",
            "/api/v1/cloud/backup/settings",
            "get_backup_settings",
            "get_backup_settings",
            d.get_bkp_settings,
        ),
    ]

    _setup_routes(router, routes)


def setup_lazy_routes(router: "Router", lazy: "LazyComponents") -> None:
    lz = lazy

    routes = [
        (
            "POST",
            "/api/v1/entities/login",
            "add_entity_login",
            "add_entity_login",
            lz.add_entity_creds,
        ),
        (
            "POST",
            "/api/v1/data/fetch/financial",
            "fetch_financial_data",
            "fetch_financial_data",
            lz.fetch_financial,
        ),
        (
            "POST",
            "/api/v1/data/fetch/crypto",
            "fetch_crypto_data",
            "fetch_crypto_data",
            lz.fetch_crypto,
        ),
        (
            "POST",
            "/api/v1/data/import/file",
            "import_file",
            "import_file_route",
            lz.import_file,
        ),
        (
            "POST",
            "/api/v1/data/export/file",
            "export_file",
            "export_file",
            lz.export_file,
        ),
        (
            "POST",
            "/api/v1/crypto-wallet",
            "connect_crypto_wallet",
            "connect_crypto_wallet",
            lz.conn_crypto,
        ),
        (
            "GET",
            "/api/v1/crypto-wallet/derivate",
            "derive_crypto_addresses",
            "derive_crypto_addresses",
            lz.derive_crypto,
        ),
        (
            "POST",
            "/api/v1/cloud/backup/upload",
            "upload_backup",
            "upload_backup",
            lz.upload_backup,
        ),
        (
            "POST",
            "/api/v1/cloud/backup/import",
            "import_backup",
            "import_backup",
            lz.import_backup,
        ),
        (
            "POST",
            "/api/v1/settings",
            "update_settings",
            "update_settings",
            lz.update_settings,
        ),
        (
            "DELETE",
            "/api/v1/entities/login",
            "disconnect_entity",
            "disconnect_entity",
            lz.disconnect_entity,
        ),
        (
            "PUT",
            "/api/v1/crypto-wallet",
            "update_crypto_wallet",
            "update_crypto_wallet",
            lz.up_crypto,
        ),
        (
            "DELETE",
            "/api/v1/crypto-wallet/<wallet_connection_id>",
            "delete_crypto_wallet",
            "delete_crypto_wallet",
            lz.del_crypto,
        ),
        (
            "GET",
            "/api/v1/crypto-wallet/addresses",
            "get_crypto_wallet_addresses",
            "get_crypto_wallet_addresses",
            lz.get_wallet_addrs,
        ),
        (
            "POST",
            "/api/v1/commodities",
            "save_commodities",
            "save_commodities",
            lz.save_commodities,
        ),
        (
            "POST",
            "/api/v1/integrations/<integration_id>",
            "connect_external_integration",
            "connect_external_integration",
            lz.conn_integration,
        ),
        (
            "DELETE",
            "/api/v1/integrations/<integration_id>",
            "disconnect_external_integration",
            "disconnect_external_integration",
            lz.disconn_integration,
        ),
        (
            "POST",
            "/api/v1/flows/periodic",
            "save_periodic_flow",
            "save_periodic_flow",
            lz.save_periodic,
        ),
        (
            "PUT",
            "/api/v1/flows/periodic",
            "update_periodic_flow",
            "update_periodic_flow",
            lz.up_periodic,
        ),
        (
            "DELETE",
            "/api/v1/flows/periodic/<flow_id>",
            "delete_periodic_flow",
            "delete_periodic_flow",
            lz.del_periodic,
        ),
        (
            "POST",
            "/api/v1/flows/pending",
            "save_pending_flows",
            "save_pending_flows",
            lz.save_pending,
        ),
        (
            "POST",
            "/api/v1/real-estate",
            "create_real_estate",
            "create_real_estate",
            lz.create_re,
        ),
        (
            "PUT",
            "/api/v1/real-estate",
            "update_real_estate",
            "update_real_estate",
            lz.up_re,
        ),
        (
            "DELETE",
            "/api/v1/real-estate/<real_estate_id>",
            "delete_real_estate",
            "delete_real_estate",
            lz.del_re,
        ),
        (
            "POST",
            "/api/v1/calculation/loan",
            "calculate_loan",
            "calculate_loan",
            lz.calc_loan,
        ),
        (
            "POST",
            "/api/v1/calculations/savings",
            "calculate_savings",
            "calculate_savings",
            lz.calc_savings,
        ),
        (
            "GET",
            "/api/v1/rates/euribor",
            "get_euribor_rates",
            "get_euribor_rates",
            lz.get_euribor,
        ),
        ("POST", "/api/v1/forecast", "forecast", "forecast", lz.forecast),
        (
            "POST",
            "/api/v1/data/manual/contributions",
            "update_contributions",
            "update_contributions",
            lz.up_contrib,
        ),
        (
            "POST",
            "/api/v1/data/manual/positions",
            "update_position",
            "update_position",
            lz.up_pos,
        ),
        (
            "POST",
            "/api/v1/data/manual/transactions",
            "add_manual_transaction",
            "add_manual_transaction",
            lz.add_manual_tx,
        ),
        (
            "PUT",
            "/api/v1/data/manual/transactions/<tx_id>",
            "update_manual_transaction",
            "update_manual_transaction",
            lz.up_manual_tx,
        ),
        (
            "DELETE",
            "/api/v1/data/manual/transactions/<tx_id>",
            "delete_manual_transaction",
            "delete_manual_transaction",
            lz.del_manual_tx,
        ),
        ("GET", "/api/v1/historic", "historic", "get_historic", lz.get_historic),
        (
            "GET",
            "/api/v1/assets/instruments",
            "instruments",
            "instruments",
            lz.get_instruments,
        ),
        (
            "GET",
            "/api/v1/assets/instruments/details",
            "instrument_details",
            "instrument_details",
            lz.get_inst_info,
        ),
        (
            "GET",
            "/api/v1/assets/crypto",
            "search_crypto_assets",
            "search_crypto_assets",
            lz.search_crypto,
        ),
        (
            "GET",
            "/api/v1/assets/crypto/<asset_id>",
            "get_crypto_asset_details",
            "get_crypto_asset_details",
            lz.get_crypto_details,
        ),
        ("GET", "/api/v1/templates", "get_templates", "get_templates", lz.get_tmpl),
        (
            "POST",
            "/api/v1/templates",
            "create_template",
            "create_template",
            lz.create_tmpl,
        ),
        ("PUT", "/api/v1/templates", "update_template", "update_template", lz.up_tmpl),
        (
            "DELETE",
            "/api/v1/templates/<template_id>",
            "delete_template",
            "delete_template",
            lz.del_tmpl,
        ),
        (
            "GET",
            "/api/v1/templates/fields",
            "get_template_fields_route",
            "get_template_fields",
            lz.get_tmpl_fields,
        ),
        (
            "POST",
            "/api/v1/cloud/backup/settings",
            "save_backup_settings",
            "save_backup_settings",
            lz.save_bkp_settings,
        ),
    ]

    _setup_routes(router, routes)
