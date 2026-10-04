import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from dateutil.tz import tzlocal
from application.ports.config_port import ConfigPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.external_tx_labeling_provider import (
    ExternalTxLabelingProvider,
)
from application.ports.label_port import LabelPort
from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_label_port import TransactionLabelPort
from application.ports.transaction_labeler import TransactionLabeler
from application.ports.transaction_port import TransactionPort
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExternalLabelingUnavailable
from domain.external_integration import ExternalIntegrationId
from domain.external_labeling import (
    MAX_LABELING_INSTRUCTIONS_LENGTH,
    ExternalLabelCandidate,
    ExternalLabelingExample,
    ExternalLabelingRequest,
    ExternalLabelingTx,
)
from domain.labeling import (
    LABELABLE_TX_TYPES,
    LabelingResult,
    LabelingRule,
    LabelingRuleKind,
    LabelingTrigger,
    conditions_match,
    matching_rules,
)
from domain.settlement import SETTLEMENT_MAX_DAYS, match_settlements
from domain.transactions import (
    ACCOUNT_MOVEMENT_TYPES,
    AccountTx,
    AccountTxSelection,
    LabelOrigin,
    TransferPair,
    TxLabel,
)
from domain.transfer_pairing import (
    TRANSFER_TX_TYPES,
    is_pairable,
    match_transfers,
    transfer_max_days,
)

EXTERNAL_BATCH_SIZE = 25
EXAMPLES_PER_LABEL = 2
MAX_EXAMPLES = 50
EXAMPLE_ORIGINS = (LabelOrigin.MANUAL, LabelOrigin.RULE)
AUTO_TIME_BUDGET_SECONDS = 45
MANUAL_TIME_BUDGET_SECONDS = 600


def _to_external_tx(tx: AccountTx) -> ExternalLabelingTx:
    return ExternalLabelingTx(
        id=tx.id,
        date=tx.date.date(),
        type=tx.type,
        amount=tx.amount,
        currency=tx.currency,
        name=tx.name,
        counterparty=tx.counterparty,
    )


def _rule_labels(rule: LabelingRule) -> list[TxLabel]:
    return [
        TxLabel(label_id=label_id, origin=LabelOrigin.RULE, rule_id=rule.id)
        for label_id in rule.label_ids
    ]


