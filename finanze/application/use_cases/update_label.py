from application.ports.label_port import LabelPort
from domain.exception.exceptions import LabelNotFound
from domain.labeling import Label, validate_label
from domain.use_cases.update_label import UpdateLabel


class UpdateLabelImpl(UpdateLabel):
    def __init__(self, label_port: LabelPort):
        self._label_port = label_port

    async def execute(self, label: Label):
        existing = await self._label_port.get_by_id(label.id)
        if existing is None:
            raise LabelNotFound()

        label.key = existing.key
        label.name = label.name.strip() if label.name else None
        validate_label(label)
        await self._label_port.update(label)
