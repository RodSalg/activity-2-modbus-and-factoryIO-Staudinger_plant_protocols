# auto.py
from queue import Queue
import threading, time
from addresses import Coils


class AutoController:
    def __init__(self, server, verbose: bool = True):
        self.server = server
        self.verbose = verbose
        self._thread = None

        from queue import Queue

        self.arrival_q: Queue[tuple[str, int]] = Queue()  # PADRÃO: (tipo, sensor)
        self._arrival_worker_th = None

        self.lines = self.server.lines

        # >>> ADICIONE ESTAS LINHAS <<<
        self.turntable_busy = False
        self.active_job = None

        self._pending_lock = threading.Lock()
        self._pending_enq = set()  # guarda sensor_addr em atraso

    def join(self, timeout=2.0):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        if self._arrival_worker_th and self._arrival_worker_th.is_alive():
            self._arrival_worker_th.join(timeout)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._auto_cycle, name="auto-cycle", daemon=True
        )
        self._thread.start()

        # inicia consumidor da fila de chegadas
        if not self._arrival_worker_th or not self._arrival_worker_th.is_alive():
            self._arrival_worker_th = threading.Thread(
                target=self._arrival_worker, name="arrival-worker", daemon=True
            )
            self._arrival_worker_th.start()

    # chamado pelos EVENTS (no edge do Sensor_2)
    def enqueue_arrival(self, tipo: str, sensor_addr: int):
        self.arrival_q.put((tipo, sensor_addr))
        if self.verbose:
            print(f"[arrival] enfileirado: {tipo} (sensor={sensor_addr})")

    def enqueue_arrival_delayed(
        self, tipo: str, sensor_addr: int, delay_s: float = 1.0
    ):
        """Agenda o enfileiramento para depois de delay_s, evitando duplicatas por sensor."""
        import threading

        with self._pending_lock:
            if sensor_addr in self._pending_enq:
                return  # já existe um agendamento pendente para este sensor
            self._pending_enq.add(sensor_addr)

        def _do_enqueue():
            try:
                self.enqueue_arrival(
                    tipo, sensor_addr
                )  # mantém o padrão (tipo, sensor)
            finally:
                with self._pending_lock:
                    self._pending_enq.discard(sensor_addr)

        t = threading.Timer(delay_s, _do_enqueue)
        t.daemon = True
        t.start()

    def _arrival_worker(self):
        stop_evt = getattr(self.server, "_stop_evt", None)

        # política por origem (ajuste livre)
        POLICY = {
            "blue": {
                "turn": None,
                "belt": "forward",
                "stop_limit": "back",
                "belt_tout": 3.0,
                "feed_delay": 0.8,
            },
            "green": {
                "turn": True,
                "belt": "forward",
                "stop_limit": "back",
                "belt_tout": 3.0,
                "feed_delay": 1.0,
            },
            "empty": {
                "turn": True,
                "belt": "backward",
                "stop_limit": "front",
                "belt_tout": 3.0,
                "feed_delay": 1.0,
            },
        }

        while not (stop_evt and stop_evt.is_set()):
            tipo, sensor_addr = self.arrival_q.get()

            # espere a mesa estar livre
            while self.turntable_busy and not (stop_evt and stop_evt.is_set()):
                time.sleep(0.01)

            self.turntable_busy = True
            self.active_job = tipo
            try:
                P = POLICY.get(tipo)
                if not P:
                    if self.verbose:
                        print(f"[arrival] tipo desconhecido: {tipo}")
                    continue

                # 1) LIGA MESA PRIMEIRO (giro + belt) com stop_limit da ORIGEM
                self.lines.set_turntable_async(
                    turn_on=P["turn"],
                    belt=P["belt"],
                    stop_limit=P["stop_limit"],  # <<< AQUI É O PONTO-CHAVE
                    belt_timeout_s=P["belt_tout"],
                )

                # 2) aguarda um pequeno intervalo ANTES de religar a esteira da linha
                t_dead = time.time() + P["feed_delay"]
                while time.time() < t_dead:
                    if (
                        stop_evt and stop_evt.is_set()
                    ) or self.server.machine_state != "running":
                        break
                    time.sleep(0.02)

                # 3) só então libera a linha de origem
                if self.server.machine_state == "running" and not (
                    stop_evt and stop_evt.is_set()
                ):
                    if tipo == "blue":
                        self.lines.run_blue_line()
                    elif tipo == "green":
                        self.lines.run_green_line()
                    elif tipo == "empty":
                        self.lines.run_empty_line()

                # 4) opcional: espere o watcher desligar o belt interno antes do próximo job
                fin_deadline = time.time() + (P["belt_tout"] + 0.7)
                while (
                    getattr(self.lines, "_belt_watching", False)
                    and time.time() < fin_deadline
                ):
                    if (
                        stop_evt and stop_evt.is_set()
                    ) or self.server.machine_state != "running":
                        break
                    time.sleep(0.02)

                time.sleep(0.05)  # anti-ricochete
            finally:
                self.active_job = None
                self.turntable_busy = False
                self.arrival_q.task_done()

    def _auto_cycle(self):
        if self.verbose:
            print("Ciclo automático iniciado")

        # se quiser manter o feeder antigo para outras lógicas, ele pode coexistir.
        # Senão, deixe apenas o arrival_worker.
        while self.server.machine_state == "running":
            time.sleep(0.1)

        if self.verbose:
            print("Ciclo automático encerrado")
