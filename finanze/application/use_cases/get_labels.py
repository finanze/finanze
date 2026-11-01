from application.ports.label_port import LabelPort
from domain.labeling import Labels
from domain.use_cases.get_labels import GetLabels


class GetLabelsImpl(GetLabels):
    def __init__(self, label_port: LabelPort):
        self._label_port = label_port

    async def execute(self) -> Labels:
        labels = await self._label_port.get_all()
        usage = await self._label_port.get_usage()
        for label in labels:
            label.usage = usage.get(label.id, 0)
        return Labels(labels=labels)
