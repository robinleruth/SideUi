import datetime as dt
from tkinter import *
from tkinter.ttk import *
from typing import *

import matplotlib
import pandas as pd

from app import *

matplotlib.use('TkAgg')
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib import pyplot as plt
from matplotlib import style
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
import numpy as np

style.use('ggplot')

f = plt.figure()
REFRESH_RATE = 1000
DAT_COUNTER = 9000


class Quote(Event):
    def __init__(self, timestamp: dt.datetime, price: float, quantity: float, way: str):
        self.timestamp = timestamp
        self.price = price
        self.quantity = quantity
        self.way = way

    @staticmethod
    def get_repr():
        return 'Graph'

    @property
    def serialize(self):
        return {
            'timestamp': self.timestamp,
            'price': self.price,
            'quantity': self.quantity,
            'way': self.way
        }


class W(metaclass_resolver(Worker, WorkerMeta)):
    def get_type(self) -> Type[Event]:
        return Quote

    async def _process_message(self, message) -> Any:
        return message


class F(MyFrame):
    def __init__(self, parent, controller):
        Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        now = dt.datetime.now()
        self.quotes: List[Quote] = []
        self.ani = animation.FuncAnimation(f, animate, interval=REFRESH_RATE, fargs=(self,))
        canvas = FigureCanvasTkAgg(f, self)
        canvas.draw()
        canvas.get_tk_widget().pack(side=BOTTOM, fill=BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(canvas, self)
        toolbar.update()
        canvas._tkcanvas.pack(side=BOTTOM, fill=BOTH, expand=1)

        self.controller.master.after(1000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=1), 2.0, 10, 'bid')))
        self.controller.master.after(1000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=1), 3.0, 10, 'ask')))
        self.controller.master.after(2000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=2), 1.5, 5, 'bid')))
        self.controller.master.after(2000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=2), 3.6, 15, 'ask')))
        self.controller.master.after(3000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=3), 2.5, 25, 'bid')))
        self.controller.master.after(4000, lambda: ui_out_queue.put(Quote(now + dt.timedelta(seconds=4), 2.6, 35, 'ask')))

    def get_types(self) -> List[Type[Event]]:
        return [Quote]

    def process(self, message: Quote):
        self.quotes.append(message)

    @staticmethod
    def get_name():
        return 'Graph'


def animate(frame, *fargs):
    try:
        obj = fargs[0]
        data = pd.DataFrame([i.__dict__ for i in obj.quotes], columns=['timestamp', 'price', 'quantity', 'way'])
        a = plt.subplot2grid((6, 4), (0, 0), rowspan=5, colspan=4)
        a2 = plt.subplot2grid((6, 4), (5, 0), rowspan=1, colspan=4, sharex=a)
        data["datestamp"] = np.array(data['timestamp']).astype('datetime64[s]')
        allDates = data["datestamp"].tolist()

        buys = data[(data['way'] == 'bid')]
        # buys["datestamp"] = np.array(buys['timestamp']).astype('datetime64[s]')
        buyDates = (buys["datestamp"]).tolist()

        sells = data[(data['way'] == 'ask')]
        # sells["datestamp"] = np.array(sells['timestamp']).astype('datetime64[s]')
        sellDates = (sells["datestamp"]).tolist()

        volume = data["quantity"]

        a.clear()

        a.plot_date(buyDates, buys["price"], '#00A3E0', label="buys")
        a.plot_date(sellDates, sells["price"], '#183A54', label="sells")
        a2.fill_between(allDates, 0, volume, facecolor='#183A54')
        a.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=2, borderaxespad=0.)

        a.xaxis.set_major_locator(mticker.MaxNLocator(5))
        a.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.setp(a.get_xticklabels(), visible=False)

        title = ' Tick Data\nLast Price: ' + str(data["price"][0])
        a.set_title(title)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    root = Tk()
    m = Frame(root)
    m.pack()
    F(m, m).pack()
    root.mainloop()
