from domain.dezimal import Dezimal
from infrastructure.client.crypto.space.space_client import SpaceClient


class BlockstreamClient(SpaceClient):
    URL = "https://blockstream.info/api"

    def __init__(self, scale: Dezimal):
        super().__init__("btc", "BTC", scale)
        self.base_url = self.URL
