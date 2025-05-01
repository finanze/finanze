from flask import jsonify

from domain.use_cases.virtual_scrape import VirtualScrape


async def virtual_scrape(virtual_scrape: VirtualScrape):
    result = await virtual_scrape.execute()

    response = {"code": result.code.name}
    if result.data:
        response["data"] = result.data

    return jsonify(response), 200
