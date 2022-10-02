import asyncio
import time
from functools import partial
from tkinter import *
from tkinter.ttk import *
from typing import *

import aiohttp
import pandas as pd
import datetime as dt

from app import *

url = r'http://127.0.0.1:5000/{}'
file = r''


class PRequest(Event):
    def __init__(self, ids: List[str]):
        self.ids = ids

    @staticmethod
    def get_repr():
        return 'PRequest'


class PResult(Event):
    def __init__(self, ids: List[Tuple[str, pd.DataFrame]], errors: List[str]):
        self.ids = ids
        self.errors = errors

    @staticmethod
    def get_repr():
        return 'PResult'


class W(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return PRequest

    async def _process_message(self, message: PRequest) -> Any:
        lst = []
        for i in message.ids:
            lst.append(do_smth(i))
        t = time.time()
        print('Launch')
        r = await asyncio.gather(*lst)
        print()
        print(time.time() - t)
        return PResult(list(zip(message.ids, r)), ["error1", "error2"])


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        Label(self, text='Requests').pack()
        self.txt = StringVar(master=self)
        self.entry = Entry(self, textvariable=self.txt)
        self.entry.pack()
        self.send_button = Button(self, text="Send", command=self.send_rq)
        self.send_button.pack()
        self.container = VerticalScrolledFrame(self)
        self.container.pack(expand=True, fill='both')

    def send_rq(self):
        ui_out_queue.put(PRequest(self.txt.get().split(",")))

    def get_types(self) -> List[Type[Event]]:
        return [PResult]

    def process(self, message: PResult):
        for error in message.errors:
            Label(self.container.interior, text=error).pack()
        self.container.canvas.update_idletasks()
        self.container.canvas.yview_moveto(1)
        for result in message.ids:
            Label(self.container.interior, text=result[0]).pack()
            self.create_treeview(result[1])

    @staticmethod
    def get_name():
        return 'A'

    def create_treeview(self, data=None):
        sv = StringVar(master=self)
        e = Entry(self.container.interior, textvariable=sv)
        e.pack()
        container = Frame(self.container.interior)
        container.pack(expand=True, fill='both')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        tree = MyTreeview(container)
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

        # def on_double_click(t: Treeview):
        #     ep: EntryPopup = None
        #
        #     def inner(event):
        #         nonlocal ep
        #         if ep is not None:
        #             ep.destroy()
        #         row_id = t.identify_row(event.y)
        #         if not row_id:
        #             return
        #         column = t.identify_column(event.x)
        #         x, y, width, height = t.bbox(row_id, column)
        #         pady = height // 2
        #         text = t.item(row_id, 'values')[int(column[1:]) - 1]
        #         ep = EntryPopup(t, row_id, int(column[1:]) - 1, text)
        #         ep.place(x=x, y=y + pady, anchor=W, width=width, height=height)

            return inner

        e.bind('<Return>', on_filter())
        # tree.bind('<Double-Button-1>', on_double_click(tree))

    @staticmethod
    def update_treeview(tree, df: pd.DataFrame):
        tree.delete(*tree.get_children())
        tree['columns'] = list(df.columns)
        tree['show'] = 'headings'
        for i in df.columns:
            tree.column(i, anchor="w", stretch=True, width=10)
            tree.heading(i, text=i, anchor="w", sort_by='num')
        for index, row in df.iterrows():
            tree.insert("", END, text=index, values=list(row))


async def do_smth(_id: str):
    try:
        u = url.format(_id)
        async with aiohttp.ClientSession(read_timeout=None) as s:
            r = await s.get(u)
            lst = await r.json()
            if len(lst) == 0:
                print('to handle')
            else:
                lst = pd.DataFrame(lst)
                return lst
    except Exception as e:
        print('ERROR :', e)


class MyTreeview(Treeview):
    def heading(self, column, sort_by=None, **kwargs):
        if sort_by and not hasattr(kwargs, 'command'):
            func = getattr(self, f"_sort_by_{sort_by}", None)
            if func:
                kwargs['command'] = partial(func, column, False)
            # End of if
        # End of if
        return super().heading(column, **kwargs)

    # End of heading()

    def _sort(self, column, reverse, data_type, callback):
        l = [(self.set(k, column), k) for k in self.get_children('')]
        l.sort(key=lambda t: data_type(t[0]), reverse=reverse)
        for index, (_, k) in enumerate(l):
            self.move(k, '', index)
        # End of for loop
        self.heading(column, command=partial(callback, column, not reverse))

    # End of _sort()

    def _sort_by_num(self, column, reverse):
        self._sort(column, reverse, int, self._sort_by_num)

    # End of _sort_by_num()

    def _sort_by_name(self, column, reverse):
        self._sort(column, reverse, str, self._sort_by_name)

    # End of _sort_by_num()

    def _sort_by_date(self, column, reverse):
        def _str_to_datetime(string):
            return dt.datetime.strptime(string, "%Y-%m-%d")

        # End of _str_to_datetime()

        self._sort(column, reverse, _str_to_datetime, self._sort_by_date)

    # End of _sort_by_num()

    def _sort_by_multidecimal(self, column, reverse):
        def _multidecimal_to_str(string):
            arrString = string.split(".")
            strNum = ""
            for iValue in arrString:
                strValue = f"{int(iValue):02}"
                strNum = "".join([strNum, str(strValue)])
            # End of for loop
            strNum = "".join([strNum, "0000000"])
            return int(strNum[:8])

        # End of _multidecimal_to_str()

        self._sort(column, reverse, _multidecimal_to_str, self._sort_by_multidecimal)

    # End of _sort_by_num()

    def _sort_by_numcomma(self, column, reverse):
        def _numcomma_to_num(string):
            return int(string.replace(",", ""))

        # End of _numcomma_to_num()

        self._sort(column, reverse, _numcomma_to_num, self._sort_by_numcomma)
    # End of _sort_by_num()


# End of class MyTreeview


if __name__ == '__main__':
    root = Tk()
    m = Frame(root)
    m.pack()
    F(m, m).pack()
    root.mainloop()
