import abc
import asyncio
import queue

from queue import Queue
from threading import Thread
from typing import List, Dict, Any, Type
from tkinter import *

ui_queues: List[Queue] = []
ui_out_queue = Queue()


class Event(metaclass=abc.ABCMeta):
    @staticmethod
    @abc.abstractmethod
    def get_repr():
        pass


class RandomSubscriberEvent(Event):
    @staticmethod
    def get_repr():
        return 'RANDOM_SUBSCRIBER'


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
            await asyncio.sleep(1)

    async def start(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._get_from_source())
        await super().start()

    def get_type(self) -> Type[Event]:
        return RandomSubscriberEvent

    async def _process_message(self, message) -> Any:
        return message


workers: List[Worker] = [RandomSubscriber(ui_queues)]
workers_by_type: Dict[str, List[Worker]] = dict()


async def init_workers():
    for w in workers:
        await w.start()
        if w.get_type() not in workers_by_type:
            workers_by_type[w.get_type().get_repr()] = []
        workers_by_type[w.get_type().get_repr()].append(w)

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
            print('No worker for type {}', type(message))


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


class App(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


if __name__ == '__main__':
    App().mainloop()
