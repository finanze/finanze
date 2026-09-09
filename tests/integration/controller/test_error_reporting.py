import pytest

from application.ports.error_reporter_port import ErrorReporterPort
from domain.exception.exceptions import EntityNotFound
from infrastructure.controller.config import quart


class FakeErrorReporter(ErrorReporterPort):
    def __init__(self):
        self.captured = []

    def set_enabled(self, enabled: bool):
        pass

    def set_context(self, context):
        pass

    def set_user(self, user_hash):
        pass

    def capture_exception(self, exc, *, tags=None, extra=None, level=None):
        self.captured.append((exc, tags))

    async def flush(self):
        pass


@pytest.fixture
def app_and_reporter(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    reporter = FakeErrorReporter()
    app = quart(static_dir, reporter)

    @app.route("/api/v1/boom", methods=["GET"])
    async def boom_route():
        raise TypeError("unexpected failure")

    @app.route("/api/v1/known", methods=["GET"])
    async def known_route():
        raise EntityNotFound("entity")

    return app, reporter


class TestErrorReporting:
    @pytest.mark.asyncio
    async def test_unexpected_error_is_reported_once(self, app_and_reporter):
        app, reporter = app_and_reporter

        response = await app.test_client().get("/api/v1/boom")

        assert response.status_code == 500
        assert len(reporter.captured) == 1
        exc, tags = reporter.captured[0]
        assert isinstance(exc, TypeError)
        assert tags["http_method"] == "GET"

    @pytest.mark.asyncio
    async def test_domain_errors_are_not_reported(self, app_and_reporter):
        app, reporter = app_and_reporter

        response = await app.test_client().get("/api/v1/known")

        assert response.status_code == 404
        assert reporter.captured == []

    @pytest.mark.asyncio
    async def test_app_works_without_reporter(self, tmp_path):
        static_dir = tmp_path / "static2"
        static_dir.mkdir()
        app = quart(static_dir)

        @app.route("/api/v1/boom", methods=["GET"])
        async def boom_route():
            raise TypeError("unexpected failure")

        response = await app.test_client().get("/api/v1/boom")

        assert response.status_code == 500
