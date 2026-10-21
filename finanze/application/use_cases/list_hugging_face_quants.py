from application.ports.huggingface_catalog import HuggingFaceCatalog
from domain.local_model import HuggingFaceQuants
from domain.use_cases.list_hugging_face_quants import ListHuggingFaceQuants


class ListHuggingFaceQuantsImpl(ListHuggingFaceQuants):
    def __init__(self, hugging_face: HuggingFaceCatalog):
        self._hugging_face = hugging_face

    async def execute(self, repo: str) -> HuggingFaceQuants:
        return await self._hugging_face.list_quants(repo)
