import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.use_cases.get_cashflow_summary import GetCashflowSummaryImpl
from application.use_cases.get_labeling_rules import GetLabelingRulesImpl
from application.use_cases.get_labels import GetLabelsImpl
from application.use_cases.get_recurring_movements import GetRecurringMovementsImpl
from infrastructure.repository.cashflow.ignored_recurring_movement_repository import (
    IgnoredRecurringMovementRepository,
)
from infrastructure.repository.labeling.label_repository import LabelRepository
from infrastructure.repository.labeling.labeling_rule_repository import (
    LabelingRuleRepository,
)

MOBILE_ROOT = Path(__file__).resolve().parents[2] / "frontend/app/src/python/finanze"
FEATURE_COMPONENTS = {
    component.__name__: component
    for component in (
        LabelRepository,
        LabelingRuleRepository,
        IgnoredRecurringMovementRepository,
        GetLabelsImpl,
        GetLabelingRulesImpl,
        GetCashflowSummaryImpl,
        GetRecurringMovementsImpl,
    )
}
FEATURE_ROUTES = {
    "/api/v1/labels": "get_labels",
    "/api/v1/labeling/rules": "get_labeling_rules",
    "/api/v1/cashflow": "get_cashflow",
    "/api/v1/cashflow/recurring": "get_recurring",
}


def _load_mobile_module(name):
    spec = importlib.util.spec_from_file_location(name, MOBILE_ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mock_components(monkeypatch):
    constructors = {}
    for name in ("app_deferred", "app_lazy"):
        tree = ast.parse((MOBILE_ROOT / f"{name}.py").read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith(
                ("application.", "infrastructure.", "finanze.infrastructure.")
            ):
                continue
            module = ModuleType(node.module)
            for alias in node.names:
                constructor = constructors.setdefault(
                    alias.name,
                    MagicMock(
                        name=alias.name,
                        wraps=FEATURE_COMPONENTS.get(alias.name),
                    ),
                )
                setattr(module, alias.name, constructor)
            monkeypatch.setitem(sys.modules, node.module, module)

    for name in ("PreferenceExchangeRateStorage", "CryptoAssetInfoClient"):
        constructors[name].return_value.initialize = AsyncMock()
    constructors["GetExchangeRatesImpl"].return_value.execute = AsyncMock()
    monkeypatch.setattr("domain.position_aggregation.add_extensions", lambda: None)
    return constructors


@pytest.fixture
def components(monkeypatch):
    config = ModuleType("finanze.build_config")
    monkeypatch.setitem(sys.modules, "finanze.build_config", config)
    constructors = _mock_components(monkeypatch)
    return SimpleNamespace(
        config=config,
        constructors=constructors,
        core=MagicMock(),
        deferred_module=_load_mobile_module("app_deferred"),
        lazy_module=_load_mobile_module("app_lazy"),
        routes_module=_load_mobile_module("mobile_routes"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("include_connections", [True, False])
async def test_feature_services_are_created_only_in_lazy(
    components, include_connections
):
    components.config.INCLUDE_CONNECTIONS = include_connections
    deferred = components.deferred_module.DeferredComponents(components.core)
    await deferred.initialize()

    for name in FEATURE_COMPONENTS:
        components.constructors[name].assert_not_called()
    for name in (
        *FEATURE_ROUTES.values(),
        "label_repo",
        "labeling_rule_repo",
        "ignored_recurring_repo",
    ):
        assert not hasattr(deferred, name)

    lazy = components.lazy_module.LazyComponents(components.core, deferred)
    await lazy.initialize()

    for name in FEATURE_COMPONENTS:
        assert components.constructors[name].call_count == 1
    label_repo = lazy.get_labels._label_port
    rule_repo = lazy.get_labeling_rules._labeling_rule_port
    ignored_repo = lazy.get_recurring._ignored_port
    for repository in (label_repo, rule_repo, ignored_repo):
        assert repository._db_client is components.core.db_client
    assert lazy.get_cashflow._label_port is label_repo
    assert lazy.get_recurring._label_port is label_repo
    assert lazy.get_cashflow._transaction_port is deferred.tx_repo
    assert lazy.get_recurring._periodic_flow_port is deferred.period_repo
    assert lazy.get_recurring._exchange_rate_storage is deferred.ex_storage

    labeler_args = components.constructors["TransactionLabelerAdapter"].call_args.kwargs
    assert labeler_args["label_port"] is label_repo
    assert labeler_args["labeling_rule_port"] is rule_repo
    components.constructors["CreateLabelImpl"].assert_called_once_with(label_repo)
    components.constructors["IgnoreRecurringMovementImpl"].assert_called_once_with(
        ignored_repo
    )
    components.constructors["RestoreRecurringMovementImpl"].assert_called_once_with(
        ignored_repo
    )


@pytest.mark.parametrize("include_connections", [True, False])
def test_feature_routes_bind_lazy_services(
    components, monkeypatch, include_connections
):
    components.config.INCLUDE_CONNECTIONS = include_connections
    deferred_fields = {
        "login",
        "register",
        "get_settings",
        "change_pw",
        "logout",
        "get_avail_sources",
        "get_pos",
        "get_contrib",
        "get_tx",
        "get_ex_rates",
        "get_events",
        "get_integrations",
        "get_periodic",
        "query_pending",
        "list_re",
        "get_backups",
        "handle_cloud",
        "get_cloud",
        "get_bkp_settings",
    }
    deferred = SimpleNamespace(**{name: object() for name in deferred_fields})
    lazy = MagicMock()
    registered = []
    monkeypatch.setattr(
        components.routes_module,
        "_setup_routes",
        lambda router, routes: registered.extend(routes),
    )
    components.routes_module.setup_deferred_routes(None, deferred)
    assert not set(FEATURE_ROUTES) & {route[1] for route in registered}

    components.routes_module.setup_lazy_routes(None, lazy)
    bindings = {(method, path): service for method, path, _, _, service in registered}
    assert len(bindings) == len(registered)
    for path, name in FEATURE_ROUTES.items():
        assert bindings[("GET", path)] is getattr(lazy, name)
    assert bindings[("POST", "/api/v1/cashflow/recurring/ignored")] is (
        lazy.ignore_recurring_movement
    )
    assert (
        bindings[("DELETE", "/api/v1/cashflow/recurring/ignored/<ignored_id>")]
        is lazy.restore_recurring_movement
    )
