import os

import domain.financial_entity as fe
import domain.native_entities
from application.ports.credentials_port import CredentialsPort


class CredentialsReader(CredentialsPort):

    def get(self, entity: fe.FinancialEntity) -> tuple:
        if entity == domain.native_entities.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif entity == domain.native_entities.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif entity == domain.native_entities.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

        elif entity == domain.native_entities.URBANITAE:
            return os.environ["URBANITAE_USERNAME"], os.environ["URBANITAE_PASSWORD"]

        elif entity == domain.native_entities.WECITY:
            return os.environ["WECITY_USERNAME"], os.environ["WECITY_PASSWORD"]

        elif entity == domain.native_entities.SEGO:
            return os.environ["SEGO_USERNAME"], os.environ["SEGO_PASSWORD"]

        elif entity == domain.native_entities.MINTOS:
            return os.environ["MINTOS_USERNAME"], os.environ["MINTOS_PASSWORD"]

        elif entity == domain.native_entities.F24:
            return os.environ["F24_USERNAME"], os.environ["F24_PASSWORD"]
