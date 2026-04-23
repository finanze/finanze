import abc

from domain.public_key import DerivedAddressesResult, AddressDerivationPreviewRequest


class DeriveCryptoAddresses(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: AddressDerivationPreviewRequest
    ) -> DerivedAddressesResult:
        raise NotImplementedError
