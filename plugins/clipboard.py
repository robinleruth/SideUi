import os
from queue import Queue
from typing import *

from app import *

CLIPBOARD_FILE = r'clipboard.txt'


class ClipboardListener(metaclass_resolver(Worker, WorkerMeta)):
    def __init__(self, out_queues: List[Queue]):
        super().__init__(out_queues)
        self.state = None

    async def start(self):
        if not os.path.exists(CLIPBOARD_FILE):
            open(CLIPBOARD_FILE, 'w').close()
        return await super().start()

    def get_type(self) -> Type[Event]:
        return NewClipboardInfo

    async def _process_message(self, message) -> Any:
        if self.state != message.clipboard:
            self.state = message.clipboard
            with open(CLIPBOARD_FILE, 'a') as f:
                f.write(message.clipboard + '\n')
            return message
