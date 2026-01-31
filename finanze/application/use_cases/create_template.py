from uuid import uuid4

from application.ports.template_port import TemplatePort
from domain.exception.exceptions import TemplateAlreadyExists
from domain.template import Template, validate_template_default_values
from domain.use_cases.create_template import CreateTemplate


class CreateTemplateImpl(CreateTemplate):
    def __init__(self, template_port: TemplatePort):
        self._template_port = template_port

    async def execute(self, template: Template):
        existing = await self._template_port.get_by_name_and_type(
            template.name, template.type
        )
        if existing is not None:
            raise TemplateAlreadyExists(template.name, template.type.value)

        validate_template_default_values(template)

        template.id = uuid4()
        await self._template_port.save(template)
