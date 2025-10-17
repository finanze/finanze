from domain.instrument import InstrumentDataRequest, InstrumentType
from domain.use_cases.get_instrument_info import GetInstrumentInfo
from flask import jsonify, request


def instrument_details(get_instrument_info_uc: GetInstrumentInfo):
    name = request.args.get("name") or None
    isin = request.args.get("isin") or None
    ticker = request.args.get("ticker") or None
    if not any([name, isin, ticker]):
        return jsonify(
            {"message": "At least one of name, isin, or ticker must be provided"}
        ), 400

    raw_type = request.args.get("type")
    if not raw_type:
        return jsonify({"message": "Instrument type must be provided"}), 400

    try:
        ins_type = InstrumentType(raw_type)
    except ValueError:
        return jsonify({"message": f"Invalid instrument type: {raw_type}"}), 400

    data_request = InstrumentDataRequest(
        name=name,
        isin=isin,
        ticker=ticker,
        type=ins_type,
    )

    info = get_instrument_info_uc.execute(data_request)
    if info is None:
        return jsonify({"message": "Instrument not found"}), 404

    return jsonify(info), 200
