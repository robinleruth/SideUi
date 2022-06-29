import os
import datetime as dt
from tkinter import *
from tkinter.ttk import *
from typing import List, Type, Any

from app import *

ROUTINE_FILE = r'routine.txt'
ROUTINE_CHECK = r'routine_check.txt'


class E(Event):
    def __init__(self, m: str):
        self.m = m

    @staticmethod
    def get_repr():
        return 'ROUTINE CHECK'


class W(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return E

    async def _process_message(self, message: E) -> Any:
        return message


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.b = Button(self, text='Load', command=self.load)
        self.b.pack()
        self.vf = VerticalScrolledFrame(self)

    def get_types(self) -> List[Type[Event]]:
        return []

    def process(self, message: E):
        pass

    @staticmethod
    def get_name():
        return 'Routine'

    def load(self):
        self.vf.pack(expand=True, fill='both')
        frame = Frame(self.vf.interior)
        button_by_name = {}
        if not os.path.exists(ROUTINE_FILE):
            return
        with open(ROUTINE_FILE, 'r') as f:
            for line in f:
                if line == '\n':
                    frame.pack(expand=True, fill='both')
                    Separator(self.vf.interior, orient=HORIZONTAL).pack(expand=True, fill='both')
                    frame = Frame(self.vf.interior)
                else:
                    def out(d):
                        l = line.strip()

                        def inner(*args, **kwargs):
                            d[l].pack_forget()

                        return inner

                    l = line.strip()
                    b = Button(frame, text=l, command=out(button_by_name))
                    button_by_name[l] = b
                    b.pack(expand=True, fill='both')
        frame.pack(expand=True, fill='both')
        self.b.pack_forget()


if __name__ == '__main__':
    root = Tk()
    m = Frame(root)
    m.pack(expand=True, fill='both')
    F(m, m).pack(expand=True, fill='both')
    root.mainloop()
