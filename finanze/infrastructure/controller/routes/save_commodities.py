from domain.commodity import CommodityRegister, UpdateCommodityPosition
from domain.use_cases.save_commodities import SaveCommodities
from flask import jsonify, request


async def save_commodities(save_commodities_uc: SaveCommodities):
    body = request.json

    registers = []
    try:
        for reg in body.get("registers", []):
            registers.append(CommodityRegister(**reg))
    except Exception as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    commodities_request = UpdateCommodityPosition(registers=registers)

    await save_commodities_uc.execute(commodities_request)
    return "", 204
