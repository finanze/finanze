from flask import jsonify

from domain.data_init import DataEncryptedError
from domain.exception.exceptions import InvalidProvidedCredentials, EntityNotFound


def handle_unexpected_error(e):
    return {"code": "UNEXPECTED_ERROR"}, 500


def handle_invalid_authentication(e):
    return {"code": "INVALID_CREDENTIALS"}, 401


def handle_entity_not_found(e):
    return jsonify({"code": "ENTITY_NOT_FOUND", "message": str(e)}), 404


def handle_invalid_credentials(e):
    return jsonify({"code": "INVALID_CREDENTIALS", "message": str(e)}), 400


def handle_data_encrypted(e):
    return jsonify({"code": "NOT_LOGGED"}), 401


def register_exception_handlers(app):
    app.register_error_handler(EntityNotFound, handle_entity_not_found)
    app.register_error_handler(InvalidProvidedCredentials, handle_invalid_credentials)
    app.register_error_handler(DataEncryptedError, handle_data_encrypted)
    app.register_error_handler(500, handle_unexpected_error)
    app.register_error_handler(401, handle_invalid_authentication)