class TransactionLabelerAdapter(TransactionLabeler):
    def __init__(
        self,
        transaction_port: TransactionPort,
        transaction_label_port: TransactionLabelPort,
        labeling_rule_port: LabelingRulePort,
        label_port: LabelPort,
        config_port: ConfigPort,
        external_integration_port: ExternalIntegrationPort,
        providers: dict[ExternalIntegrationId, ExternalTxLabelingProvider],
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._transaction_port = transaction_port
        self._transaction_label_port = transaction_label_port
        self._labeling_rule_port = labeling_rule_port
        self._label_port = label_port
        self._config_port = config_port
        self._external_integration_port = external_integration_port
        self._providers = providers
        self._transaction_handler_port = transaction_handler_port
        self._log = logging.getLogger(__name__)

    async def classify(self, selection: AccountTxSelection) -> LabelingResult:
        txs = await self._transaction_port.get_account_txs(selection)
        result = LabelingResult(processed=len(txs))
        if not txs:
            return result

        async with self._transaction_handler_port.start():
            result.linked = await self._link(txs)

            rules = await self._labeling_rule_port.get_all(enabled_only=True)
            transfer_rules = [
                rule
                for rule in rules
                if rule.kind == LabelingRuleKind.TRANSFER and rule.label_ids
            ]
            result.paired = await self._pair_transfers(txs, transfer_rules)
            transfer_labels = {rule.id: _rule_labels(rule) for rule in transfer_rules}

            for tx in txs:
                if tx.labels_locked:
                    result.skipped_locked += 1
                    continue
                if tx.linked_tx:
                    result.skipped_linked += 1
                    continue
                pair_labels = (
                    transfer_labels.get(tx.transfer_pair.rule_id)
                    if tx.transfer_pair
                    else None
                )
                if await self._apply_rules(tx, rules, pair_labels):
                    result.rule_labeled += 1

        return result

    async def link_settlements(self, selection: AccountTxSelection) -> int:
        txs = await self._transaction_port.get_account_txs(
            replace(
                selection,
                include_locked=False,
                include_linked=False,
                types=list(ACCOUNT_MOVEMENT_TYPES),
            )
        )
        if not txs:
            return 0
        async with self._transaction_handler_port.start():
            return await self._link(txs)

    async def apply_rule(self, rule: LabelingRule) -> int:
        if rule.kind == LabelingRuleKind.TRANSFER:
            return await self._apply_transfer_rule(rule)

        if not rule.enabled or not rule.label_ids:
            return 0

        conditions = rule.conditions
        types = [t for t in (conditions.types or LABELABLE_TX_TYPES)]
        txs = await self._transaction_port.get_account_txs(
            AccountTxSelection(
                from_date=conditions.from_date,
                to_date=conditions.to_date,
                entities=conditions.entities,
                types=types,
                include_locked=False,
                include_linked=False,
            )
        )

        applied = 0
        async with self._transaction_handler_port.start():
            for tx in txs:
                if not conditions_match(conditions, tx):
                    continue
                if any(
                    label.origin == LabelOrigin.EXTERNAL for label in tx.labels or []
                ):
                    await self._transaction_label_port.delete(
                        [tx.id], [LabelOrigin.EXTERNAL]
                    )
                await self._transaction_label_port.add(
                    tx.id,
                    [
                        TxLabel(
                            label_id=label_id, origin=LabelOrigin.RULE, rule_id=rule.id
                        )
                        for label_id in rule.label_ids
                    ],
                )
                applied += 1
        return applied

    async def classify_external(
        self,
        selection: AccountTxSelection,
        trigger: LabelingTrigger,
        retry_unmatched: bool = False,
    ) -> LabelingResult:
        result = LabelingResult()
        try:
            settings = await self._config_port.load()
            config = settings.labeling.external
            if not config.enabled or not config.provider or not config.model:
                return result
            if trigger == LabelingTrigger.AUTO and not config.autoRun:
                return result

            try:
                provider_id = ExternalIntegrationId(config.provider)
            except ValueError:
                return result
            provider = self._providers.get(provider_id)
            if provider is None:
                return result

            credentials = await self._external_integration_port.get_payload(provider_id)
            if not credentials:
                return result

            txs = await self._transaction_port.get_account_txs(
                replace(
                    selection,
                    include_locked=False,
                    include_linked=False,
                    unlabeled_only=True,
                    exclude_external_unmatched=not retry_unmatched,
                    types=[
                        t
                        for t in (selection.types or LABELABLE_TX_TYPES)
                        if t in LABELABLE_TX_TYPES
                    ],
                ),
                limit=max(config.maxPerRun, 0),
            )
            result.processed = len(txs)
            if not txs:
                return result

            labels = await self._label_port.get_all()
            if not labels:
                return result
            candidates = [
                ExternalLabelCandidate(
                    id=label.id,
                    key=label.key,
                    name=label.name,
                    description=label.description,
                )
                for label in labels
            ]
            known_label_ids = {label.id for label in labels}

            examples = None
            example_origins = [
                origin
                for origin in config.examples.origins
                if origin in EXAMPLE_ORIGINS
            ]
            if (
                config.examples.enabled
                and config.examples.count > 0
                and example_origins
            ):
                examples = await self._build_examples(
                    min(config.examples.count, MAX_EXAMPLES),
                    known_label_ids,
                    example_origins,
                )

            min_confidence = Dezimal(max(min(config.minConfidence, 100), 0)) / 100
            instructions = (config.instructions or "").strip()[
                :MAX_LABELING_INSTRUCTIONS_LENGTH
            ] or None
            provider_name = f"{provider_id.value}:{config.model}"
            budget = (
                AUTO_TIME_BUDGET_SECONDS
                if trigger == LabelingTrigger.AUTO
                else MANUAL_TIME_BUDGET_SECONDS
            )
            started = time.monotonic()

            for index in range(0, len(txs), EXTERNAL_BATCH_SIZE):
                if time.monotonic() - started > budget:
                    break
                batch = txs[index : index + EXTERNAL_BATCH_SIZE]
                suggestions = await provider.label(
                    ExternalLabelingRequest(
                        model=config.model,
                        txs=[_to_external_tx(tx) for tx in batch],
                        labels=candidates,
                        examples=examples,
                        instructions=instructions,
                        upstream_provider=(config.upstreamProvider or "").strip()
                        or None,
                    ),
                    credentials,
                )
                result.external_labeled += await self._store_external(
                    batch, suggestions, known_label_ids, min_confidence, provider_name
                )
        except ExternalLabelingUnavailable as e:
            self._log.warning(f"External transaction labeling unavailable: {e.details}")
            result.external_error = type(e).__name__
            result.external_error_details = e.details or None
        except Exception as e:
            self._log.exception("External transaction labeling failed")
            result.external_error = type(e).__name__
        return result

    async def _build_examples(
        self,
        count: int,
        known_label_ids: set[UUID],
        origins: list[LabelOrigin],
    ) -> Optional[list[ExternalLabelingExample]]:
        example_txs = await self._transaction_label_port.get_examples(
            origins, EXAMPLES_PER_LABEL, count
        )
        examples = []
        for tx in example_txs:
            label_ids = [
                label.label_id
                for label in tx.labels or []
                if label.origin in origins and label.label_id in known_label_ids
            ]
            if label_ids:
                examples.append(
                    ExternalLabelingExample(tx=_to_external_tx(tx), label_ids=label_ids)
                )
        return examples or None

    async def _store_external(
        self,
        batch: list[AccountTx],
        suggestions,
        known_label_ids: set[UUID],
        min_confidence: Dezimal,
        provider_name: str,
    ) -> int:
        accepted: dict[UUID, list[TxLabel]] = {}
        batch_ids = {tx.id for tx in batch}
        for suggestion in suggestions:
            if suggestion.tx_id not in batch_ids:
                continue
            if suggestion.label_id not in known_label_ids:
                continue
            if suggestion.confidence is None:
                if min_confidence > 0:
                    continue
            elif suggestion.confidence < min_confidence:
                continue
            accepted.setdefault(suggestion.tx_id, []).append(
                TxLabel(
                    label_id=suggestion.label_id,
                    origin=LabelOrigin.EXTERNAL,
                    provider=provider_name,
                    confidence=suggestion.confidence,
                )
            )

        async with self._transaction_handler_port.start():
            await self._transaction_label_port.set_external_unmatched(
                [tx.id for tx in batch if tx.id not in accepted],
                datetime.now(tzlocal()),
            )
            if not accepted:
                return 0
            still_eligible = await self._transaction_port.get_account_txs(
                AccountTxSelection(
                    ids=list(accepted.keys()),
                    include_locked=False,
                    include_linked=False,
                    unlabeled_only=True,
                )
            )
            for tx in still_eligible:
                await self._transaction_label_port.add(tx.id, accepted[tx.id])
            await self._transaction_label_port.set_external_unmatched(
                [tx.id for tx in still_eligible], None
            )
        return len(still_eligible)

    async def _apply_rules(
        self,
        tx: AccountTx,
        rules: list[LabelingRule],
        pair_labels: Optional[list[TxLabel]] = None,
    ) -> bool:
        if tx.type not in LABELABLE_TX_TYPES:
            return False

        new_labels: dict[UUID, TxLabel] = {}
        if pair_labels:
            new_labels = {label.label_id: label for label in pair_labels}
        else:
            for rule in matching_rules(rules, tx):
                for label_id in rule.label_ids:
                    new_labels.setdefault(
                        label_id,
                        TxLabel(
                            label_id=label_id, origin=LabelOrigin.RULE, rule_id=rule.id
                        ),
                    )

        current = tx.labels or []
        current_rule = {
            (label.label_id, label.rule_id)
            for label in current
            if label.origin == LabelOrigin.RULE
        }
        has_external = any(label.origin == LabelOrigin.EXTERNAL for label in current)
        target = {(label.label_id, label.rule_id) for label in new_labels.values()}

        if new_labels:
            if current_rule == target and not has_external:
                return True
            await self._transaction_label_port.delete(
                [tx.id], [LabelOrigin.RULE, LabelOrigin.EXTERNAL]
            )
            await self._transaction_label_port.add(tx.id, list(new_labels.values()))
            return True

        if current_rule:
            await self._transaction_label_port.delete([tx.id], [LabelOrigin.RULE])
        return False

    async def _set_rule_labels(self, tx: AccountTx, labels: list[TxLabel]):
        await self._transaction_label_port.delete(
            [tx.id], [LabelOrigin.RULE, LabelOrigin.EXTERNAL]
        )
        await self._transaction_label_port.add(tx.id, labels)

    async def _pair_transfers(
        self, txs: list[AccountTx], rules: list[LabelingRule]
    ) -> int:
        if not rules:
            return 0

        candidates = [tx for tx in txs if is_pairable(tx)]
        paired = 0
        if candidates:
            gap = timedelta(days=max(transfer_max_days(r.conditions) for r in rules))
            pool = await self._transaction_port.get_account_txs(
                AccountTxSelection(
                    from_date=min(tx.date.date() for tx in candidates) - gap,
                    to_date=max(tx.date.date() for tx in candidates) + gap,
                    types=list(TRANSFER_TX_TYPES),
                    include_locked=False,
                    include_linked=False,
                )
            )
            pool = [tx for tx in pool if is_pairable(tx)]
            selected = {tx.id: tx for tx in txs}
            taken: set[UUID] = set()

            for rule in rules:
                pairs = match_transfers(candidates, pool, rule.conditions)
                if not pairs:
                    continue
                labels = _rule_labels(rule)
                for outflow, inflow in pairs:
                    await self._transaction_label_port.add_transfer_pair(
                        outflow.id, inflow.id, rule.id
                    )
                    for tx, partner in ((outflow, inflow), (inflow, outflow)):
                        taken.add(tx.id)
                        pair = TransferPair(
                            tx_id=partner.id,
                            entity_id=partner.entity.id,
                            rule_id=rule.id,
                        )
                        if tx.id in selected:
                            selected[tx.id].transfer_pair = pair
                        else:
                            await self._set_rule_labels(tx, labels)
                paired += len(pairs)
                candidates = [tx for tx in candidates if tx.id not in taken]
                pool = [tx for tx in pool if tx.id not in taken]

        await self._transaction_label_port.delete_unpaired_rule_labels(
            [rule.id for rule in rules]
        )
        return paired

    async def _apply_transfer_rule(self, rule: LabelingRule) -> int:
        async with self._transaction_handler_port.start():
            await self._transaction_label_port.delete_transfer_pairs_by_rule(rule.id)
            if not rule.enabled or not rule.label_ids:
                await self._transaction_label_port.delete_unpaired_rule_labels(
                    [rule.id]
                )
                return 0

            txs = await self._transaction_port.get_account_txs(
                AccountTxSelection(
                    entities=rule.conditions.entities,
                    types=list(TRANSFER_TX_TYPES),
                    include_locked=False,
                    include_linked=False,
                )
            )
            pairable = [tx for tx in txs if is_pairable(tx)]
            for outflow, inflow in match_transfers(pairable, pairable, rule.conditions):
                await self._transaction_label_port.add_transfer_pair(
                    outflow.id, inflow.id, rule.id
                )
                for tx, partner in ((outflow, inflow), (inflow, outflow)):
                    tx.transfer_pair = TransferPair(
                        tx_id=partner.id, entity_id=partner.entity.id, rule_id=rule.id
                    )

            labels = _rule_labels(rule)
            applied = 0
            for tx in txs:
                if tx.transfer_pair and tx.transfer_pair.rule_id == rule.id:
                    await self._set_rule_labels(tx, labels)
                    applied += 1

            await self._transaction_label_port.delete_unpaired_rule_labels([rule.id])
        return applied

    async def _link(self, txs: list[AccountTx]) -> int:
        candidates = [
            tx
            for tx in txs
            if not tx.labels_locked
            and not tx.linked_tx
            and tx.type in ACCOUNT_MOVEMENT_TYPES
        ]
        if not candidates:
            return 0

        entity_ids = list({tx.entity.id for tx in candidates})
        gap = timedelta(days=SETTLEMENT_MAX_DAYS)
        from_date = min(tx.date.date() for tx in candidates) - gap
        to_date = max(tx.date.date() for tx in candidates) + gap

        investment_txs = await self._transaction_port.get_investment_txs_in_range(
            entity_ids, from_date, to_date
        )
        if not investment_txs:
            return 0

        taken = await self._transaction_label_port.get_linked_refs(entity_ids)
        links = match_settlements(candidates, investment_txs, taken)
        by_id = {tx.id: tx for tx in candidates}
        for tx_id, ref in links.items():
            await self._transaction_label_port.set_linked_tx(tx_id, ref)
            await self._transaction_label_port.delete(
                [tx_id], [LabelOrigin.RULE, LabelOrigin.EXTERNAL]
            )
            by_id[tx_id].linked_tx = ref
        return len(links)
