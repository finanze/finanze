from dataclasses import asdict
from datetime import date

from domain.dezimal import Dezimal
from domain.exception.exceptions import MissingFieldsError
from domain.global_position import InterestType
from domain.loan_calculator import LoanCalculationParams
from domain.use_cases.calculate_loan import CalculateLoan
from quart import jsonify, request


async def calculate_loan(calculate_loan_uc: CalculateLoan):
    body = await request.get_json() or {}

    try:
        # Optional monetary fields
        loan_amount = body.get("loan_amount")
        if loan_amount is not None:
            loan_amount = Dezimal(loan_amount)

        principal_outstanding = body.get("principal_outstanding")
        if principal_outstanding is not None:
            principal_outstanding = Dezimal(principal_outstanding)

        # Required fields
        interest_rate = Dezimal(body["interest_rate"])  # annual fraction (e.g., 0.03)
        interest_type = InterestType(body["interest_type"])  # FIXED | VARIABLE | MIXED

        # Conditional fields
        euribor_rate_val = body.get("euribor_rate")
        euribor_rate = (
            Dezimal(euribor_rate_val) if euribor_rate_val is not None else None
        )

        fixed_years = body.get("fixed_years")
        if fixed_years is not None:
            fixed_years = int(fixed_years)

        start = body["start"]
        end = body["end"]
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)

        params = LoanCalculationParams(
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            interest_type=interest_type,
            euribor_rate=euribor_rate,
            fixed_years=fixed_years,
            start=start,
            end=end,
            principal_outstanding=principal_outstanding,
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        result = await calculate_loan_uc.execute(params)
    except MissingFieldsError as e:
        return jsonify({"message": str(e)}), 400

    return jsonify(asdict(result)), 200
