import os

import domain.financial_entity as fe
from application.ports.credentials_port import CredentialsPort


class CredentialsReader(CredentialsPort):

    def get(self, entity: fe.FinancialEntity) -> tuple:
        if entity == fe.MY_INVESTOR:
            return os.environ["MYI_USERNAME"], os.environ["MYI_PASSWORD"]

        elif entity == fe.TRADE_REPUBLIC:
            return os.environ["TR_PHONE"], os.environ["TR_PIN"]

        elif entity == fe.UNICAJA:
            return os.environ["UNICAJA_USERNAME"], os.environ["UNICAJA_PASSWORD"]

        elif entity == fe.URBANITAE:
            return os.environ["URBANITAE_USERNAME"], os.environ["URBANITAE_PASSWORD"]

        elif entity == fe.WECITY:
            return os.environ["WECITY_USERNAME"], os.environ["WECITY_PASSWORD"]

        elif entity == fe.SEGO:
            return os.environ["SEGO_USERNAME"], os.environ["SEGO_PASSWORD"]

        elif entity == fe.MINTOS:
            return os.environ["MINTOS_USERNAME"], os.environ["MINTOS_PASSWORD"]

        elif entity == fe.F24:
            return os.environ["F24_USERNAME"], os.environ["F24_PASSWORD"]
