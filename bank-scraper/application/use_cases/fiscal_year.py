from application.ports.transaction_port import TransactionPort
from domain.fiscal_year_simulation import FiscalYearSimulation
from domain.use_cases.fiscal_year import FiscalYear


class FiscalYearImpl(FiscalYear):
    def __init__(self, transaction_port: TransactionPort):
        self.transaction_port = transaction_port

    def execute(self, year: int) -> FiscalYearSimulation:
        pass
# transactions = self.transaction_port.get_by_product(product_types=[TxProductType.FUND, TxProductType.STOCK_ETF])
#
# inv_txs: list[Union[StockTx, FundTx]] = transactions.investment
#
# grouped_by_isin = {}
# for tx in inv_txs:
#     if tx.type not in [TxType.BUY, TxType.SELL]:
#         continue
#
#     if tx.date.year > year:
#         continue
#
#     if tx.isin not in grouped_by_isin:
#         grouped_by_isin[tx.isin] = []
#
#     grouped_by_isin[tx.isin].append(tx)
#
# fifo_isin = {}
# for isin, txs in grouped_by_isin.items():
#     if not any(tx.type == TxType.SELL and tx.date.year == year for tx in txs):
#         continue
#
#     entries = [
#         Entry(quantity=(-1 if tx.type == TxType.BUY else 1) * tx.shares,
#               price=tx.netAmount / tx.shares,
#               order_date=tx.date)
#         for tx in txs
#     ]
#     fifo = FIFO(entries)
#     fifo_isin[isin] = fifo
#
# for isin, fifo in fifo_isin.items():
#     fifo_isin[isin] = {
#         "profitLoss": round(fifo.profit_and_loss, 2),
#         "details": [(" | ".join([f"({e})" for e in element])) for element in fifo.trace]
#     }
#
# total_profit_loss = round(sum([result["profitLoss"] for result in fifo_isin.values()]), 2)
#
# return FiscalYearSimulation(
#     year=year,
#     details=fifo_isin,
#     profitLoss=total_profit_loss,
# )
