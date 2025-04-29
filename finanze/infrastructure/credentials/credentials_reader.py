import os
from typing import Optional
from uuid import UUID

import domain.native_entities
from application.ports.credentials_port import CredentialsPort
from domain.financial_entity import FinancialEntity, EntityCredentials
from domain.native_entities import NATIVE_ENTITIES


class CredentialsReader(CredentialsPort):

    def get(self, entity_id: UUID) -> Optional[EntityCredentials]:
        if entity_id == domain.native_entities.MY_INVESTOR.id:
            return {
                "user": os.environ["MYI_USERNAME"],
                "password": os.environ["MYI_PASSWORD"]
            }

        elif entity_id == domain.native_entities.TRADE_REPUBLIC.id:
            return {
                "phone": os.environ["TR_PHONE"],
                "password": os.environ["TR_PIN"]
            }

        elif entity_id == domain.native_entities.UNICAJA.id:
            return {
                "user": os.environ["UNICAJA_USERNAME"],
                "password": os.environ["UNICAJA_PASSWORD"]
            }

        elif entity_id == domain.native_entities.URBANITAE.id:
            return {
                "user": os.environ["URBANITAE_USERNAME"],
                "password": os.environ["URBANITAE_PASSWORD"]
            }

        elif entity_id == domain.native_entities.WECITY.id:
            return {
                "user": os.environ["WECITY_USERNAME"],
                "password": os.environ["WECITY_PASSWORD"]
            }

        elif entity_id == domain.native_entities.SEGO.id:
            return {
                "user": os.environ["SEGO_USERNAME"],
                "password": os.environ["SEGO_PASSWORD"]
            }

        elif entity_id == domain.native_entities.MINTOS.id:
            return {
                "user": os.environ["MINTOS_USERNAME"],
                "password": os.environ["MINTOS_PASSWORD"]
            }

        elif entity_id == domain.native_entities.F24.id:
            return {
                "user": os.environ["F24_USERNAME"],
                "password": os.environ["F24_PASSWORD"]
            }

        elif entity_id == domain.native_entities.INDEXA_CAPITAL.id:
            return {
                "token": os.environ["INDEXA_CAPITAL_TOKEN"]
            }

        return None

    def get_available_entities(self) -> list[FinancialEntity]:
        return NATIVE_ENTITIES

    def save(self, entity_id: UUID, credentials: EntityCredentials):
        pass

    def delete(self, entity_id: UUID):
        pass

    def update_last_usage(self, entity_id: UUID):
        pass
