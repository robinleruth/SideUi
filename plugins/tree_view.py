from tkinter import *
from tkinter.ttk import *
from typing import List, Type

import pandas as pd

from app import *


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        Button(self, text='Load data', command=self.load).pack()

    def get_types(self) -> List[Type[Event]]:
        return []

    def process(self, message: Event):
        pass

    @staticmethod
    def get_name():
        return 'TreeView'

    def load(self):
        df = pd.DataFrame([
            {
                'a': 1,
                'b': 2,
                'c': 3
            },
            {
                'a': 4,
                'b': 5,
                'c': 6
            }
        ])
        self.create_treeview(df)

    def create_treeview(self, data=None):
        sv = StringVar(master=self)
        e = Entry(self, textvariable=sv)
        e.pack()
        container = Frame(self)
        container.pack(expand=True, fill='both')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        tree = Treeview(container)
        tree.grid(row=0, column=0, sticky='nsew')

        def item_selected(t):
            def inner(*args, **kwargs):
                for selected_item in t.selection():
                    item = tree.item(selected_item)
                    record = [str(i) for i in item['values']]
                    # showinfo(title='Information', message=','.join(record))
                    print(record)

            return inner

        tree.bind('<<TreeviewSelect>>', item_selected(tree))
        scrollbar = Scrollbar(container, orient=VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')
        if data is not None:
            self.update_treeview(tree, data)

        def on_filter():
            detached = set()
            nonlocal sv
            nonlocal tree

            def brut_search(children, query):
                nonlocal detached
                i_r = -1
                for item_id in children:
                    values = tree.item(item_id)['values']
                    txt = ','.join([str(i) for i in values])
                    if query in txt.lower():
                        i_r += 1
                        tree.reattach(item_id, '', i_r)
                    else:
                        detached.add(item_id)
                        tree.detach(item_id)

            def inner(*args, **kwargs):
                nonlocal detached
                children = list(detached) + list(tree.get_children())
                detached = set()
                query = sv.get()
                brut_search(children, query.lower())

            return inner

        def on_double_click(t: Treeview):
            ep: EntryPopup = None

            def inner(event):
                nonlocal ep
                if ep is not None:
                    ep.destroy()
                row_id = t.identify_row(event.y)
                if not row_id:
                    return
                column = t.identify_column(event.x)
                x, y, width, height = t.bbox(row_id, column)
                pady = height // 2
                text = t.item(row_id, 'values')[int(column[1:]) - 1]
                ep = EntryPopup(t, row_id, int(column[1:]) - 1, text)
                ep.place(x=x, y=y + pady, anchor=W, width=width, height=height)

            return inner

        e.bind('<Return>', on_filter())
        tree.bind('<Double-Button-1>', on_double_click(tree))

    @staticmethod
    def update_treeview(tree, df: pd.DataFrame):
        tree.delete(*tree.get_children())
        tree['columns'] = list(df.columns)
        tree['show'] = 'headings'
        for i in df.columns:
            tree.column(i, anchor="w", stretch=True, width=10)
            tree.heading(i, text=i, anchor="w")
        for index, row in df.iterrows():
            tree.insert("", END, text=index, values=list(row))


class EntryPopup(Entry):
    def __init__(self, parent, iid, column, text, **kw):
        Style().configure('pad.TEntry', padding='1 1 1 1')
        super().__init__(parent, style='pad.TEntry', **kw)
        self.tv = parent
        self.iid = iid
        self.column = column

        self.insert(0, text)
        # self['state'] = 'readonly'
        # self['readonlybackground'] = 'white'
        # self['selectbackground'] = '#1BA1E2'
        self['exportselection'] = False

        self.focus_force()
        self.select_all()
        self.bind("<Return>", self.on_return)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Escape>", lambda *ignore: self.destroy())

    def on_return(self, event):
        rowid = self.tv.focus()
        item = [*self.tv.item(rowid, 'values')]
        item[self.column] = self.get()
        self.tv.insert('', str(rowid)[1:], values=item)
        self.tv.delete(rowid)
        self.destroy()

    def select_all(self, *ignore):
        ''' Set selection on the whole text '''
        self.selection_range(0, 'end')

        # returns 'break' to interrupt default key-bindings
        return 'break'
