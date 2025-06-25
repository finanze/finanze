from infrastructure.repository.db.versions.v0_genesis import V0Genesis
from infrastructure.repository.db.versions.v011_0 import V0110
from infrastructure.repository.db.versions.v020_0_crypto import V0200Crypto
from infrastructure.repository.db.versions.v020_1_fetches import V0201

versions = [V0Genesis(), V0110(), V0200Crypto(), V0201()]
