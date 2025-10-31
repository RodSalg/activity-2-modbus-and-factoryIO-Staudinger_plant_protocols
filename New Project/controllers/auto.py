import time
import threading
from collections import deque
from addresses import Coils, Inputs

class AutoController:
    """
    Gerencia o ciclo automático e a feeder queue.
    Depende do 'server' para estado e IO.
    """
    def __init__(self, server, verbose: bool = True):
        self.server = server
        self.verbose = verbose
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._auto_cycle, name="auto-cycle", daemon=True)
        self._thread.start()

    def join(self, timeout: float = 2.0):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ---------- feeder ----------
    def _feeder_queue(self):
        fila = deque(["blue", "green", "empty"])
        print("minha fila: ", fila)
        while self.server.machine_state == "running" and not self.server.stop_event.is_set():
            for _ in range(len(fila)):
                tipo = fila[0]
                print(f"Checando: {tipo}")

                if tipo == "blue":
                    sensor = Coils.Sensor_2_Caixote_Azul
                elif tipo == "green":
                    sensor = Coils.Sensor_2_Caixote_Verde
                elif tipo == "empty":
                    sensor = Coils.Sensor_2_Caixote_Vazio
                else:
                    sensor = None

                if sensor is not None and self.server.get_sensor(sensor):
                    print(f"Ação tomada para: {tipo}")
                    time.sleep(7)  # manter como no original
                    fila.rotate(-1)
                    break
                else:
                    fila.rotate(-1)
            time.sleep(0.1)

    # ---------- ciclo automático ----------
    def _auto_cycle(self):
        if self.verbose:
            print("Ciclo automático iniciado")
        feeder = threading.Thread(target=self._feeder_queue, name="feeder", daemon=True)
        feeder.start()

        while self.server.machine_state == "running":
            step = self.server.sequence_step
            if step in ("idle", "wait_inspection", "sorter1", "sorter2", "exit_wait"):
                time.sleep(0.1)
            else:
                time.sleep(0.05)

        if self.verbose:
            print("Ciclo automático encerrado")
