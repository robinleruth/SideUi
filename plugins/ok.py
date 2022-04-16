from tkinter import *
from tkinter.ttk import *
from typing import List, Type, Any

from app import Event, Worker, WorkerMeta, MyFrame, ui_out_queue, VerticalScrolledFrame, metaclass_resolver


class E(Event):
    def __init__(self, m: str):
        self.m = m

    @staticmethod
    def get_repr():
        return 'E'


class W(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return E

    async def _process_message(self, message) -> Any:
        return message


class A(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        Label(self, text='Main content').pack()
        Button(self, text="Send", command=lambda: ui_out_queue.put(E("ok"))).pack()
        self.container = VerticalScrolledFrame(self)
        self.container.pack(expand=True, fill='both')

    def get_types(self) -> List[Type[Event]]:
        return [E]

    def process(self, message: E):
        Label(self.container.interior, text=message.m).pack()
        self.container.canvas.update_idletasks()
        self.container.canvas.yview_moveto(1)

    @staticmethod
    def get_name():
        return 'A'
