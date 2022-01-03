import abc
import asyncio
import os
import pandas as pd
from queue import Queue
from threading import Thread
from tkinter import *
from tkinter import ttk
from typing import List, Dict, Any, Type

from pandas.errors import EmptyDataError

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


class DataFileUpdateEvent(FileUpdateEvent):
    update: pd.DataFrame

    @staticmethod
    def get_repr():
        return 'CONFIG FILE UPDATE'


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


class Subscriber(Worker, metaclass=abc.ABCMeta):
    async def _get_from_source(self):
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


class FileSubscriber(Subscriber, metaclass=abc.ABCMeta):
    async def start(self):
        if not os.path.exists(self.get_file_name()):
            open(self.get_file_name(), 'w').close()
        return await super().start()

    def seconds_before_next_update(self) -> int:
        return 1

    async def _get_update(self) -> Any:
        with open(self.get_file_name(), 'r') as f:
            update = f.read()
        if update != self.get_file_name() and update != '':
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


class DataFileSubscriber(FileSubscriber):
    def __init__(self, out_queues: List[Queue]):
        super().__init__(out_queues)
        self.state = None

    async def _get_update(self) -> Any:
        try:
            df = pd.read_csv(self.get_file_name())
        except EmptyDataError:
            print('No data in data file')
        else:
            if not df.equals(self.state):
                self.state = df
                return self.get_type()(df)

    def get_type(self) -> Type[FileUpdateEvent]:
        return DataFileUpdateEvent

    def get_file_name(self) -> str:
        return 'some_data.txt'


class RandomSubscriber(Subscriber):
    def seconds_before_next_update(self) -> int:
        return 10

    async def _get_update(self) -> Any:
        return 'Ok'

    def get_type(self) -> Type[Event]:
        return RandomSubscriberEvent


class StrFromUiWorker(Worker):
    def get_type(self) -> Type[Event]:
        return StrFromUi

    async def _process_message(self, message) -> Any:
        return message


class ServerWorker(Worker):
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


class MessageToPeerWorker(Worker):
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


# ================= SET UP =================

workers: List[Worker] = [
    StrFromUiWorker(ui_queues),
    ServerWorker(ui_queues),
    MessageToPeerWorker(ui_queues),
    DataFileSubscriber(ui_queues)
]
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
        if not ui_out_queue.empty():
            alert = ui_out_queue.get_nowait()
            await dispatcher_queue.put(alert)
        else:
            await asyncio.sleep(0.5)


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


# ================= UI =================

class NavBar(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        Label(self, text='Navbar').pack()
        self.var = IntVar(master=self)
        Radiobutton(self, text='Main', variable=self.var, value=1, command=self.switch).pack()
        Radiobutton(self, text='Test', variable=self.var, value=2, command=self.switch).pack()
        Radiobutton(self, text='Server', variable=self.var, value=3, command=self.switch).pack()
        Radiobutton(self, text='Peer to peer', variable=self.var, value=4, command=self.switch).pack()
        Radiobutton(self, text='Data', variable=self.var, value=5, command=self.switch).pack()
        Radiobutton(self, text='Config', variable=self.var, value=6, command=self.switch).pack()
        self.var.set(1)

        self.lookup = {
            1: 'Main',
            2: 'Test',
            3: 'Server',
            4: 'Peer to peer',
            5: 'Data',
            6: 'Config'
        }

    def switch(self):
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
        Label(self, text='Test').pack()
        self.entry = Entry(self)
        self.entry.pack()
        Button(self, text='Send event', command=self.send_event).pack()

    def send_event(self):
        msg = StrFromUi(self.entry.get())
        ui_out_queue.put(msg)


class ServerFrame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        Label(self, text='Choose port').pack()
        self.port = StringVar(master=self)
        self.entry = Entry(self, textvariable=self.port)
        self.entry.pack()
        Button(self, text='Create server', command=self.create_server).pack()

    def create_server(self):
        event = CreateServerEvent(self.port.get())
        ui_out_queue.put(event)


messages_by_peers: Dict[str, List[str]] = {}


class PeerToPeerFrame(Frame):
    def __init__(self, parent):
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
        self.container.pack()
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.messages_thread_by_addr = {}

        for addr in messages_by_peers:
            if addr not in self.messages_thread_by_addr:
                f = Frame(self.container)
                self.messages_thread_by_addr[addr] = f
                f.grid(row=0, column=0, sticky='nsew')
                Button(self.menubar, text=addr, command=lambda x=addr: self.switch(x)).pack(side=LEFT)
            messages = messages_by_peers[addr]
            for message in messages:
                Label(self.messages_thread_by_addr[addr], text=message).pack()

    def send_msg(self):
        self.get_msg(self.addr.get(), self.msg.get())
        ui_out_queue.put(MessageToPeer(self.addr.get(), self.msg.get()))

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
        if addr not in self.messages_thread_by_addr:
            f = Frame(self.container)
            self.messages_thread_by_addr[addr] = f
            f.grid(row=0, column=0, sticky='nsew')
            Button(self.menubar, text=addr, command=lambda x=addr: self.switch(x)).pack(side=LEFT)
            messages_by_peers[addr] = []
        f = self.messages_thread_by_addr[addr]
        if port is not None:
            msg = port + ' : ' + msg
        Label(f, text=msg).pack()
        messages_by_peers[addr].append(msg)
        f.tkraise()


class SomeDataFrame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.tree = ttk.Treeview(self)
        self.tree.pack()

    def update_tree_view(self, update: DataFileUpdateEvent):
        self.tree.delete(*self.tree.get_children())
        df = update.update
        self.tree['columns'] = list(df.columns)
        for i in df.columns:
            self.tree.column(i, anchor="w")
            self.tree.heading(i, text=i, anchor="w")
        for index, row in df.iterrows():
            self.tree.insert("", 0, text=index, values=list(row))


class ConfigFrame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)


