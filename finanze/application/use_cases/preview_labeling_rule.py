from application.ports.transaction_port import TransactionPort
from domain.labeling import (
    LabelingRulePreview,
    LabelingRulePreviewRequest,
    candidate_selection,
    groups_match,
    validate_condition_groups,
)
from domain.use_cases.preview_labeling_rule import PreviewLabelingRule

MAX_PREVIEW_SAMPLES = 50


class PreviewLabelingRuleImpl(PreviewLabelingRule):
    def __init__(self, transaction_port: TransactionPort):
        self._transaction_port = transaction_port

    async def execute(self, request: LabelingRulePreviewRequest) -> LabelingRulePreview:
        groups = request.conditions
        validate_condition_groups(groups)

        txs = await self._transaction_port.get_account_txs(candidate_selection(groups))
        matches = [tx for tx in txs if groups_match(groups, tx)]
        limit = max(0, min(request.limit, MAX_PREVIEW_SAMPLES))
        return LabelingRulePreview(count=len(matches), samples=matches[:limit])
