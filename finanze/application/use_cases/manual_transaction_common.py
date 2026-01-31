from datetime import datetime
from uuid import UUID, uuid4

from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.transactions import BaseTx, TxType
from domain.virtual_data import VirtualDataImport, VirtualDataSource


class ManualTransactionVirtualImportHelper:
    def __init__(self, virtual_import_registry: VirtualImportRegistry):
        self._virtual_import_registry = virtual_import_registry

    def update_derived_fields(self, tx: BaseTx):
        if not hasattr(tx, "net_amount"):
            return tx

        incoming_types = {
            TxType.SELL,
            TxType.DIVIDEND,
            TxType.INTEREST,
            TxType.REPAYMENT,
            TxType.RIGHT_SELL,
            TxType.TRANSFER_IN,
            TxType.SWITCH_TO,
            TxType.SWAP_TO,
        }
        outgoing_types = {
            TxType.BUY,
            TxType.INVESTMENT,
            TxType.SUBSCRIPTION,
            TxType.FEE,
            TxType.RIGHT_ISSUE,
            TxType.TRANSFER_OUT,
            TxType.SWITCH_FROM,
            TxType.SWAP_FROM,
        }

        fees = getattr(tx, "fees", None) or Dezimal(0)
        retentions = getattr(tx, "retentions", None) or Dezimal(0)

        if tx.type in incoming_types:
            tx.net_amount = tx.amount - fees - retentions
        elif tx.type in outgoing_types:
            tx.net_amount = tx.amount + fees + retentions
        else:
            tx.net_amount = tx.amount - fees - retentions

        return tx

    async def refresh(self, entity_id: UUID, has_transactions: bool):
        now = datetime.now(tzlocal())
        today = now.date()
        cloned = []
        last_manual_imports = (
            await self._virtual_import_registry.get_last_import_records(
                source=VirtualDataSource.MANUAL
            )
        )
        is_same_day = (
            last_manual_imports and last_manual_imports[0].date.date() == today
        )

        if is_same_day:
            import_id = last_manual_imports[0].import_id

            await self._virtual_import_registry.delete_by_import_feature_and_entity(
                import_id, Feature.TRANSACTIONS, entity_id
            )

        else:
            import_id = uuid4()
            for entry in last_manual_imports:
                if (
                    entry.feature == Feature.TRANSACTIONS
                    and entry.entity_id == entity_id
                ):
                    continue

                cloned.append(
                    VirtualDataImport(
                        import_id=import_id,
                        global_position_id=entry.global_position_id,
                        source=entry.source,
                        date=now,
                        feature=entry.feature,
                        entity_id=entry.entity_id,
                    )
                )

        if has_transactions:
            cloned.append(
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=None,
                    source=VirtualDataSource.MANUAL,
                    date=now,
                    feature=Feature.TRANSACTIONS,
                    entity_id=entity_id,
                )
            )

        if cloned:
            await self._virtual_import_registry.insert(cloned)
