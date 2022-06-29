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
from typing import List, Dict, Any, Type, Tuple

import pandas as pd
from pandas.errors import EmptyDataError

ui_queues: List[Queue] = []
ui_out_queue = Queue()

NORM_FONT = ("Helvetica", 10)
TODO_FILE = r'./A_todo_today.txt'
DONE_FILE = r'./done.txt'
SOME_DATA_FILE = r'./some_data.txt'
IP_FILE = r'./ip_addr_list.txt'
CLIPBOARD_FILE = r'./clipboard.txt'


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
        self.clipboard = cp

    @staticmethod
    def get_repr():
        return 'NewClipboardInfo'


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


class CreateServerEvent(Event):
    def __init__(self, port) -> None:
        self.port = port

    @staticmethod
    def get_repr():
        return 'CREATE_SERVER'

    def __repr__(self):
        return f'CREATE_SERVER On {self.port}'


class ServerCreatedEvent:
    def __init__(self, message) -> None:
        self.message = message


class MessageFromPeer(StrFromUi):
    def __init__(self, server, message) -> None:
        self.server = server
        super().__init__(message)


class MessageToPeer(Event):
    def __init__(self, server, message) -> None:
        self.server: str = server
        self.message: str = message

    @staticmethod
    def get_repr():
        return 'MESSAGE TO PEER'

    def __repr__(self):
        return self.message + ' -> ' + self.server


class FileUpdateEvent(Event):
    def __init__(self, update) -> None:
        self.update = update

    @staticmethod
    def get_repr():
        return 'FILE UPDATE'


#
#
# class DataFileUpdateEvent(FileUpdateEvent):
#     update: pd.DataFrame
#
#     @staticmethod
#     def get_repr():
#         return 'DATA FILE UPDATE'


class IPAddrListChangedEvent(FileUpdateEvent):
    @staticmethod
    def get_repr():
        return 'IP ADDR LIST CHANGED EVENT'


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


#
#
# class DataFileSubscriber(FileSubscriber):
#     def __init__(self, out_queues: List[Queue]):
#         super().__init__(out_queues)
#         self.state = None
#
#     async def _get_update(self) -> Any:
#         try:
#             df = pd.read_csv(self.get_file_name())
#         except EmptyDataError:
#             print('No data in data file')
#         else:
#             if not df.equals(self.state):
#                 self.state = df
#                 return self.get_type()(df)
#
#     def get_type(self) -> Type[FileUpdateEvent]:
#         return DataFileUpdateEvent
#
#     def get_file_name(self) -> str:
#         return SOME_DATA_FILE


class RandomSubscriber(Subscriber):
    def seconds_before_next_update(self) -> int:
        return 10

    async def _get_update(self) -> Any:
        return 'Ok'

    def get_type(self) -> Type[Event]:
        return RandomSubscriberEvent


