from quart import jsonify

from domain.use_cases.get_available_entities import GetAvailableEntities


async def get_available_sources(get_available_entities: GetAvailableEntities):
    available_sources = await get_available_entities.execute()
    return jsonify(available_sources), 200
