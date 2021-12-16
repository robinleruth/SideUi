import abc
import asyncio
import queue

from queue import Queue
from threading import Thread
from tkinter import ttk
from typing import List, Dict, Any, Type
from tkinter import *

ui_queues: List[Queue] = []
ui_out_queue = Queue()

NORM_FONT = ("Helvetica", 10)


# ================= EVENT =================

class Event(metaclass=abc.ABCMeta):
    @staticmethod
    @abc.abstractmethod
    def get_repr():
        pass


class RandomSubscriberEvent(Event):
    @staticmethod
    def get_repr():
        return 'RANDOM_SUBSCRIBER'


class StrFromUi(Event):
    def __init__(self, message: str) -> None:
        self.message = message

    @staticmethod
    def get_repr():
        return 'STR_FROM_UI'

    def __repr__(self):
        return self.message


# ================= WORKERS =================


class Worker(metaclass=abc.ABCMeta):
    def __init__(self, out_queues: List[Queue]):
        self.queues = out_queues
        self.in_queue = asyncio.Queue()

    async def tell(self, message):
        await self.in_queue.put(message)

    async def start(self):
        print(f'Worker for {self.get_type().get_repr()} init')
        while True:
            message = await self.in_queue.get()
            print(f'{message} received in {self.get_type().get_repr()}')
            result = await self._process_message(message)
            for q in self.queues:
                q.put(result)

    @abc.abstractmethod
    def get_type(self) -> Type[Event]:
        pass

    @abc.abstractmethod
    async def _process_message(self, message) -> Any:
        pass


class RandomSubscriber(Worker):
    async def _get_from_source(self):
        while True:
            await self.tell('Ok')
            await asyncio.sleep(3)

    async def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._get_from_source())
        await super().start()

    def get_type(self) -> Type[Event]:
        return RandomSubscriberEvent

    async def _process_message(self, message) -> Any:
        return message


class StrFromUiWorker(Worker):
    def get_type(self) -> Type[Event]:
        return StrFromUi

    async def _process_message(self, message) -> Any:
        return message


# ================= SET UP =================

workers: List[Worker] = [RandomSubscriber(ui_queues), StrFromUiWorker(ui_queues)]
workers_by_type: Dict[str, List[Worker]] = dict()


async def init_workers():
    lst = []
    for w in workers:
        lst.append(w)
        if w.get_type() not in workers_by_type:
            workers_by_type[w.get_type().get_repr()] = []
        workers_by_type[w.get_type().get_repr()].append(w)
    await asyncio.gather(*[w.start() for w in lst])

dispatcher_queue = asyncio.Queue()


async def populate_queue():
    print("populate_queue")
    while True:
        try:
            alert = ui_out_queue.get_nowait()
            await dispatcher_queue.put(alert)
        except queue.Empty:
            await asyncio.sleep(1)


async def dispatcher():
    print('Dispatcher init')
    while True:
        message: Event = await dispatcher_queue.get()
        workers = workers_by_type.get(message.get_repr())
        if workers is not None:
            for w in workers:
                await w.tell(message)
        else:
            print(f'No worker for type {message.get_repr()}')


def process_message_from_ui():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.create_task(init_workers())
    loop.create_task(populate_queue())
    loop.create_task(dispatcher())

    loop.run_forever()


get_message_thread = Thread(target=process_message_from_ui)
get_message_thread.daemon = True
get_message_thread.start()


# ================= UI =================

class NavBar(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        Label(self, text='Navbar').pack()
        self.var = IntVar(master=self)
        Radiobutton(self, text='Main', variable=self.var, value=1, command=self.test).pack()
        Radiobutton(self, text='TreeView', variable=self.var, value=2, command=self.test).pack()
        self.var.set(1)

        self.lookup = {
            1: 'Main',
            2: 'TreeView'
        }

    def test(self):
        self.parent.statusbar.set(self.var.get())
        self.parent.switch_main(self.lookup[self.var.get()])


class ToolBar(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        Label(self, text='Toolbar').pack()


class StatusBar(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.var = StringVar(master=self, value='Launching...')
        self.label = Label(self, textvariable=self.var)
        self.label.pack()
        self.set('Ready')

    def set(self, value):
        self.var.set(str(value))


class MainContent(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        Label(self, text='Main content').pack()


class TV(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        Label(self, text='TreeView').pack()
        self.entry = Entry(self)
        self.entry.pack()
        Button(self, text='Send event', command=self.send_event).pack()

    def send_event(self):
        msg = StrFromUi(self.entry.get())
        ui_out_queue.put(msg)


class Main(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.statusbar = StatusBar(self)
        self.toolbar = ToolBar(self)
        self.navbar = NavBar(self)
        container = Frame(self, width=400, height=400)
        self.main_content = MainContent(container)
        self.tview = TV(container)

        self.statusbar.pack(side='bottom', fill='x')
        self.toolbar.pack(side='top', fill='x')
        self.navbar.pack(side='left', fill='y')
        container.pack(side='right', fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.main_content.grid(row=0, column=0, sticky='nsew')
        self.tview.grid(row=0, column=0, sticky='nsew')

        menubar = Menu(container)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label='New window', command=launch_daemon)
        filemenu.add_separator()
        filemenu.add_command(label='Exit', command=quit)
        menubar.add_cascade(label='File', menu=filemenu)

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label='?', command=lambda: popupmsg('Not supported just yet'))
        menubar.add_cascade(label='Help', menu=helpmenu)

        Tk.config(self.master, menu=menubar)

        self.frames = {}
        for f in zip(('Main', 'TreeView'), (self.main_content, self.tview)):
            self.frames[f[0]] = f[1]

        self.switch_main('Main')

        self.master.after(100, self.process_queue)

    def process_queue(self):
        while not self.master.queue.empty():
            message = self.master.queue.get()
            if type(message) == str:
                Label(self.main_content, text=message).pack()
            elif type(message) == StrFromUi:
                Label(self.main_content, text=message.message).pack()
        self.master.after(100, self.process_queue)

    def switch_main(self, value):
        frame = self.frames.get(value)
        if frame is not None:
            frame.tkraise()


class App(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()
        ui_queues.append(self.queue)
        self.geometry('300x300')


def launch_ui():
    r = App()
    Main(r).pack(side='top', fill='both', expand=True)
    r.mainloop()


def launch_daemon():
    t = Thread(target=launch_ui)
    t.daemon = True
    t.start()


def popupmsg(msg):
    popup = Tk()

    def leavemini():
        popup.destroy()

    popup.wm_title("!")

    label = ttk.Label(popup, text=msg, font=NORM_FONT)
    label.pack(side="top", fill="x", pady=10)
    B1 = ttk.Button(popup, text="Okay", command=leavemini)
    B1.pack()

    popup.mainloop()


if __name__ == '__main__':
    launch_ui()
