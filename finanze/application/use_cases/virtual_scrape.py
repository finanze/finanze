from asyncio import Lock
from datetime import datetime
from uuid import uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.ports.virtual_scraper import VirtualScraper
from application.use_cases.update_sheets import apply_global_config
from dateutil.tz import tzlocal
from domain.exception.exceptions import ExecutionConflict
from domain.scrap_result import ScrapResult, ScrapResultCode
from domain.scraped_data import VirtuallyScrapedData
from domain.use_cases.virtual_scrape import VirtualScrape
from domain.virtual_scrape import VirtualDataImport, VirtualDataSource


class VirtualScrapeImpl(AtomicUCMixin, VirtualScrape):
    def __init__(
        self,
        position_port: PositionPort,
        transaction_port: TransactionPort,
        virtual_scraper: VirtualScraper,
        entity_port: EntityPort,
        config_port: ConfigPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._position_port = position_port
        self._transaction_port = transaction_port
        self._virtual_scraper = virtual_scraper
        self._entity_port = entity_port
        self._config_port = config_port
        self._virtual_import_registry = virtual_import_registry

        self._lock = Lock()

    async def execute(self) -> ScrapResult:
        config = self._config_port.load()
        virtual_scrape_config = config.scrape.virtual

        sheet_config = config.integrations.sheets

        if (
            not virtual_scrape_config.enabled
            or not sheet_config
            or not sheet_config.credentials
        ):
            return ScrapResult(ScrapResultCode.DISABLED)

        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            sheets_credentials = sheet_config.credentials

            config_globals = virtual_scrape_config.globals

            registered_txs = self._transaction_port.get_refs_by_source_type(real=False)

            investment_sheets = virtual_scrape_config.investments or []
            transaction_sheets = virtual_scrape_config.transactions or []
            investment_sheets = apply_global_config(config_globals, investment_sheets)
            transaction_sheets = apply_global_config(config_globals, transaction_sheets)

            existing_entities = self._entity_port.get_all()
            existing_entities_by_name = {
                entity.name: entity for entity in existing_entities
            }

            (
                global_positions,
                created_pos_entities,
            ) = await self._virtual_scraper.global_positions(
                sheets_credentials, investment_sheets, existing_entities_by_name
            )

            if global_positions:
                for entity in created_pos_entities:
                    self._entity_port.insert(entity)
                    existing_entities_by_name[entity.name] = entity

                import_id = uuid4()
                import_date = datetime.now(tzlocal())
                for position in global_positions:
                    self._position_port.save(position)
                    self._virtual_import_registry.insert(
                        VirtualDataImport(
                            import_id=import_id,
                            global_position_id=position.id,
                            source=VirtualDataSource.SHEETS,
                            date=import_date,
                        )
                    )

            (
                transactions,
                created_tx_entities,
            ) = await self._virtual_scraper.transactions(
                sheets_credentials,
                transaction_sheets,
                registered_txs,
                existing_entities_by_name,
            )

            if transactions:
                for entity in created_tx_entities:
                    self._entity_port.insert(entity)

                self._transaction_port.save(transactions)

            data = VirtuallyScrapedData(
                positions=global_positions, transactions=transactions
            )

            return ScrapResult(ScrapResultCode.COMPLETED, data=data)
