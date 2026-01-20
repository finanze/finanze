from domain.entity import Feature
from domain.template_fields import ALL_TEMPLATE_FIELDS, FieldGroup
from domain.use_cases.get_template_fields import GetTemplateFields


class GetTemplateFieldsImpl(GetTemplateFields):
    async def execute(self) -> dict[Feature, list[FieldGroup]]:
        return ALL_TEMPLATE_FIELDS
