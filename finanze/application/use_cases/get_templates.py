from application.ports.template_port import TemplatePort
from domain.template import Template, get_effective_field
from domain.template_type import TemplateType
from domain.use_cases.get_templates import GetTemplates


class GetTemplatesImpl(GetTemplates):
    def __init__(self, template_port: TemplatePort):
        self._template_port = template_port

    async def execute(self, template_type: TemplateType) -> list[Template]:
        templates = await self._template_port.get_by_type(template_type)
        for template in templates:
            effective_fields = []
            for field in template.fields:
                effective_field = get_effective_field(
                    field.field, field.name, field.default_value, template
                )
                if effective_field:
                    effective_fields.append(effective_field)
            template.fields = effective_fields
        return templates
