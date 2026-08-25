from dataclasses import asdict

from domain.native_entities import B100, MY_INVESTOR, SEGO, TRADE_REPUBLIC, WECITY
from domain.native_entity import PinChannel


def test_sms_pin_entities_expose_sms_channel():
    assert MY_INVESTOR.pin is not None
    assert MY_INVESTOR.pin.channel == PinChannel.SMS
    assert MY_INVESTOR.pin.positions == 6

    assert WECITY.pin is not None
    assert WECITY.pin.channel == PinChannel.SMS
    assert WECITY.pin.positions == 6

    assert B100.pin is not None
    assert B100.pin.channel == PinChannel.SMS
    assert B100.pin.positions == 6

    assert TRADE_REPUBLIC.pin is not None
    assert TRADE_REPUBLIC.pin.channel == PinChannel.SMS
    assert TRADE_REPUBLIC.pin.positions == 4


def test_sego_pin_uses_email_channel():
    assert SEGO.pin is not None
    assert SEGO.pin.channel == PinChannel.EMAIL
    assert SEGO.pin.positions == 6


def test_pin_details_asdict_includes_channel():
    payload = asdict(WECITY)
    assert payload["pin"]["channel"] == PinChannel.SMS
    assert payload["pin"]["positions"] == 6
    assert payload["pin"]["pattern"] is None
