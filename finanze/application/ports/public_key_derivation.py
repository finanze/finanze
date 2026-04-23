import abc

from domain.public_key import AddressDerivationRequest, DerivedAddressesResult


class PublicKeyDerivation(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def calculate(self, request: AddressDerivationRequest) -> DerivedAddressesResult:
        pass
