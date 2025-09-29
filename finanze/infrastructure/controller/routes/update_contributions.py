from datetime import date
from uuid import UUID

from domain.auto_contributions import (
    ContributionFrequency,
    ContributionTargetType,
    ManualPeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.use_cases.update_contributions import UpdateContributions
from flask import jsonify, request


async def update_contributions(update_contributions_uc: UpdateContributions):
    body = request.json

    contributions: list[ManualPeriodicContribution] = []
    try:
        entries = body.get("entries")
        for item in entries:
            entity_id = UUID(item["entity_id"])
            name = item["name"]
            target = item["target"]
            target_type = ContributionTargetType(item["target_type"])
            amount = Dezimal(item["amount"])
            currency = item["currency"]
            frequency = ContributionFrequency(item["frequency"])
            since_raw = item["since"]
            if isinstance(since_raw, str):
                since = date.fromisoformat(since_raw)
            elif isinstance(since_raw, date):
                since = since_raw
            else:
                raise ValueError("Invalid 'since' value")

            until_raw = item.get("until")
            if isinstance(until_raw, str):
                until = date.fromisoformat(until_raw)
            elif isinstance(until_raw, date) or until_raw is None:
                until = until_raw
            else:
                raise ValueError("Invalid 'until' value")

            contribution = ManualPeriodicContribution(
                entity_id=entity_id,
                name=name,
                target=target,
                target_name=item.get("target_name"),
                target_type=target_type,
                amount=amount,
                currency=currency,
                since=since,
                until=until,
                frequency=frequency,
            )
            contributions.append(contribution)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    await update_contributions_uc.execute(contributions)
    return "", 204
