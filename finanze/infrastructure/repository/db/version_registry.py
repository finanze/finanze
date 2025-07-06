from infrastructure.repository.db.versions.v0_genesis import V0Genesis
from infrastructure.repository.db.versions.v011_0 import V0110
from infrastructure.repository.db.versions.v020_0_crypto import V0200Crypto
from infrastructure.repository.db.versions.v020_1_fetches import V0201
from infrastructure.repository.db.versions.v020_2_null_portfolio_kpis import V0202
from infrastructure.repository.db.versions.v020_3_virtual_imports_feature import V0203
from infrastructure.repository.db.versions.v020_4_commodities import V0204Commodities

versions = [
    V0Genesis(),
    V0110(),
    V0200Crypto(),
    V0201(),
    V0202(),
    V0203(),
    V0204Commodities(),
]
