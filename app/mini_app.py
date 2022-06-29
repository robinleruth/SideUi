import abc
import asyncio
import datetime as dt
import os
import pdb
import platform
import subprocess
import sys
import traceback
from queue import Queue
from threading import Thread
from tkinter import *
from tkinter.ttk import *
from typing import List, Dict, Any, Type

ui_queues: List[Queue] = []
ui_out_queue = Queue()

NORM_FONT = ("Helvetica", 10)


# ================= UTIL =================


def open_file(file_name):
    if platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', file_name))
    elif platform.system() == 'Windows':  # Windows
        os.startfile(file_name)
    else:  # linux variants
        subprocess.call(['gnome-terminal', '--', 'vim', file_name])


def metaclass_resolver(*classes):
    metaclass = tuple(set(type(cls) for cls in classes))
    metaclass = metaclass[0] if len(metaclass) == 1 \
        else type("_".join(mcls.__name__ for mcls in metaclass), metaclass, {})  # class M_C
    return metaclass("_".join(cls.__name__ for cls in classes), classes, {})


# ================= EVENT =================
class ToggleSideBarEvent:
    pass


class Event(metaclass=abc.ABCMeta):
    @staticmethod
    @abc.abstractmethod
    def get_repr():
        pass


class NewClipboardInfo(Event):
    def __init__(self, cp):
        self.cp = cp

    @staticmethod
    def get_repr():
        return 'NewClipboardInfo'


class FileUpdateEvent(Event):
    def __init__(self, update) -> None:
        self.update = update

    @staticmethod
    def get_repr():
        return 'FILE UPDATE'


# ================= WORKERS =================


class Worker(metaclass=abc.ABCMeta):
    def __init__(self, out_queues: List[Queue]):
        self.queues = out_queues
        self.in_queue = None
        self.buffer_queue = Queue()

    async def tell(self, message):
        if self.in_queue is not None:
            await self.in_queue.put(message)
        else:
            self.buffer_queue.put(message)

    async def start(self):
        print(f'Worker for {self.get_type().get_repr()} init')
        self.in_queue = asyncio.Queue()
        while not self.buffer_queue.empty():
            await self.tell(self.buffer_queue.get())
        while True:
            message = await self.in_queue.get()
            print(f'{message} received in {self.get_type().get_repr()}')
            try:
                result = await self._process_message(message)
                for q in self.queues:
                    q.put(result)
            except Exception as e:
                print('ERROR : ', e)

    @abc.abstractmethod
    def get_type(self) -> Type[Event]:
        pass

    @abc.abstractmethod
    async def _process_message(self, message) -> Any:
        pass


workers: List[Worker] = []


def register_instance(inst):
    global workers
    workers.append(inst)


class M_WorkerMeta(type):
    def __new__(cls, name, base, attrs):
        worker_cls = super().__new__(cls, name, base, attrs)
        try:
            w = worker_cls(ui_queues)
            register_instance(w)
        except Exception as e:
            print('ERR Worker META, ', e)
        return worker_cls


class WorkerMeta(metaclass=M_WorkerMeta):
    pass


class Subscriber(Worker):
    async def _get_from_source(self):
        await asyncio.sleep(1)
        while True:
            update = await self._get_update()
            if update is not None:
                await self.tell(update)
            await asyncio.sleep(self.seconds_before_next_update())

    async def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._get_from_source())
        await super().start()

    async def _process_message(self, message) -> Any:
        return message

    @abc.abstractmethod
    def seconds_before_next_update(self) -> int:
        pass

    @abc.abstractmethod
    async def _get_update(self) -> Any:
        pass


class FileSubscriber(Subscriber):
    def __init__(self, out_queues: List[Queue]):
        super().__init__(out_queues)
        self.state = None

    async def start(self):
        if not os.path.exists(self.get_file_name()):
            open(self.get_file_name(), 'w').close()
        return await super().start()

    def seconds_before_next_update(self) -> int:
        return 1

    async def _get_update(self) -> Any:
        with open(self.get_file_name(), 'r') as f:
            update = f.readlines()
        if update != self.state and update != []:
            self.state = update
            return self.get_type()(update)
        else:
            return None

    @abc.abstractmethod
    def get_type(self) -> Type[FileUpdateEvent]:
        pass

    @abc.abstractmethod
    def get_file_name(self) -> str:
        pass


# ================= SET UP =================
workers_by_type: Dict[str, List[Worker]] = dict()
config_ip_rows = []


async def init_workers():
    lst = []
    for w in workers:
        try:
            if w.get_type() not in workers_by_type:
                workers_by_type[w.get_type().get_repr()] = []
            workers_by_type[w.get_type().get_repr()].append(w)
            lst.append(w)
        except AttributeError:
            pass
    await asyncio.gather(*[w.start() for w in lst])


async def populate_queue(dispatcher_queue):
    print("populate_queue")
    while True:
        if not ui_out_queue.empty():
            alert = ui_out_queue.get_nowait()
            await dispatcher_queue.put(alert)
        else:
            await asyncio.sleep(0.5)


async def dispatcher(dispatcher_queue):
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

    # dispatcher_queue = asyncio.Queue(loop=loop)
    dispatcher_queue = asyncio.Queue()

    loop.create_task(init_workers())
    loop.create_task(populate_queue(dispatcher_queue))
    loop.create_task(dispatcher(dispatcher_queue))

    loop.run_forever()


