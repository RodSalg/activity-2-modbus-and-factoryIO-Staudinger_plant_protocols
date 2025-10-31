import inspect
import time
import threading
from datetime import datetime
from typing import Optional, List
from pyModbusTCP.server import ModbusServer

from utils import Stoppable, now
from addresses import Inputs, Coils
from controllers.lines import LineController
from controllers.events import EventProcessor
from controllers.auto import AutoController


class FactoryModbusEventServer(Stoppable):
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5020,
        scan_time: float = 0.05,
        verbose: bool = True,
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.scan_time = scan_time
        self.verbose = verbose

        self._server: Optional[ModbusServer] = None
        self._event_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Estado de máquina
        self.machine_state = "emergency"
        self.sequence_step = "idle"

        # Controladores
        self.lines = LineController(self, verbose=verbose)
        self.auto = AutoController(self, verbose=verbose)
        self.events = EventProcessor(self, self.lines, verbose=verbose)

    # -------- lifecycle --------
    def start(self) -> None:
        if self._server is not None:
            return
        self._server = ModbusServer(host=self.host, port=self.port, no_block=True)
        self._server.start()

        self.stop_event.clear()
        self._event_thread = threading.Thread(
            target=self._event_loop, name="modbus-event-loop", daemon=True
        )
        self._event_thread.start()

        if self.verbose:
            print(f"\n[{now()}] Servidor Modbus em {self.host}:{self.port}")

    def stop(self) -> None:
        self.stop_event.set()
        if self._event_thread and self._event_thread.is_alive():
            self._event_thread.join(timeout=2.0)
        self.auto.join(timeout=2.0)
        if self._server:
            self._server.stop()
            self._server = None
        if self.verbose:
            print("Servidor parado.")

    # -------- helpers de acesso ao banco --------
    def _db(self):
        if not self._server:
            raise RuntimeError("Servidor não iniciado.")
        return self._server.data_bank

    def get_sensor(self, sensor_address: int) -> bool:
        db = self._db()
        return bool(db.get_coils(sensor_address, 1)[0])

    def set_actuator(self, coil_address: int, value: bool) -> None:
        print(
            f"[DEBUG ACTUATOR] {coil_address} <= {value}  (chamado por {inspect.stack()[1].function})"
        )
        db = self._db()
        db.set_discrete_inputs(coil_address, [int(value)])

    def _write_coil(self, addr: int, value: bool) -> None:
        db = self._db()
        with self._lock:
            db.set_coils(addr, [1 if value else 0])

    def _all_off(self) -> None:
        self._write_coil(Inputs.EntryConveyor, False)

    # -------- loop de eventos --------
    def _event_loop(self):
        db = self._db()
        while not self.stop_event.is_set():
            coils = db.get_coils(0, 120) or []
            if coils:
                self.events.handle_scan(coils)
            self.stop_event.wait(self.scan_time)

    # -------- handlers de botões (mantidos) --------
    def _on_start(self):
        if self.verbose:
            print("Start Line")
        if self.machine_state in ("emergency", "running"):
            return
        self.machine_state = "running"
        self.sequence_step = "idle"
        self.auto.start()

    def _on_stop(self):
        if self.verbose:
            print("Stop")
        self.machine_state = "idle"
        self._all_off()

    def _on_reset(self):
        if self.verbose:
            print("Reset")
        if self.get_sensor(Coils.Emergency) is True:
            self.sequence_step = "idle"
            self.machine_state = "idle"

            self._all_off()

    def _on_emergency_toggle(self):
        print("valor da emergencia: ", self.get_sensor(Coils.Emergency))

        # Emergência ON (coil False)
        if (
            self.machine_state != "emergency"
            and self.get_sensor(Coils.Emergency) is False
        ):
            if self.verbose:
                print("Emergency ON")
            self.machine_state = "emergency"
            self.sequence_step = "idle"
            self._all_off()

        # Emergência OFF (coil True) -> SAIR do estado 'emergency'
        elif (
            self.machine_state == "emergency"
            and self.get_sensor(Coils.Emergency) is True
        ):
            if self.verbose:
                print("Emergency OFF")
            self.machine_state = "idle"  # <-- faltava isso
            self.sequence_step = "idle"

    # -------- debug --------
    def snapshot(self):
        """Imprime o estado apenas se houver mudança desde a última amostra."""
        current_state = (self.machine_state, self.sequence_step)
        if not hasattr(self, "_last_snapshot_state"):
            self._last_snapshot_state = current_state
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] estado={self.machine_state} passo={self.sequence_step}"
            )
            print("=" * 60, "\n")
            return

        if current_state != self._last_snapshot_state:
            self._last_snapshot_state = current_state
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] estado={self.machine_state} passo={self.sequence_step}"
            )
            print("=" * 60, "\n")
