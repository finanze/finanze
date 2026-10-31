from application.ports.transaction_port import TransactionPort
from domain.labeling import (
    LABELABLE_TX_TYPES,
    LabelingRulePreview,
    LabelingRulePreviewRequest,
    conditions_match,
    validate_conditions,
)
from domain.transactions import AccountTxSelection
from domain.use_cases.preview_labeling_rule import PreviewLabelingRule

MAX_PREVIEW_SAMPLES = 50


class PreviewLabelingRuleImpl(PreviewLabelingRule):
    def __init__(self, transaction_port: TransactionPort):
        self._transaction_port = transaction_port

    async def execute(self, request: LabelingRulePreviewRequest) -> LabelingRulePreview:
        conditions = request.conditions
        validate_conditions(conditions)

        txs = await self._transaction_port.get_account_txs(
            AccountTxSelection(
                from_date=conditions.from_date,
                to_date=conditions.to_date,
                entities=conditions.entities,
                types=list(conditions.types or LABELABLE_TX_TYPES),
                include_locked=False,
                include_linked=False,
            )
        )
        matches = [tx for tx in txs if conditions_match(conditions, tx)]
        limit = max(0, min(request.limit, MAX_PREVIEW_SAMPLES))
        return LabelingRulePreview(count=len(matches), samples=matches[:limit])