def get_all_files_subscribers() -> List[FileSubscriber]:
    return [i for i in workers if isinstance(i, FileSubscriber)]


# ================= UI =================


frames_ctor = []
lookup = {}


def register_frame(f):
    global frames_ctor
    frames_ctor.append(f)


class FrameMeta(type):
    n = 9

    def __new__(cls, name, base, attrs):
        c = super().__new__(cls, name, base, attrs)
        n = getattr(c, 'get_name')()
        if n is not None:
            register_frame(c)
            lookup[cls.n] = getattr(c, 'get_name')()
            cls.n = cls.n + 1
        return c


class MyFrame(Frame, metaclass=FrameMeta):
    def get_types(self) -> List[Type[Event]]:
        pass

    def process(self, message: Event):
        pass

    @staticmethod
    def get_name():
        pass


class VerticalScrolledFrame(Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling

    """

    def __init__(self, parent, *args, **kw):
        Frame.__init__(self, parent, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        self.vscrollbar = vscrollbar = Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        self.canvas = canvas = Canvas(self, bd=0, highlightthickness=0,
                                      yscrollcommand=vscrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior, anchor=NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        canvas.bind('<Configure>', _configure_canvas)


class NavBar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        self.parent = parent
        Label(self, text='=====').pack()
        self.var = IntVar(master=self)
        for k in lookup:
            Radiobutton(self, text=lookup[k], variable=self.var, value=k, command=self.switch).pack()
        self.var.set(1)

    def switch(self):
        # self.parent.statusbar.set(self.var.get())
        self.parent.switch_main(lookup[self.var.get()])


class ToolBar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        Label(self, text='Toolbar').pack()


class StatusBar(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        self.var = StringVar(master=self, value='Launching...')
        self.label = Label(self, textvariable=self.var)
        self.label.pack()
        self.set('Ready')

    def set(self, value):
        self.var.set(str(value))



class Main(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        self.navbar_shown = True
        self.statusbar = StatusBar(self)
        # self.toolbar = ToolBar(self)
        self.navbar = NavBar(self)
        container = Frame(self)

        self.statusbar.pack(side='bottom', fill='x')
        self.navbar.pack(side='left', fill='y')
        container.pack(side='right', fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.load_plugins()
        self.my_frames = []

        for f_ctor in frames_ctor:
            f_inst = f_ctor(container, self)
            f_inst.grid(row=0, column=0, sticky='nsew')
            self.my_frames.append(f_inst)

        menubar = Menu(container)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label='New window', command=launch_daemon)
        filemenu.add_separator()
        filemenu.add_command(label='Exit', command=quit)
        menubar.add_cascade(label='File', menu=filemenu)

        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label='?', command=lambda: popupmsg('Not supported just yet'))
        # menubar.add_cascade(label='Help', menu=helpmenu)
        menubar.add_command(label='New window', command=launch_daemon)

        Tk.config(self.master, menu=menubar)

        self.frames = {}
        lframes = []
        lframes.extend(self.my_frames)
        for f in zip(lookup.values(), lframes):
            self.frames[f[0]] = f[1]

        self.switch_main('Main')

        self.master.after(100, self.process_queue)

    def process_queue(self):
        try:
            while not self.master.queue.empty():
                message = self.master.queue.get()
                if type(message) == ToggleSideBarEvent:
                    self.navbar_shown = not self.navbar_shown
                    if not self.navbar_shown:
                        self.navbar.pack_forget()
                    else:
                        self.navbar.pack(side='left', fill='y', after=self.statusbar)
                for f in self.my_frames:
                    self.process(f, message)
        except Exception:
            extype, val, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)
        finally:
            self.master.after(100, self.process_queue)

    def switch_main(self, value):
        frame = self.frames.get(value)
        if frame is not None:
            frame.tkraise()

    def process(self, f: MyFrame, e: Event):
        if type(e) in f.get_types():
            f.process(e)

    def load_plugins(self):
        pass


class App(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()
        ui_queues.append(self.queue)
        self.geometry('200x300')
        self.wm_title('Side')
        self.lift()
        self.attributes('-topmost', True)
        self.bind('<Control-t>', self._key)
        self.clipboard = None
        self.init = False
        self.after(1000, self.fetch_clipboard)

    def _key(self, event):
        self.queue.put(ToggleSideBarEvent())

    def fetch_clipboard(self):
        t = self._get_clipboard()
        if t != self.clipboard:
            self.clipboard = t
            if self.init:
                ui_out_queue.put(NewClipboardInfo(self.clipboard))
        self.init = True
        self.after(1000, self.fetch_clipboard)

    def _get_clipboard(self):
        try:
            return self.clipboard_get()
        except Exception as e:
            pass


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

    label = Label(popup, text=msg, font=NORM_FONT)
    label.pack(side="top", fill="x", pady=10)
    b = Button(popup, text="Okay", command=leavemini)
    b.pack()

    popup.mainloop()


if __name__ == '__main__':
    get_message_thread = Thread(target=process_message_from_ui)
    get_message_thread.daemon = True
    get_message_thread.start()
    # ui_out_queue.put(CreateServerEvent('8888'))
    launch_ui()
