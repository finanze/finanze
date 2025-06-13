from application.ports.transaction_handler_port import TransactionHandlerPort


class AtomicUCMixin:
    def __init__(
        self, transaction_handler_port: TransactionHandlerPort, *args, **kwargs
    ):
        self._transaction_handler_port = transaction_handler_port
        super().__init__(*args, **kwargs)

    @classmethod
    def _wrap_execute(cls):
        original_execute = cls.execute

        async def wrapped_execute(self, *args, **kwargs):
            async with self._transaction_handler_port.start():
                return await original_execute(self, *args, **kwargs)

        cls.execute = wrapped_execute

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "execute" in cls.__dict__:
            cls._wrap_execute()
