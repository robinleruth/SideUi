import datetime as dt
import os
from tkinter import *
from tkinter.ttk import *
from typing import List, Type, Any

import pandas as pd

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
        if not os.path.exists(ROUTINE_CHECK):
            with open(ROUTINE_CHECK, 'w') as f:
                f.write("date,item\n")
        with open(ROUTINE_CHECK, 'a') as f:
            now = dt.date.today()
            f.write(f"{now},{message.m}\n")
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
        return [E]

    def process(self, message: E):
        print(f"{message.m} done")

    @staticmethod
    def get_name():
        return 'Routine'

    def load(self):
        self.vf.pack(expand=True, fill='both')
        frame = Frame(self.vf.interior)
        button_by_name = {}
        if not os.path.exists(ROUTINE_FILE):
            return
        already_done = set()
        if os.path.exists(ROUTINE_CHECK):
            df = pd.read_csv(ROUTINE_CHECK)
            now = dt.date.today()
            df = df[df['date'].isin([str(now)])]
            already_done = set(df['item'].values)
        with open(ROUTINE_FILE, 'r') as f:
            for line in f:
                if line == '\n':
                    frame.pack(expand=True, fill='both')
                    Separator(self.vf.interior, orient=HORIZONTAL).pack(expand=True, fill='both')
                    frame = Frame(self.vf.interior)
                else:
                    l = line.strip()
                    if l in already_done:
                        continue

                    def out(d):
                        _l = l

                        def inner(*args, **kwargs):
                            ui_out_queue.put(E(_l))
                            d[_l].pack_forget()

                        return inner

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
