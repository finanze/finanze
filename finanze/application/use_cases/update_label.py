from application.ports.label_port import LabelPort
from domain.exception.exceptions import LabelNotFound, ProtectedLabel
from domain.labeling import Label, validate_label
from domain.use_cases.update_label import UpdateLabel


class UpdateLabelImpl(UpdateLabel):
    def __init__(self, label_port: LabelPort):
        self._label_port = label_port

    async def execute(self, label: Label, *, subcategory_provided: bool = True):
        existing = await self._label_port.get_by_id(label.id)
        if existing is None:
            raise LabelNotFound()
        if existing.protected:
            raise ProtectedLabel()

        label.key = existing.key
        if not subcategory_provided and label.category == existing.category:
            label.subcategory = existing.subcategory
        label.name = label.name.strip() if label.name else None
        validate_label(label)
        await self._label_port.update(label)
