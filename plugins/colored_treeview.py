from tkinter import *
from tkinter.font import Font
from tkinter.ttk import *


class App(Frame):
    def __init__(self, parent, *args, **kwargs):
        Frame.__init__(self, parent, *args, **kwargs)

        self.tree = Treeview(parent, columns=("size", "modified"))
        self.tree["columns"] = ("date", "time", "loc")

        self.tree.column("#0", width=100, anchor='center')
        self.tree.column("date", width=100, anchor='center')
        self.tree.column("time", width=100, anchor='center')
        self.tree.column("loc", width=100, anchor='center')

        self.tree.heading("#0", text="Name")
        self.tree.heading("date", text="Date")
        self.tree.heading("time", text="Time")
        self.tree.heading("loc", text="Location")

        self.tree.insert("", "end", text="Grace", values=("2010-09-03", "03:44:53", "Garden"))
        self.tree.insert("", "end", text="John", values=("2017-02-05", "11:30:23", "Airport"))
        self.tree.insert("", "end", text="Betty", values=("2014-06-25", "10:00:00", ""))

        self.tree.grid()
        self.tree.bind('<ButtonRelease-1>', self.select_item)

        sel_bg = '#ecffc4'
        sel_fg = '#05640e'
        self.setup_selection(sel_bg, sel_fg)

    def setup_selection(self, sel_bg, sel_fg):
        self._font = Font()
        self._canvas = Canvas(self.tree, background=sel_bg, borderwidth=0, highlightthickness=0)
        self._canvas.text = self._canvas.create_text(0, 0, fill=sel_fg, anchor='w')

    def select_item(self, event):
        self._canvas.place_forget()
        x, y, widget = event.x, event.y, event.widget
        item = widget.item(widget.focus())
        item_text = item['text']
        item_values = item['values']
        iid = widget.identify_row(y)
        column = event.widget.identify_column(x)
        print('\n&&&&&&&&&& def select_item(self, event):')
        print('item = ', item)
        print('item_text = ', item_text)
        print('item_values = ', item_values)
        print('iid = ', iid)
        print('column = ', column)

        # Leave method if mouse pointer clicks on treeview area without data
        if not column or not iid:
            return

        # Leave method if selected item's value is empty
        if not len(item_values):
            return

        if column == '#0':
            self.cell_value = item_text
        else:
            self.cell_value = item_values[int(column[1]) - 1]
        print('column[1] = ', column[1])
        print('self.cell_value = ', self.cell_value)

        # Leave method if selected TreeView cell is empty
        if not self.cell_value:
            return

        # Get the bounding box of selected cell, a tuple (x, y, w, h) where
        # x, y are coordinates of the upper left corner of that cell relative
        # to the widget, and
        # w, h are width and height of the cell in pixels
        # if the item is not visible, the method returns an empty string
        bbox = widget.bbox(iid, column)
        print('bbox = ', bbox)
        if not bbox:
            return

        # Update and show selection in Canvas Overlay
        self.show_selection(widget, bbox, column)
        print('Selected Cell value = ', self.cell_value)

    def show_selection(self, parent, bbox, column):
        """ Configure canvas and canvas-textbox for a new selection. """
        print("@@@@@@@@@@ def show_selection(self, parent, bbox, column):")
        x, y, width, height = bbox
        fudgeTreeColumnx = 19
        fudgeColumnx = 15

        # Number of pixels of cell value in horizontal direction
        textw = self._font.measure(self.cell_value)
        print("textw = ", textw)

        # Make Canvas size to fit selected cell
        self._canvas.configure(width=width, height=height)

        # Position canvas-textbox in Canvas
        print('self._canvas.coords(self._canvas.text) = ', self._canvas.coords(self._canvas.text))
        if column == "#0":
            self._canvas.coords(self._canvas.text, fudgeTreeColumnx, height / 2)
        else:
            self._canvas.coords(self._canvas.text, (width - (textw - fudgeColumnx)) / 2.0, height / 2)

        # Update value of canvas-textbox with the value of the selected cell
        self._canvas.itemconfigure(self._canvas.text, text=self.cell_value)

        # Overlay Canvas over Treeview cell
        self._canvas.place(in_=parent, x=x, y=y)

if __name__ == '__main__':
    window = Tk()
    app = App(window)
    window.mainloop()
