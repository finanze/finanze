import os

from application.ports.credentials_port import CredentialsPort
from domain.financial_entity import Entity


class CredentialsReader(CredentialsPort):

    def get(self, entity: Entity) -> tuple:
        if entity == Entity.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif entity == Entity.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif entity == Entity.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

        elif entity == Entity.URBANITAE:
            return os.environ["URBANITAE_USERNAME"], os.environ["URBANITAE_PASSWORD"]

        elif entity == Entity.WECITY:
            return os.environ["WECITY_USERNAME"], os.environ["WECITY_PASSWORD"]

        elif entity == Entity.SEGO:
            return os.environ["SEGO_USERNAME"], os.environ["SEGO_PASSWORD"]