class StrFromUiWorker(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return StrFromUi

    async def _process_message(self, message) -> Any:
        return message


class ServerWorker(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return CreateServerEvent

    async def _process_message(self, message: CreateServerEvent) -> Any:
        port = message.port
        server = await asyncio.start_server(self._handle_msg, '0.0.0.0', port)
        addr = server.sockets[0].getsockname()
        print(f'Serving on {addr}')

        async def serve():
            async with server:
                await server.serve_forever()

        loop = asyncio.get_event_loop()
        loop.create_task(serve())

        return ServerCreatedEvent(f'Serving on {addr}')

    async def _handle_msg(self, reader, writer):
        data = await reader.read(100)
        message = data.decode()
        addr = writer.get_extra_info('peername')

        # print(f'Received {message!r} from {addr!r}')
        ui_out_queue.put(MessageFromPeer(addr[0] + ':' + str(addr[1]), message))
        # print(f'Send {message!r}')
        writer.write(data)
        await writer.drain()

        # print('Close connection')
        writer.close()


class MessageToPeerWorker(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return MessageToPeer

    async def _process_message(self, message: MessageToPeer) -> Any:
        server, port = message.server.split(':')
        reader, writer = await asyncio.open_connection(server, int(port))

        # print(f'Send {message!r}')
        writer.write(message.message.encode())

        data = await reader.read(100)
        # print(f'Received {data.decode()!r}')

        # print('Close connection')
        writer.close()

        return StrFromUi('Message sent !')


class IpAddrListFileSubscriber(metaclass_resolver(FileSubscriber, WorkerMeta)):
    async def _get_update(self) -> Any:
        msg = await super()._get_update()
        if msg is not None:
            global config_ip_rows
            config_ip_rows = msg.update
        return msg

    def get_type(self) -> Type[FileUpdateEvent]:
        return IPAddrListChangedEvent

    def get_file_name(self) -> str:
        return IP_FILE


class TodoFileUpdate(FileUpdateEvent):
    update: List[str]

    @staticmethod
    def get_repr():
        return 'TODO FILE UPDATE'


class DoneFileUpdate(FileUpdateEvent):
    update: pd.DataFrame
    new_update: Tuple[str, str]

    def __init__(self, update, new_update) -> None:
        super().__init__(update)
        self.new_update = new_update

    @staticmethod
    def get_repr():
        return 'DONE FILE UPDATE'


class TodoFileSubscriber(metaclass_resolver(FileSubscriber, WorkerMeta)):
    def get_type(self) -> Type[FileUpdateEvent]:
        return TodoFileUpdate

    def get_file_name(self) -> str:
        return TODO_FILE


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


# ================= SET UP =================

# workers: List[Worker] = [
#     ClipboardListener(ui_queues),
#     StrFromUiWorker(ui_queues),
#     ServerWorker(ui_queues),
#     MessageToPeerWorker(ui_queues),
#     # DataFileSubscriber(ui_queues),
#     IpAddrListFileSubscriber(ui_queues),
#     TodoFileSubscriber(ui_queues),
#     DoneFileSubscriber(ui_queues)
# ]
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
lookup = {
    1: 'Main',
    2: 'Test',
    3: 'Server',
    4: 'Peer to peer',
    # 5: 'Data',
    6: 'Config',
    7: 'Todo',
    8: 'Done'
}


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


class MainContent(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        Label(self, text='Main content').pack()
        self.container = VerticalScrolledFrame(self)
        self.container.pack(expand=True, fill='both')

    def add(self, message: str):
        Label(self.container.interior, text=message).pack()
        self.container.canvas.update_idletasks()
        self.container.canvas.yview_moveto(1)


class TV(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        Label(self, text='Test').pack()
        self.entry = Entry(self)
        self.entry.pack()
        Button(self, text='Send event', command=self.send_event).pack()

    def send_event(self):
        msg = StrFromUi(self.entry.get())
        ui_out_queue.put(msg)


class ServerFrame(Frame):
    def __init__(self, parent, controller, *args, **kwargs):
        Frame.__init__(self, parent)
        self.controller = controller
        Label(self, text='Choose port').pack()
        self.port = StringVar(master=self)
        self.entry = Entry(self, textvariable=self.port)
        self.entry.pack()
        Button(self, text='Create server', command=self.create_server).pack()

    def create_server(self):
        self.controller.statusbar.set('Creating server for port ' + self.port.get())
        event = CreateServerEvent(self.port.get())
        ui_out_queue.put(event)


messages_by_peers: Dict[str, List[str]] = {}


class PeerToPeerFrame(Frame):
    def __init__(self, parent, controller, *args, **kwargs):
        self.parent = parent
        self.controller = controller
        Frame.__init__(self, parent)
        Label(self, text='Choose server:port').pack()
        self.addr = StringVar(master=self)
        self.server_entry = Entry(self, textvariable=self.addr)
        self.server_entry.pack()
        Label(self, text='Message to send :').pack()
        self.msg = StringVar(master=self)
        self.msg_entry = Entry(self, textvariable=self.msg)
        self.msg_entry.pack()
        Button(self, text='Send msg', command=self.send_msg).pack()

        self.menubar = Frame(self)
        self.menubar.pack()

        self.container = Frame(self)
        self.container.pack(expand=True, fill='x')
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.messages_thread_by_addr: Dict[str, VerticalScrolledFrame] = {}
        self.name_variable_by_addr: Dict[str, StringVar] = {}

        for addr in messages_by_peers:
            if addr not in self.name_variable_by_addr:
                self.name_variable_by_addr[addr] = StringVar(master=self)
            if addr not in self.messages_thread_by_addr:
                f = VerticalScrolledFrame(self.container)
                self.messages_thread_by_addr[addr] = f
                f.grid(row=0, column=0, sticky='nsew')
                Button(self.menubar, textvariable=self.name_variable_by_addr[addr],
                       command=lambda x=addr: self.switch(x)).pack(side=LEFT)
            messages = messages_by_peers[addr]
            for message in messages:
                Label(self.messages_thread_by_addr[addr].interior, text=message).pack()

        self._update_button_names(config_ip_rows)

    def send_msg(self):
        self.controller.statusbar.set('Sending msg...')
        self.get_msg(self.addr.get(), self.msg.get())
        ui_out_queue.put(MessageToPeer(self.addr.get(), self.msg.get()))
        self.controller.statusbar.set('Sent')

    def switch(self, value):
        f = self.messages_thread_by_addr.get(value)
        if f is not None:
            f.tkraise()
            self.addr.set(value + ':8888')
            self.msg.set('')

    def get_msg(self, addr, msg):
        port = None
        if ':' in addr:
            addr, port = addr.split(':')
        if addr not in self.name_variable_by_addr:
            self.name_variable_by_addr[addr] = StringVar(master=self)
        if addr not in self.messages_thread_by_addr:
            f = VerticalScrolledFrame(self.container)
            self.messages_thread_by_addr[addr] = f
            f.grid(row=0, column=0, sticky='nsew')
            Button(self.menubar, textvariable=self.name_variable_by_addr[addr],
                   command=lambda x=addr: self.switch(x)).pack(side=LEFT)
            messages_by_peers[addr] = []
        f = self.messages_thread_by_addr[addr]
        if port is not None:
            port = 'Me' if port == '8888' else 'Other'
            msg = port + ' : ' + msg
        Label(f.interior, text=msg).pack()
        messages_by_peers[addr].append(msg)
        f.tkraise()
        f.canvas.update_idletasks()
        f.canvas.yview_moveto(1)

    def update_button_names(self, message: IPAddrListChangedEvent):
        self._update_button_names(message.update)

    def _update_button_names(self, lst):
        lst = [i.split(',') for i in lst]
        d = {i[0]: i[1].strip() for i in lst}
        for ip in d:
            if ip not in self.name_variable_by_addr:
                self.get_msg(ip, '')
            self.name_variable_by_addr[ip].set(d[ip])


#
#
# class SomeDataFrame(Frame):
#     def __init__(self, parent):
#         Frame.__init__(self, parent)
#         container = Frame(self)
#         container.pack(expand=True, fill='both')
#         container.grid_rowconfigure(0, weight=1)
#         container.grid_columnconfigure(0, weight=1)
#         self.tree = Treeview(container)
#         self.tree.grid(row=0, column=0, sticky='nsew')
#         self.tree.bind('<<TreeviewSelect>>', self.item_selected)
#         scrollbar = Scrollbar(container, orient=VERTICAL, command=self.tree.yview)
#         self.tree.configure(yscroll=scrollbar.set)
#         scrollbar.grid(row=0, column=1, sticky='ns')
#
#     def item_selected(self, event):
#         for selected_item in self.tree.selection():
#             item = self.tree.item(selected_item)
#             record = [str(i) for i in item['values']]
#             # show a message
#             showinfo(title='Information', message=','.join(record))
#
#     def update_tree_view(self, update: DataFileUpdateEvent):
#         self.tree.delete(*self.tree.get_children())
#         df = update.update
#         self.tree['columns'] = list(df.columns)
#         self.tree['show'] = 'headings'
#         for i in df.columns:
#             self.tree.column(i, anchor="w", stretch=True, width=10)
#             self.tree.heading(i, text=i, anchor="w")
#         for index, row in df.iterrows():
#             self.tree.insert("", END, text=index, values=list(row))


class ConfigFrame(Frame):
    def __init__(self, parent, controller, *args, **kwargs):
        Frame.__init__(self, parent)
        self.controller = controller
        Button(self, text="Open file", command=lambda: open_file(IP_FILE)).pack()
        self.ip_addr_list_tree_view = Treeview(self)
        self.ip_addr_list_tree_view['show'] = 'headings'
        self.ip_addr_list_tree_view.pack(fill='x', expand=True)
        self._update_ip_addr_list(config_ip_rows)

    def update_ip_addr_list(self, message: IPAddrListChangedEvent):
        self._update_ip_addr_list(message.update)

    def _update_ip_addr_list(self, lst):
        self.ip_addr_list_tree_view.delete(*self.ip_addr_list_tree_view.get_children())
        cols = ['ip', 'name']
        self.ip_addr_list_tree_view['columns'] = cols
        self.ip_addr_list_tree_view['show'] = 'headings'
        for i in cols:
            self.ip_addr_list_tree_view.column(i, anchor="w", stretch=True, width=13)
            self.ip_addr_list_tree_view.heading(i, text=i, anchor="w")
        for i in lst:
            row = i.split(',')
            self.ip_addr_list_tree_view.insert("", END, values=row)
        self.controller.statusbar.set('Config updated')


class TodoFrame(Frame):
    def __init__(self, parent, controller, *args, **kwargs):
        Frame.__init__(self, parent)
        self.controller = controller
        self.container = VerticalScrolledFrame(self)
        Button(self, text="Open file", command=lambda: open_file(TODO_FILE)).pack()
        self.container.pack(expand=True, fill='x')

    def update_todos(self, message: TodoFileUpdate):
        for item in self.container.interior.winfo_children():
            item.destroy()
        for update in message.update:
            Label(self.container.interior, text=update.strip()).pack()


class DoneFrame(Frame):
    def __init__(self, parent, controller, *args, **kwargs):
        Frame.__init__(self, parent)
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


class Main(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent)
        self.navbar_shown = True
        self.statusbar = StatusBar(self)
        # self.toolbar = ToolBar(self)
        self.navbar = NavBar(self)
        container = Frame(self)
        self.main_content = MainContent(container)
        self.tview = TV(container)
        self.server_frame = ServerFrame(container, self)
        self.peer_to_peer = PeerToPeerFrame(container, self)
        # self.some_data_frame = SomeDataFrame(container)
        self.config_frame = ConfigFrame(container, self)
        self.todo_frame = TodoFrame(container, self)
        self.done_frame = DoneFrame(container, self)

        self.statusbar.pack(side='bottom', fill='x')
        # self.toolbar.pack(side='top', fill='x')
        self.navbar.pack(side='left', fill='y')
        container.pack(side='right', fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.main_content.grid(row=0, column=0, sticky='nsew')
        self.tview.grid(row=0, column=0, sticky='nsew')
        self.server_frame.grid(row=0, column=0, sticky='nsew')
        self.peer_to_peer.grid(row=0, column=0, sticky='nsew')
        # self.some_data_frame.grid(row=0, column=0, sticky='nsew')
        self.config_frame.grid(row=0, column=0, sticky='nsew')
        self.todo_frame.grid(row=0, column=0, sticky='nsew')
        self.done_frame.grid(row=0, column=0, sticky='nsew')
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
        menubar.add_cascade(label='Help', menu=helpmenu)
        menubar.add_command(label='New window', command=launch_daemon)

        Tk.config(self.master, menu=menubar)

        self.frames = {}
        lframes = [self.main_content, self.tview, self.server_frame, self.peer_to_peer, self.config_frame,
                   self.todo_frame, self.done_frame]
        lframes.extend(self.my_frames)
        for f in zip(lookup.values(), lframes):
            self.frames[f[0]] = f[1]

        self.switch_main('Main')

        self.master.after(100, self.process_queue)

    def process_queue(self):
        try:
            while not self.master.queue.empty():
                message = self.master.queue.get()
                if type(message) == str:
                    self.main_content.add(message)
                if type(message) == StrFromUi:
                    self.main_content.add(message.message)
                if type(message) == ServerCreatedEvent:
                    self.statusbar.set('Processing ServerCreatedEvent...')
                    Label(self.server_frame, text=message.message).pack()
                    self.statusbar.set('ServerCreatedEvent processed')
                if type(message) == MessageFromPeer:
                    self.statusbar.set('Receiving message from peer')
                    m = 'FROM ' + message.server + ' -> ' + message.message
                    Label(self.server_frame, text=m).pack()
                    self.main_content.add(m)
                    self.peer_to_peer.get_msg(message.server, message.message)
                if type(message) == FileUpdateEvent:
                    m = 'From file : ' + message.update
                    self.main_content.add(m)
                # if type(message) == DataFileUpdateEvent:
                #     self.some_data_frame.update_tree_view(message)
                if type(message) == IPAddrListChangedEvent:
                    self.statusbar.set('IP Addr list updating...')
                    self.config_frame.update_ip_addr_list(message)
                    self.peer_to_peer.update_button_names(message)
                    self.statusbar.set('IP Addr list changed')
                if type(message) == TodoFileUpdate:
                    self.statusbar.set('Todo file updating...')
                    self.todo_frame.update_todos(message)
                    self.statusbar.set('Todo file updated')
                if type(message) == DoneFileUpdate:
                    self.statusbar.set('Done file updating...')
                    self.done_frame.update_dones(message)
                    self.statusbar.set('Done file updated')
                if type(message) == ToggleSideBarEvent:
                    self.navbar_shown = not self.navbar_shown
                    if not self.navbar_shown:
                        self.navbar.pack_forget()
                    else:
                        self.navbar.pack(side='left', fill='y', after=self.statusbar)
                if type(message) == NewClipboardInfo:
                    self.statusbar.set(message.clipboard)
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
        self.bind('<Escape>', self._iconify)
        self.clipboard = None
        self.init = False
        self.after(1000, self.fetch_clipboard)

    def _key(self, event):
        self.queue.put(ToggleSideBarEvent())

    def _iconify(self, event):
        print('icon')
        self.iconify()

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
