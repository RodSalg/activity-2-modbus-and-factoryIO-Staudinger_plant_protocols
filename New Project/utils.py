import threading
from datetime import datetime

def now():
    return datetime.now().isoformat(timespec="seconds")

class Stoppable:
    def __init__(self):
        self._stop_evt = threading.Event()

    @property
    def stop_event(self):
        return self._stop_evt

    def stopped(self) -> bool:
        return self._stop_evt.is_set()

    def stop(self) -> None:
        self._stop_evt.set()

