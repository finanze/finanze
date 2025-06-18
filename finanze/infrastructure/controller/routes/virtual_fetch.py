from flask import jsonify

from domain.use_cases.virtual_fetch import VirtualFetch


async def virtual_fetch(virtual_fetch_uc: VirtualFetch):
    result = await virtual_fetch_uc.execute()

    response = {"code": result.code.name}
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
