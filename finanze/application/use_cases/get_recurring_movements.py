from datetime import datetime

from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.ignored_recurring_movement_port import (
    IgnoredRecurringMovementPort,
)
from application.ports.label_port import LabelPort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.transaction_port import TransactionPort
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from domain.cashflow import (
    MAX_RECURRING_LOOKBACK_MONTHS,
    RecurringMovements,
    RecurringMovementsQuery,
    detect_recurring,
    rate_converter,
)
from domain.labeling import LabelCategory
from domain.transactions import ACCOUNT_MOVEMENT_TYPES, AccountTxSelection
from domain.use_cases.get_recurring_movements import GetRecurringMovements

MIN_RECURRING_LOOKBACK_MONTHS = 3


class GetRecurringMovementsImpl(GetRecurringMovements):
    def __init__(
        self,
        transaction_port: TransactionPort,
        label_port: LabelPort,
        entity_port: EntityPort,
        periodic_flow_port: PeriodicFlowPort,
        exchange_rate_storage: ExchangeRateStorage,
        ignored_recurring_movement_port: IgnoredRecurringMovementPort,
    ):
        self._transaction_port = transaction_port
        self._label_port = label_port
        self._entity_port = entity_port
        self._periodic_flow_port = periodic_flow_port
        self._exchange_rate_storage = exchange_rate_storage
        self._ignored_port = ignored_recurring_movement_port

    async def execute(self, query: RecurringMovementsQuery) -> RecurringMovements:
        today = datetime.now(tzlocal()).date()
        lookback = min(
            max(query.lookback_months, MIN_RECURRING_LOOKBACK_MONTHS),
            MAX_RECURRING_LOOKBACK_MONTHS,
        )
        types = [query.type] if query.type else sorted(ACCOUNT_MOVEMENT_TYPES)

        disabled = {e.id for e in await self._entity_port.get_disabled_entities()}
        excluded_labels = {
            label.id
            for label in await self._label_port.get_all()
            if label.category == LabelCategory.EXCLUDED
        }
        txs = await self._transaction_port.get_account_txs(
            AccountTxSelection(
                from_date=today - relativedelta(months=lookback),
                to_date=today,
                entities=query.entities,
                types=types,
                include_linked=False,
            )
        )
        txs = [tx for tx in txs if tx.entity.id not in disabled]
        flows = await self._periodic_flow_port.get_all()
        convert = rate_converter(
            await self._exchange_rate_storage.get(), query.currency
        )

        movements = detect_recurring(
            txs,
            excluded_labels,
            today,
            flows,
            convert,
            await self._ignored_port.get_all(),
        )
        return RecurringMovements(currency=query.currency, movements=movements)
