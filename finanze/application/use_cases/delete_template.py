from application.ports.template_port import TemplatePort
from domain.use_cases.delete_template import DeleteTemplate
from uuid import UUID


class DeleteTemplateImpl(DeleteTemplate):
    def __init__(self, template_port: TemplatePort):
        self._template_port = template_port

    def execute(self, template_id: UUID):
        self._template_port.delete(template_id)
