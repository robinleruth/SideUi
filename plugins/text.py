import os
from tkinter import *
from tkinter.ttk import *
from typing import List, Type

from app import *

FILE = r'text.txt'


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.file = StringVar(master=self)
        self.b = Button(self, text='Load', command=self.load)
        self.b.pack()
        self.f = Frame(self)
        self.t = Text(self.f)
        self.t.pack()
        self.state = None

    def get_types(self) -> List[Type[Event]]:
        return []

    def process(self, message: Event):
        pass

    @staticmethod
    def get_name():
        return 'T'

    def save(self):
        content = self.t.get('1.0', 'end')
        if content != self.state:
            print('Saving')
            self.state = content
            with open(FILE, 'w') as f:
                f.write(content)
        self.controller.master.after(4000, self.save)

    def load(self):
        if os.path.exists(FILE):
            with open(FILE, 'r') as f:
                self.t.insert('1.0', ''.join(f.readlines()))
        self.f.pack()
        self.b.pack_forget()
        self.controller.master.after(4000, self.save)


if __name__ == '__main__':
    root = Tk()
    m = Frame(root)
    m.pack()
    F(m, m).pack()
    root.mainloop()
