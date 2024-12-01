import datetime
from collections import deque


class Entry:
    """
    Defines an accounting entry.
    """

    def __init__(self, quantity, price, factor=1, order_date=None, **kwargs):
        """
        Initializes an entry object with quantity, price, order_date, and optional factor.
        """
        self.quantity = quantity
        self.price = price
        self.factor = factor
        self.order_date = order_date or datetime.date.today()
        self.data = kwargs

    def __repr__(self):
        return f"{self.quantity} @ {self.price} on {self.order_date}"

    @property
    def size(self):
        return abs(self.quantity)

    @property
    def buy(self):
        return self.quantity > 0

    @property
    def sell(self):
        return not self.buy

    @property
    def zero(self):
        return self.quantity == 0

    @property
    def value(self):
        return self.quantity * self.price * self.factor

    def copy(self, quantity=None):
        return Entry(
            quantity or self.quantity,
            self.price,
            self.factor,
            self.order_date,
            **self.data.copy(),
        )


class FIFO:
    """
    Implements a FIFO accounting rule with the Wash Sale Rule applied.
    """

    def __init__(self, entries=None, wash_sale_period=60):
        """
        Initializes the FIFO accounting with optional wash sale rule.
        """
        self._entries = entries or []
        self.wash_sale_period = wash_sale_period  # Wash sale period in days
        self.inventory = deque()
        self.trace = []
        self.disallowed_losses = []  # Track wash sale disallowed losses

        self._balance = 0
        self._compute()

    @property
    def stock(self):
        return self._balance

    @property
    def valuation(self):
        return sum(e.quantity * e.price for e in self.inventory)

    @property
    def profit_and_loss(self):
        return sum(e.price * e.quantity for trace in self.trace for e in trace)

    def _push(self, entry):
        """
        Adds an entry to the inventory.
        """
        self.inventory.append(entry)
        self._balance += entry.quantity

    def _fill(self, entry):
        """
        Processes a sale with the wash sale rule applied.
        """
        entry = entry.copy()

        while not entry.zero:
            if not self.inventory:
                self._push(entry)
                return

            earliest = self.inventory.popleft()

            if self._is_wash_sale(earliest, entry):
                self.disallowed_losses.append((earliest, entry))
                self.inventory.appendleft(earliest)
                return

            if entry.size <= earliest.size:
                consumed = earliest.copy(-entry.quantity)
                earliest.quantity += entry.quantity

                if earliest.quantity != 0:
                    self.inventory.appendleft(earliest)

                self.trace.append([consumed, entry])
                self._balance += entry.quantity
                return
            else:
                consumed = entry.copy(-earliest.quantity)
                entry.quantity += earliest.quantity
                self.trace.append([earliest, consumed])
                self._balance += consumed.quantity

    def _is_wash_sale(self, buy, sell):
        """
        Determines if the sale triggers a wash sale rule.
        """
        if not buy.buy or not sell.sell:
            return False

        wash_sale_date = buy.order_date + datetime.timedelta(days=self.wash_sale_period)
        return sell.order_date <= wash_sale_date

    def _compute(self):
        for entry in self._entries:
            if (self._balance >= 0 and entry.buy) or (self._balance <= 0 and entry.sell):
                self._push(entry)
            elif not entry.zero:
                self._fill(entry)
