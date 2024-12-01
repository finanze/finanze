from dataclasses import dataclass


@dataclass
class FiscalYearSimulation:
    year: int
    details: dict
    profitLoss: float
