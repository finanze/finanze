from application.ports.label_port import LabelPort
from domain.labeling import Label, validate_label
from domain.use_cases.create_label import CreateLabel


class CreateLabelImpl(CreateLabel):
    def __init__(self, label_port: LabelPort):
        self._label_port = label_port

    async def execute(self, label: Label) -> Label:
        label.id = None
        label.key = None
        label.name = label.name.strip() if label.name else None
        validate_label(label)
        return await self._label_port.save(label)
