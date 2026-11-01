from datetime import time
from difflib import SequenceMatcher
from uuid import UUID

from domain.dezimal import Dezimal
from domain.labeling import DEFAULT_TRANSFER_MAX_DAYS, LabelingRuleConditions
from domain.transactions import AccountTx, TxType

TRANSFER_TX_TYPES = {TxType.INFLOW, TxType.OUTFLOW}
TRANSFER_AMOUNT_TOLERANCE = Dezimal("0.01")

Cost = tuple[int, int, int]
ZERO_COST: Cost = (0, 0, 0)


def transfer_max_days(conditions: LabelingRuleConditions) -> int:
    if conditions.max_days is None:
        return DEFAULT_TRANSFER_MAX_DAYS
    return conditions.max_days


def is_pairable(tx: AccountTx) -> bool:
    return (
        tx.type in TRANSFER_TX_TYPES
        and not tx.labels_locked
        and not tx.linked_tx
        and tx.transfer_pair is None
    )


def transfer_eligible(conditions: LabelingRuleConditions, tx: AccountTx) -> bool:
    if not is_pairable(tx):
        return False
    amount = abs(tx.amount)
    if amount == 0:
        return False
    if conditions.min_amount is not None and amount < conditions.min_amount:
        return False
    if conditions.max_amount is not None and amount > conditions.max_amount:
        return False
    if conditions.currency and tx.currency.upper() != conditions.currency.upper():
        return False
    if conditions.entities and tx.entity.id not in conditions.entities:
        return False
    if conditions.ibans and tx.iban not in conditions.ibans:
        return False
    return True


def _different_accounts(tx: AccountTx, other: AccountTx) -> bool:
    if tx.iban and other.iban:
        return tx.iban != other.iban
    return tx.entity.id != other.entity.id


def _cost(outflow: AccountTx, inflow: AccountTx) -> Cost:
    gap = abs((outflow.date.date() - inflow.date.date()).days)
    seconds = 0
    if outflow.date.time() != time(0) and inflow.date.time() != time(0):
        seconds = int(abs((outflow.date - inflow.date).total_seconds()))
    similarity = SequenceMatcher(
        None, _normalize_name(outflow.name), _normalize_name(inflow.name)
    ).ratio()
    return gap, seconds, round((1 - similarity) * 1000)


def _normalize_name(name: str) -> str:
    return " ".join((name or "").lower().split())


def _add(a: Cost, b: Cost) -> Cost:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _sub(a: Cost, b: Cost) -> Cost:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _node_key(tx: AccountTx):
    return tx.date, tx.ref, tx.name, str(tx.id)


def _components(edges: dict[tuple[UUID, UUID], Cost]) -> list[set[UUID]]:
    parent: dict[UUID, UUID] = {}

    def find(node: UUID) -> UUID:
        while parent.setdefault(node, node) != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for out_id, in_id in edges:
        parent[find(out_id)] = find(in_id)

    groups: dict[UUID, set[UUID]] = {}
    for node in parent:
        groups.setdefault(find(node), set()).add(node)
    return list(groups.values())


def _match_component(
    outflows: list[UUID],
    inflows: list[UUID],
    edges: dict[tuple[UUID, UUID], Cost],
) -> dict[UUID, UUID]:
    # Successive shortest augmenting paths: max pairs first, then lowest total cost.
    adjacency = {
        out_id: [in_id for in_id in inflows if (out_id, in_id) in edges]
        for out_id in outflows
    }
    match_out: dict[UUID, UUID] = {}
    match_in: dict[UUID, UUID] = {}

    while True:
        dist_out: dict[UUID, Cost] = {
            out_id: ZERO_COST for out_id in outflows if out_id not in match_out
        }
        dist_in: dict[UUID, Cost] = {}
        prev_in: dict[UUID, UUID] = {}
        changed = True
        while changed:
            changed = False
            for out_id in outflows:
                if out_id not in dist_out:
                    continue
                for in_id in adjacency[out_id]:
                    if match_out.get(out_id) == in_id:
                        continue
                    candidate = _add(dist_out[out_id], edges[(out_id, in_id)])
                    if in_id not in dist_in or candidate < dist_in[in_id]:
                        dist_in[in_id] = candidate
                        prev_in[in_id] = out_id
                        changed = True
            for in_id in inflows:
                matched_out = match_in.get(in_id)
                if matched_out is None or in_id not in dist_in:
                    continue
                candidate = _sub(dist_in[in_id], edges[(matched_out, in_id)])
                if matched_out not in dist_out or candidate < dist_out[matched_out]:
                    dist_out[matched_out] = candidate
                    changed = True

        free_reached = [
            in_id for in_id in inflows if in_id in dist_in and in_id not in match_in
        ]
        if not free_reached:
            return match_out

        in_id = min(free_reached, key=lambda node: dist_in[node])
        while in_id is not None:
            out_id = prev_in[in_id]
            next_in = match_out.get(out_id)
            match_out[out_id] = in_id
            match_in[in_id] = out_id
            in_id = next_in


def match_transfers(
    candidates: list[AccountTx],
    pool: list[AccountTx],
    conditions: LabelingRuleConditions,
) -> list[tuple[AccountTx, AccountTx]]:
    max_days = transfer_max_days(conditions)
    eligible_pool = [tx for tx in pool if transfer_eligible(conditions, tx)]

    nodes: dict[UUID, AccountTx] = {}
    edges: dict[tuple[UUID, UUID], Cost] = {}
    for tx in candidates:
        if not transfer_eligible(conditions, tx):
            continue
        for other in eligible_pool:
            if other.id == tx.id or not _different_accounts(tx, other):
                continue
            if other.type == tx.type:
                continue
            if other.currency.upper() != tx.currency.upper():
                continue
            if abs(abs(tx.amount) - abs(other.amount)) > TRANSFER_AMOUNT_TOLERANCE:
                continue
            gap = abs((tx.date.date() - other.date.date()).days)
            if gap > max_days:
                continue
            outflow, inflow = (tx, other) if tx.type == TxType.OUTFLOW else (other, tx)
            nodes.setdefault(outflow.id, outflow)
            nodes.setdefault(inflow.id, inflow)
            edges.setdefault((outflow.id, inflow.id), _cost(outflow, inflow))

    pairs = []
    for component in _components(edges):
        ordered = sorted(component, key=lambda node: _node_key(nodes[node]))
        outflows = [node for node in ordered if nodes[node].type == TxType.OUTFLOW]
        inflows = [node for node in ordered if nodes[node].type == TxType.INFLOW]
        for out_id, in_id in _match_component(outflows, inflows, edges).items():
            pairs.append((nodes[out_id], nodes[in_id]))

    pairs.sort(key=lambda pair: _node_key(pair[0]))
    return pairs
