from domain.dezimal import Dezimal
from domain.transactions import TxType


def compute_return_values(related_inv_txs):
    repayment_txs = [tx for tx in related_inv_txs if tx.type == TxType.REPAYMENT]
    interest_txs = [tx for tx in related_inv_txs if tx.type == TxType.INTEREST]
    dividend_txs = [tx for tx in related_inv_txs if tx.type == TxType.DIVIDEND]

    returned, repaid, fees, retentions, interests, net_return = (
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
        Dezimal(0),
    )
    last_return_tx = None

    if repayment_txs:
        fees += sum([tx.fees for tx in repayment_txs], start=Dezimal(0))
        retentions += sum([tx.retentions for tx in repayment_txs], start=Dezimal(0))

        repaid += sum([tx.amount for tx in repayment_txs], start=Dezimal(0))
        returned = repaid
        net_return = repaid

        last_return_tx = max(repayment_txs, key=lambda txx: txx.date)
        if last_return_tx:
            last_return_tx = last_return_tx.date

    if interest_txs:
        interest_fees = sum([tx.fees for tx in interest_txs], start=Dezimal(0))
        interest_retentions = sum(
            [tx.retentions for tx in interest_txs], start=Dezimal(0)
        )
        added_interests = sum([tx.amount for tx in interest_txs], start=Dezimal(0))

        fees += interest_fees
        retentions += interest_retentions
        interests += added_interests

        net_return += added_interests - interest_fees - interest_retentions
        returned += added_interests

    if dividend_txs:
        dividend_fees = sum([tx.fees for tx in dividend_txs], start=Dezimal(0))
        dividend_retentions = sum(
            [tx.retentions for tx in dividend_txs], start=Dezimal(0)
        )

        total_dividends = sum([tx.amount for tx in dividend_txs], start=Dezimal(0))

        fees += dividend_fees
        retentions += dividend_retentions
        interests += total_dividends

        net_return += total_dividends - dividend_fees - dividend_retentions
        returned += total_dividends

    return fees, interests, net_return, repaid, retentions, returned, last_return_tx
