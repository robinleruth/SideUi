from threading import Thread

from app import launch_ui, process_message_from_ui, workers

import plugins
get_message_thread = Thread(target=process_message_from_ui)
get_message_thread.daemon = True
get_message_thread.start()
# ui_out_queue.put(CreateServerEvent('8888'))
launch_ui()
