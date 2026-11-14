import abc

from domain.ai import AIAttachment


class ImageNormalizer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def normalize(
        self, image: AIAttachment, max_pixels: int, max_bytes: int
    ) -> AIAttachment:
        raise NotImplementedError
