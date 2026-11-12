from application.ports.file_rw_port import TableRWPort
from application.ports.template_parser_port import TemplateParserPort
from application.ports.template_port import TemplatePort
from domain.entity import Feature
from domain.exception.exceptions import FeatureNotSupported
from domain.importing import TemplateFieldsSuggestion, TemplateFieldsSuggestionRequest
from domain.template_fields import TEMPLATE_FIELD_MATRIX
from domain.template_type import TemplateType
from domain.use_cases.suggest_template_fields import SuggestTemplateFields

IMPORTABLE_FEATURES = {Feature.POSITION, Feature.TRANSACTIONS}


class SuggestTemplateFieldsImpl(SuggestTemplateFields):
    def __init__(
        self,
        table_rw_port: TableRWPort,
        template_parser: TemplateParserPort,
        template_port: TemplatePort,
    ):
        self._table_rw_port = table_rw_port
        self._template_parser = template_parser
        self._template_port = template_port

    async def execute(
        self, request: TemplateFieldsSuggestionRequest
    ) -> TemplateFieldsSuggestion:
        product_fields = None
        if request.feature in IMPORTABLE_FEATURES:
            product_fields = TEMPLATE_FIELD_MATRIX[request.feature].get(request.product)
        if not product_fields:
            raise FeatureNotSupported()

        fields = [
            field
            for field in product_fields
            if field.template_type != TemplateType.EXPORT
        ]
        table = await self._table_rw_port.parse(request.file)
        templates = [
            template
            for template in await self._template_port.get_by_type(TemplateType.IMPORT)
            if template.feature == request.feature
            and (not template.products or request.product in template.products)
        ]
        return await self._template_parser.suggest_fields(table, fields, templates)
