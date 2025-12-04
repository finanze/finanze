from dataclasses import asdict

from domain.calculations import (
    SavingsCalculationRequest,
    SavingsPeriodicity,
    SavingsRetirementRequest,
    SavingsScenarioRequest,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import CalculationInputError, MissingFieldsError
from domain.use_cases.calculate_savings import CalculateSavings
from flask import jsonify, request


def _parse_periodicity(value: str) -> SavingsPeriodicity:
    try:
        return SavingsPeriodicity(value)
    except ValueError as e:
        raise MissingFieldsError(["periodicity"]) from e


def _parse_scenario(raw: dict) -> SavingsScenarioRequest:
    return SavingsScenarioRequest(
        scenario_id=raw["id"],
        annual_market_performance=Dezimal(raw["annual_market_performance"]),
        periodic_contribution=Dezimal(raw["periodic_contribution"])
        if raw.get("periodic_contribution") is not None
        else None,
        target_amount=Dezimal(raw["target_amount"])
        if raw.get("target_amount")
        else None,
    )


def _parse_retirement(payload: dict | None) -> SavingsRetirementRequest | None:
    if payload is None:
        return None
    return SavingsRetirementRequest(
        withdrawal_amount=Dezimal(payload["withdrawal_amount"])
        if payload.get("withdrawal_amount") is not None
        else None,
        withdrawal_years=payload.get("withdrawal_years"),
    )


def calculate_savings(calculate_savings_uc: CalculateSavings):
    body = request.json or {}
    try:
        base_amount = (
            Dezimal(body["base_amount"])
            if body.get("base_amount") is not None
            else None
        )
        years = body.get("years")
        years = int(years) if years is not None else None
        periodicity = _parse_periodicity(body["periodicity"])
        scenarios = [_parse_scenario(raw) for raw in body["scenarios"]]
        retirement = _parse_retirement(body.get("retirement"))
    except (KeyError, ValueError, TypeError, MissingFieldsError) as e:
        print(e)
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        result = calculate_savings_uc.execute(
            SavingsCalculationRequest(
                base_amount=base_amount,
                years=years,
                periodicity=periodicity,
                scenarios=scenarios,
                retirement=retirement,
            )
        )
    except (MissingFieldsError, CalculationInputError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return jsonify(asdict(result)), 200
