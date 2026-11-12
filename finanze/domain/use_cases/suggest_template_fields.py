import abc

from domain.importing import TemplateFieldsSuggestion, TemplateFieldsSuggestionRequest


class SuggestTemplateFields(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: TemplateFieldsSuggestionRequest
    ) -> TemplateFieldsSuggestion:
        raise NotImplementedError
