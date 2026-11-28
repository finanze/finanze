import abc

from domain.ai import AIAttachment


class ImageNormalizer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def normalize(
        self, image: AIAttachment, max_pixels: int, max_bytes: int
    ) -> AIAttachment:
        raise NotImplementedError

    # Top and bottom halves cut between text lines, empty when it cannot be split
    @abc.abstractmethod
    async def split(self, image: AIAttachment, max_bytes: int) -> list[AIAttachment]:
        raise NotImplementedError
