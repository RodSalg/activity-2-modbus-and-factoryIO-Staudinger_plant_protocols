# lines.py
import threading
from addresses import Coils, Inputs


class LineController:
    def __init__(self, server, verbose: bool = True):
        self.server = server
        self.verbose = verbose
        self._blue_running = False
        self._green_running = False
        self._empty_running = False
        self._lock = threading.Lock()

    # Helpers de IO
    def _activate(self, *actuators):
        with self._lock:
            for a in actuators:
                self.server.set_actuator(a, True)

    def _deactivate(self, *actuators):
        with self._lock:
            for a in actuators:
                self.server.set_actuator(a, False)

    # ================= BLUE =================

    def run_blue_line(self):
        if self.server.machine_state != "running":
            return
        if self.verbose:
            print("ligando linha azul")
        # >>> CRIA A TASK DO RUN <<<
        threading.Thread(
            target=self._t_run_blue_line, name="TRUN-BlueLine", daemon=True
        ).start()

    def stop_blue_line(self):
        if self.verbose:
            print("parando linha azul")
        # >>> CRIA A TASK DO STOP (sempre pode parar) <<<
        threading.Thread(
            target=self._t_stop_blue_line, name="TSTOP-BlueLine", daemon=True
        ).start()

    def _t_run_blue_line(self):
        with self._lock:
            if self._blue_running:
                return
            self._blue_running = True
        try:
            # Apenas LIGA os atuadores (sem loops/sleeps, sem desligar)
            self._activate(
                Inputs.Caixote_Azul_Esteira_1, Inputs.Caixote_Azul_Esteira_2
            )
        finally:
            # Mantém _blue_running=True até alguém chamar stop
            pass

    def _t_stop_blue_line(self):
        try:
            # Sempre DESLIGA, não importa se _blue_running está True/False
            self._deactivate(
                Inputs.Caixote_Azul_Esteira_1, Inputs.Caixote_Azul_Esteira_2
            )
        finally:
            with self._lock:
                self._blue_running = False

    # ================ GREEN / EMPTY (mesmo padrão) ================
    def run_green_line(self):
        if self.server.machine_state != "running":
            return
        if self.verbose:
            print("ligando linha verde")
        threading.Thread(
            target=self._t_run_green_line, name="TRUN-GreenLine", daemon=True
        ).start()

    def stop_green_line(self):
        if self.verbose:
            print("parando linha verde")
        threading.Thread(
            target=self._t_stop_green_line, name="TSTOP-GreenLine", daemon=True
        ).start()

    def _t_run_green_line(self):
        with self._lock:
            if self._green_running:
                return
            self._green_running = True
        try:
            self._activate(
                Inputs.Caixote_Verde_Esteira_1,
                Inputs.Caixote_Verde_Esteira_2,
                Inputs.Caixote_Verde_Esteira_3,
                Inputs.Caixote_Verde_Esteira_4,
            )
        finally:
            pass

    def _t_stop_green_line(self):
        try:
            self._deactivate(
                Inputs.Caixote_Verde_Esteira_1,
                Inputs.Caixote_Verde_Esteira_2,
                Inputs.Caixote_Verde_Esteira_3,
                Inputs.Caixote_Verde_Esteira_4,
            )
        finally:
            with self._lock:
                self._green_running = False

    def run_empty_line(self):
        if self.server.machine_state != "running":
            return
        if self.verbose:
            print("ligando linha vazio")
        threading.Thread(
            target=self._t_run_empty_line, name="TRUN-EmptyLine", daemon=True
        ).start()

    def stop_empty_line(self):
        if self.verbose:
            print("parando linha vazio")
        threading.Thread(
            target=self._t_stop_empty_line, name="TSTOP-EmptyLine", daemon=True
        ).start()

    def _t_run_empty_line(self):
        with self._lock:
            if self._empty_running:
                return
            self._empty_running = True
        try:
            self._activate(
                Inputs.Caixote_Vazio_Esteira_1,
                Inputs.Caixote_Vazio_Esteira_2,
                Inputs.Caixote_Vazio_Esteira_3,
                Inputs.Caixote_Vazio_Esteira_4,
            )
        finally:
            pass

    def _t_stop_empty_line(self):
        try:
            self._deactivate(
                Inputs.Caixote_Vazio_Esteira_1,
                Inputs.Caixote_Vazio_Esteira_2,
                Inputs.Caixote_Vazio_Esteira_3,
                Inputs.Caixote_Vazio_Esteira_4,
            )
        finally:
            with self._lock:
                self._empty_running = False
