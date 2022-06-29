import os
import datetime as dt
from tkinter import *
from tkinter.ttk import *
from typing import *

import pandas as pd
from pandas.errors import EmptyDataError

from app import *

DONE_FILE = r'done.txt'


class DoneFileUpdate(Event):
    update: pd.DataFrame
    new_update: Tuple[str, str]

    def __init__(self, update, new_update) -> None:
        self.update = update
        self.new_update = new_update

    @staticmethod
    def get_repr():
        return 'DONE FILE UPDATE'


class DoneFileSubscriber(metaclass_resolver(FileSubscriber, WorkerMeta)):
    async def start(self):
        if not os.path.exists(self.get_file_name()):
            with open(self.get_file_name(), 'w') as f:
                f.write("date,task\n")
        return await super().start()

    def get_type(self) -> Type[DoneFileUpdate]:
        return DoneFileUpdate

    def get_file_name(self) -> str:
        return DONE_FILE

    async def _process_message(self, message: DoneFileUpdate) -> DoneFileUpdate:
        if message.new_update is not None:
            with open(self.get_file_name(), 'a') as f:
                d = message.new_update[0]
                t = message.new_update[1]
                f.write("{},{}\n".format(d, t))
            return
        return message

    async def _get_update(self) -> Any:
        try:
            df = pd.read_csv(self.get_file_name())
        except EmptyDataError:
            print('No data in data file')
        else:
            if not df.equals(self.state):
                self.state = df
                now = dt.date.today().strftime('%Y-%m-%d')
                df = df[df['date'].isin([now])]
                return self.get_type()(df, None)


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        grid = Frame(self)
        grid.pack()
        Label(grid, text='Task').grid(row=0, column=0)
        self.msg = StringVar(master=self)
        self.entry = Entry(grid, textvariable=self.msg)
        self.entry.grid(row=0, column=1)
        Button(self, text='Update', command=lambda: self._update()).pack()
        Button(self, text="Open file", command=lambda: open_file(DONE_FILE)).pack()
        self.container = VerticalScrolledFrame(self)
        self.container.pack(expand=True, fill='x')

    def get_types(self) -> List[Type[Event]]:
        return [DoneFileUpdate]

    def process(self, message: DoneFileUpdate):
        self.update_dones(message)

    @staticmethod
    def get_name():
        return 'Done'

    def update_dones(self, message: DoneFileUpdate):
        for item in self.container.interior.winfo_children():
            item.destroy()
        for update in message.update['task'].values:
            Label(self.container.interior, text=update.strip()).pack()

    def _update(self):
        now = dt.date.today().strftime('%Y-%m-%d')
        task = self.msg.get()
        self.msg.set('')
        self.entry.focus()
        ui_out_queue.put(DoneFileUpdate(None, (now, task)))


if __name__ == '__main__':
    root = Tk()
    m = Frame(root)
    m.pack()
    F(m, m).pack()
    root.mainloop()
