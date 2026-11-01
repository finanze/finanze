from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from domain.exception.exceptions import ProviderPsuTypeNotSupported
from domain.external_entity import (
    ExternalEntityConnectionResult,
    ExternalEntitySetupResponseCode,
    PsuType,
)
from infrastructure.controller.config import quart
from infrastructure.controller.routes.connect_external_entity import (
    connect_external_entity,
)

BODY = {"institution_id": "ES:Bank", "provider": "ENABLE_BANKING"}


@pytest_asyncio.fixture
async def ctx(tmp_path):
    use_case = AsyncMock()
    use_case.execute.return_value = ExternalEntityConnectionResult(
        ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK,
        link="https://auth.example/start",
        id=uuid4(),
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    app = quart(static_dir)

    @app.route("/api/v1/entities/external", methods=["POST"])
    async def connect_route():
        return await connect_external_entity(use_case)

    yield SimpleNamespace(http=app.test_client(), use_case=use_case)


@pytest.mark.asyncio
async def test_forwards_requested_psu_type(ctx):
    response = await ctx.http.post(
        "/api/v1/entities/external", json={**BODY, "psu_type": "business"}
    )

    assert response.status_code == 200
    request = ctx.use_case.execute.await_args.args[0]
    assert request.psu_type == PsuType.BUSINESS


@pytest.mark.asyncio
async def test_omitted_psu_type_is_forwarded_as_none(ctx):
    response = await ctx.http.post("/api/v1/entities/external", json=BODY)

    assert response.status_code == 200
    assert ctx.use_case.execute.await_args.args[0].psu_type is None


@pytest.mark.asyncio
async def test_rejects_unknown_psu_type(ctx):
    response = await ctx.http.post(
        "/api/v1/entities/external", json={**BODY, "psu_type": "corporate"}
    )

    assert response.status_code == 400
    ctx.use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_maps_unsupported_psu_type_to_bad_request(ctx):
    ctx.use_case.execute.side_effect = ProviderPsuTypeNotSupported()

    response = await ctx.http.post(
        "/api/v1/entities/external", json={**BODY, "psu_type": "personal"}
    )

    assert response.status_code == 400
