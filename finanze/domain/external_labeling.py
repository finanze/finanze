from datetime import date
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.external_integration import ExternalIntegrationId
from domain.transactions import TxType
from pydantic.dataclasses import dataclass

MAX_LABELING_INSTRUCTIONS_LENGTH = 2000


@dataclass
class ExternalLabelCandidate:
    id: UUID
    key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ExternalLabelingTx:
    id: UUID
    date: date
    type: TxType
    amount: Dezimal
    currency: str
    name: str
    counterparty: Optional[str] = None


@dataclass
class ExternalLabelingExample:
    tx: ExternalLabelingTx
    label_ids: list[UUID]


@dataclass
class ExternalLabelingRequest:
    model: str
    txs: list[ExternalLabelingTx]
    labels: list[ExternalLabelCandidate]
    examples: Optional[list[ExternalLabelingExample]] = None
    instructions: Optional[str] = None
    upstream_provider: Optional[str] = None


@dataclass
class ExternalLabelSuggestion:
    tx_id: UUID
    label_id: UUID
    confidence: Optional[Dezimal] = None


@dataclass
class ExternalLabelingModel:
    id: str
    name: str
    description: Optional[str] = None
    probabilistic: bool = False


@dataclass
class ExternalLabelingProviderDetails:
    id: ExternalIntegrationId
    connected: bool
    recommended_models: list[ExternalLabelingModel]
    custom_models: bool = True
    upstream_providers: bool = False


@dataclass
class ExternalLabelingProviders:
    providers: list[ExternalLabelingProviderDetails]
