import abc

from domain.ai import AIAttachment


class PdfPageRenderer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def render(
        self, pdf: bytes, max_pages: int, max_pixels: int
    ) -> list[AIAttachment]:
        raise NotImplementedError
