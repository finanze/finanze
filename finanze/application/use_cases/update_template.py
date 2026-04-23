from application.ports.template_port import TemplatePort
from domain.exception.exceptions import TemplateNotFound
from domain.template import Template, validate_template_default_values
from domain.use_cases.update_template import UpdateTemplate


class UpdateTemplateImpl(UpdateTemplate):
    def __init__(self, template_port: TemplatePort):
        self._template_port = template_port

    async def execute(self, template: Template):
        existing = await self._template_port.get_by_id(template.id)
        if existing is None:
            raise TemplateNotFound()

        validate_template_default_values(template)

        await self._template_port.update(template)
