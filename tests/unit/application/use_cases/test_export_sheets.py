from datetime import datetime, timezone

from dateutil.tz import tzlocal, tzoffset

from application.use_cases.export_sheets import _format_datetime
from domain.entity import Feature
from domain.export import NumberFormat, TemplatedDataProcessorParams


def _params(datetime_format=None):
    return TemplatedDataProcessorParams(
        template=None,
        number_format=NumberFormat.ENGLISH,
        feature=Feature.POSITION,
        products=None,
        datetime_format=datetime_format,
        date_format=None,
    )


class TestFormatDatetime:
    def test_aware_value_keeps_its_instant(self):
        value = datetime(2025, 2, 3, 23, 30, tzinfo=tzoffset(None, 5 * 3600))

        assert _format_datetime(value, _params()) == (
            value.astimezone(tzlocal()).isoformat()
        )
        assert _format_datetime(value, _params("%d/%m/%Y %H:%M")) == (
            value.astimezone(tzlocal()).strftime("%d/%m/%Y %H:%M")
        )

    def test_naive_value_is_treated_as_utc(self):
        value = datetime(2025, 2, 4, 8, 15)

        assert _format_datetime(value, _params("%Y-%m-%d %H:%M")) == (
            value.replace(tzinfo=timezone.utc)
            .astimezone(tzlocal())
            .strftime("%Y-%m-%d %H:%M")
        )