class Main(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.statusbar = StatusBar(self)
        self.toolbar = ToolBar(self)
        self.navbar = NavBar(self)
        container = Frame(self, width=400, height=400)
        self.main_content = MainContent(container)
        self.tview = TV(container)
        self.server_frame = ServerFrame(container)
        self.peer_to_peer = PeerToPeerFrame(container)
        self.some_data_frame = SomeDataFrame(container)
        self.config_frame = ConfigFrame(container)

        self.statusbar.pack(side='bottom', fill='x')
        self.toolbar.pack(side='top', fill='x')
        self.navbar.pack(side='left', fill='y')
        container.pack(side='right', fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.main_content.grid(row=0, column=0, sticky='nsew')
        self.tview.grid(row=0, column=0, sticky='nsew')
        self.server_frame.grid(row=0, column=0, sticky='nsew')
        self.peer_to_peer.grid(row=0, column=0, sticky='nsew')
        self.some_data_frame.grid(row=0, column=0, sticky='nsew')
        self.config_frame.grid(row=0, column=0, sticky='nsew')

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
        for f in zip(('Main', 'Test', 'Server', 'Peer to peer', 'Data', 'Config'),
                     (self.main_content, self.tview, self.server_frame, self.peer_to_peer, self.some_data_frame, self.config_frame)):
            self.frames[f[0]] = f[1]

        self.switch_main('Main')

        self.master.after(100, self.process_queue)

    def process_queue(self):
        while not self.master.queue.empty():
            message = self.master.queue.get()
            if type(message) == str:
                Label(self.main_content, text=message).pack()
            if type(message) == StrFromUi:
                Label(self.main_content, text=message.message).pack()
            if type(message) == ServerCreatedEvent:
                Label(self.server_frame, text=message.message).pack()
            if type(message) == MessageFromPeer:
                m = 'FROM ' + message.server + ' -> ' + message.message
                Label(self.server_frame, text=m).pack()
                Label(self.main_content, text=m).pack()
                self.peer_to_peer.get_msg(message.server, message.message)
            if type(message) == FileUpdateEvent:
                m = 'From file : ' + message.update
                Label(self.main_content, text=m).pack()
            if type(message) == DataFileUpdateEvent:
                self.some_data_frame.update_tree_view(message)
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
        self.wm_title('Side')


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
    get_message_thread = Thread(target=process_message_from_ui)
    get_message_thread.daemon = True
    get_message_thread.start()
    ui_out_queue.put(CreateServerEvent('8888'))
    launch_ui()
