import threading
import time
from addresses import Coils, Inputs


class LineController:
    def __init__(self, server, verbose: bool = True):
        self.server = server
        self.verbose = verbose
        self._blue_running = False
        self._green_running = False
        self._empty_running = False
        self._production_running = False
        self._lock = threading.Lock()

        # --- Estados da mesa ---
        self._turntable_turn = False  # False = giro OFF/centro
        self._turntable_belt = "stop"  # "forward" | "backward" | "stop"
        self._belt_watch_th = None  # thread do watcher
        self._belt_watching = False  # flag do watcher
        self.turntable_busy = False
        self.active_job = None
        self.turntable1_busy = False

    # ---------------- Helpers IO ----------------
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
        # if self.verbose:
        #     print("ligando linha azul")

        threading.Thread(
            target=self._t_run_blue_line, name="TRUN-BlueLine", daemon=True
        ).start()

    def stop_blue_line(self):
        if self.verbose:
            print("parando linha azul")

        threading.Thread(
            target=self._t_stop_blue_line, name="TSTOP-BlueLine", daemon=True
        ).start()

    def _t_run_blue_line(self):
        with self._lock:
            if self._blue_running:
                return
            self._blue_running = True
        try:
            self._activate(Inputs.Caixote_Azul_Esteira_1, Inputs.Caixote_Azul_Esteira_2)
        finally:
            pass

    def _t_stop_blue_line(self):
        try:
            self._deactivate(
                Inputs.Caixote_Azul_Esteira_1, Inputs.Caixote_Azul_Esteira_2
            )
        finally:
            with self._lock:
                self._blue_running = False

    # ================= GREEN =================
    def run_green_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha verde")
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

    # ================= EMPTY =================
    def run_empty_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha vazio")
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

    # ================ Production (all) ================
    def run_production_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha produção")
        threading.Thread(
            target=self._t_run_production_line, name="TRUN-ProductionLine", daemon=True
        ).start()

    def stop_production_line(self):
        if self.verbose:
            print("parando linha produção")
        threading.Thread(
            target=self._t_stop_production_line,
            name="TSTOP-ProductionLine",
            daemon=True,
        ).start()

    def _t_run_production_line(self):
        with self._lock:
            if self._production_running:
                return
            self._production_running = True
        try:

            self._activate(Inputs.Esteira_Producao_1, Inputs.Esteira_Producao_2)

        finally:
            pass

    def _t_stop_production_line(self):
        try:
            self._deactivate(Inputs.Esteira_Producao_1)
        finally:
            with self._lock:
                self._production_running = False

    # ========== Prod Line ==========
    def is_production_running(self, color: str) -> bool:
        with self._lock:
            return self._production_running

    # ========== Turntable Unified (ON/OFF + Belt) ==========
    # def set_turntable_async(
    #     self,
    #     turn_on: bool | None,
    #     belt: str = "none",  # "forward" | "backward" | "stop"/"none"
    #     stop_limit: str | None = None,  # "front" | "back" | None (não vigia)
    #     belt_timeout_s: float = 1.0,
    # ):
    #     if self.server.machine_state != "running":
    #         return
    #     threading.Thread(
    #         target=self._t_set_turntable,
    #         args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
    #         name=f"TRUN-Turntable-{turn_on}-{belt}-{stop_limit}",
    #         daemon=True,
    #     ).start()

    def set_turntable_async(
        self,
        turn_on: bool | None,
        belt: str = "none",            # "forward" | "backward" | "stop"/"none"
        stop_limit: str | None = None, # "front" | "back" | None (não vigia)
        belt_timeout_s: float = 1.0,
    ):
        if self.server.machine_state != "running":
            return

        # ====== GUARDA TT1: só aceitar novo comando quando a operação anterior terminar ======
        # Considera "ocupado" se:
        #   - uma operação anterior marcou busy (turntable1_busy=True), ou
        #   - o watcher da TT1 ainda está ativo (_belt_watching=True).
        # Obs.: Se preferir não BLOQUEAR, você pode apenas "return" quando ocupado.
        wait_deadline = time.time() + 10.0  # timeout de segurança para não travar
        while (self.turntable1_busy or getattr(self, "_belt_watching", False)) and time.time() < wait_deadline:
            time.sleep(0.01)

        if self.turntable1_busy or getattr(self, "_belt_watching", False):
            # Ainda ocupado após timeout, não agenda nova operação.
            if self.verbose:
                print("[TT1][GUARDA] ocupado (busy/watcher ativo); ignorando comando para evitar atropelo.")
            return
        # =====================================================================================

        threading.Thread(
            target=self._t_set_turntable,
            args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
            name=f"TRUN-Turntable-{turn_on}-{belt}-{stop_limit}",
            daemon=True,
        ).start()

    def turntable_on(self, belt: str = "none"):
        self.set_turntable_async(True, belt)

    def turntable_off(self, belt: str = "none"):
        self.set_turntable_async(False, belt)

    def turntable_belt_forward(self):
        self.set_turntable_async(turn_on=None, belt="forward")

    def turntable_belt_backward(self):
        self.set_turntable_async(turn_on=None, belt="backward")

    def turntable_belt_stop(self):
        self.set_turntable_async(turn_on=None, belt="stop")

    # ---------------- worker da mesa ----------------
    def _t_set_turntable(
        self,
        turn_on: bool | None,
        belt: str,
        stop_limit: str | None,
        belt_timeout_s: float,
    ):
        self.turntable1_busy = True
        TURN_COIL = Inputs.Turntable1_turn
        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida

        try:
            # --- gira (se pedido) ---
            with self._lock:
                if turn_on is True:
                    self.server.set_actuator(TURN_COIL, True)
                    self._turntable_turn = True
                elif turn_on is False:
                    self.server.set_actuator(TURN_COIL, False)
                    self._turntable_turn = False

            # --- belt interno ---
            belt_to_watch = None
            if belt == "forward":
                self.server.set_actuator(BELT_REV, False)
                self.server.set_actuator(BELT_FWD, True)
                with self._lock:
                    self._turntable_belt = "forward"
                belt_to_watch = "forward"
            elif belt == "backward":
                self.server.set_actuator(BELT_FWD, False)
                self.server.set_actuator(BELT_REV, True)
                with self._lock:
                    self._turntable_belt = "backward"
                belt_to_watch = "backward"
            elif belt in ("stop", "none"):
                self.server.set_actuator(BELT_FWD, False)
                self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                belt_to_watch = None

            # --- watcher: escolhe o LIMITE conforme stop_limit explicitado ---
            if stop_limit is None or belt_to_watch is None:
                self._stop_belt_watcher()
                if self.verbose:
                    print(
                        f"[turntable] turn_on={turn_on} belt={belt} -> turn={getattr(self,'_turntable_turn',None)} belt_state={self._turntable_belt}"
                    )
                return

            if stop_limit.lower() == "front":
                limit_addr = Coils.Turntable1_FrontLimit
            elif stop_limit.lower() == "back":
                limit_addr = Coils.Turntable1_BackLimit
            else:
                if self.verbose:
                    print(
                        f"[turntable] stop_limit inválido: {stop_limit} (esperado 'front' ou 'back'); watcher desativado."
                    )
                self._stop_belt_watcher()
                return

            # inicia watcher com grace + borda + tempo mínimo
            self._start_belt_watcher(
                direction=belt_to_watch, limit_addr=limit_addr, timeout_s=belt_timeout_s
            )
            if self.verbose:
                print(
                    f"[turntable] turn_on={turn_on} belt={belt} stop_limit={stop_limit} -> turn={getattr(self,'_turntable_turn',None)} belt_state={self._turntable_belt}"
                )
        finally:
            self.turntable1_busy = False

    # ---------------- watcher da esteira da mesa ----------------
    def _stop_belt_watcher(self):
        """Solicita parada do watcher atual (se existir) e aguarda um pouco."""
        self._belt_watching = False
        th = self._belt_watch_th
        if th and th.is_alive():
            th.join(timeout=0.2)
        self._belt_watch_th = None

    def _start_belt_watcher(
        self,
        direction: str,
        limit_addr: int,
        timeout_s: float = 3.0,
        grace_s: float = 0.20,
        min_on_s: float = 0.30,
    ):
        # mata watcher anterior
        self._stop_belt_watcher()
        self._belt_watching = True

        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida
        BELT_ADDR = BELT_FWD if direction == "forward" else BELT_REV

        stop_evt = getattr(self.server, "_stop_evt", None)

        def _watch():
            t_on = time.time()
            try:
                # grace: dá tempo do motor iniciar (evita desligar se limite já começar True)
                time.sleep(grace_s)

                # snapshot inicial para exigir BORDA (0->1)
                start_state = bool(self.server.get_sensor(limit_addr))
                deadline = time.time() + timeout_s
                DEBOUNCE_N = 2
                stable = 0

                while time.time() < deadline:
                    if stop_evt and stop_evt.is_set():
                        break
                    if self.server.machine_state != "running":
                        break

                    cur = bool(self.server.get_sensor(limit_addr))
                    if (not start_state) and cur:
                        stable += 1
                    else:
                        stable = 0

                    if stable >= DEBOUNCE_N:
                        break
                    time.sleep(0.02)

                # tempo mínimo ligado antes de cortar
                rem = min_on_s - (time.time() - t_on)
                if rem > 0:
                    time.sleep(rem)

                # corta belt por limite (estável) ou por timeout (fail-safe)
                self.server.set_actuator(BELT_ADDR, False)
                with self._lock:
                    self._turntable_belt = "stop"

                if self.verbose:
                    if stable >= DEBOUNCE_N:
                        print(
                            f"[turntable] limite (edge) atingido ({direction}); esteira interna parada."
                        )
                    else:
                        print(
                            f"[turntable] timeout ({direction}); esteira interna parada por segurança."
                        )
            finally:
                self._belt_watching = False

        self._belt_watch_th = threading.Thread(
            target=_watch, name=f"TWatch-Turntable-{direction}", daemon=True
        )
        self._belt_watch_th.start()

    def _watch_limit_and_stop(self, direction: str, limit_addr: int, timeout_s: float):
        """
        Espera COIL de limite (Factory I/O: sensores são COILS) sem bloquear o event loop.
        Quando o limite aciona, desliga a direção ativa da esteira interna da mesa.
        """
        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida
        stop_evt = getattr(self.server, "stop_event", None) or getattr(
            self.server, "_stop_evt", None
        )

        DEBOUNCE_N = 2
        stable = 0
        t0 = time.time()
        print(
            f"[watcher] iniciado: direction={direction}, limit={limit_addr}, timeout={timeout_s}"
        )

        while self._belt_watching:
            # dentro do watcher loop:
            print(
                f"[debug] sensor({limit_addr}) = {self.server.get_sensor(limit_addr)} belt={direction}"
            )

            if stop_evt and stop_evt.is_set():
                break
            if self.server.machine_state != "running":
                break

            if self.server.get_sensor(limit_addr):
                stable += 1
            else:
                stable = 0

            if stable >= DEBOUNCE_N:
                if direction == "forward":
                    self.server.set_actuator(BELT_FWD, False)
                else:
                    self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                if self.verbose:
                    print(
                        f"[turntable] limite estável ({direction}); esteira interna parada."
                    )
                break
            time.sleep(0.25)
            if (time.time() - t0) > timeout_s:
                # FAIL-SAFE: pare a direção ativa mesmo sem limite
                if self.verbose:
                    print(
                        f"[turntable] watcher timeout ({direction}); parando belt por segurança."
                    )
                if direction == "forward":
                    self.server.set_actuator(BELT_FWD, False)
                else:
                    self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                break

            time.sleep(0.02)

        self._belt_watching = False

    # =============== [ADD] API da TT2 (paralela à da TT1) ===============
    def set_turntable2_async(
        self,
        turn_on: bool | None,
        belt: str = "none",  # "forward" | "backward" | "stop"/"none"
        stop_limit: str | None = None,  # "front" | "back" | None
        belt_timeout_s: float = 1.0,
    ):
        if self.server.machine_state != "running":
            return
        threading.Thread(
            target=self._t2_set_turntable,
            args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
            name=f"TRUN-TT2-{turn_on}-{belt}-{stop_limit}",
            daemon=True,
        ).start()

    def _t2_set_turntable(
        self,
        turn_on: bool | None,
        belt: str,
        stop_limit: str | None,
        belt_timeout_s: float,
    ):
        # ----- ENDEREÇOS TT2 -----
        TURN_COIL = Inputs.Turntable2_turn

        # Ajuste se você tiver FWD/REV separados na TT2:
        BELT_FWD = (
            Inputs.Discharg_turn
            if hasattr(Inputs, "Turntable2_Esteira_SaidaEntrada")
            else Inputs.Discharg_turn
        )
        BELT_REV = (
            Inputs.Load_turn
            if hasattr(Inputs, "Turntable2_Esteira_EntradaSaida")
            else Inputs.Load_turn
        )

        # --- gira (se pedido) ---
        with self._lock:
            if turn_on is True:
                self.server.set_actuator(TURN_COIL, True)
                self._turntable2_turn = True
            elif turn_on is False:
                self.server.set_actuator(TURN_COIL, False)
                self._turntable2_turn = False

        # --- belt interno ---
        belt_to_watch = None
        if belt == "forward":
            try:
                self.server.set_actuator(BELT_REV, False)
            except Exception:
                pass
            self.server.set_actuator(BELT_FWD, True)
            with self._lock:
                self._turntable2_belt = "forward"
            belt_to_watch = "forward"

        elif belt == "backward":
            try:
                self.server.set_actuator(BELT_FWD, False)
            except Exception:
                pass
            self.server.set_actuator(BELT_REV, True)
            with self._lock:
                self._turntable2_belt = "backward"
            belt_to_watch = "backward"

        elif belt in ("stop", "none"):
            self.server.set_actuator(BELT_FWD, False)
            try:
                self.server.set_actuator(BELT_REV, False)
            except Exception:
                pass
            with self._lock:
                self._turntable2_belt = "stop"
            belt_to_watch = None

        # --- watcher dos limites da TT2 ---
        if stop_limit is None or belt_to_watch is None:
            self._stop_belt_watcher()
            if self.verbose:
                print(
                    f"[tt2] turn_on={turn_on} belt={belt} -> turn={getattr(self,'_turntable2_turn',None)} belt_state={getattr(self,'_turntable2_belt',None)}"
                )
            return

        if stop_limit.lower() == "front":
            limit_addr = Coils.Turntable2_FrontLimit
        elif stop_limit.lower() == "back":
            limit_addr = Coils.Turntable2_BackLimit
        else:
            if self.verbose:
                print(f"[tt2] stop_limit inválido: {stop_limit}")
            self._stop_belt_watcher()
            return

        self._start_belt_watcher(
            direction=belt_to_watch, limit_addr=limit_addr, timeout_s=belt_timeout_s
        )
        if self.verbose:
            print(
                f"[tt2] turn_on={turn_on} belt={belt} stop_limit={stop_limit} -> turn={getattr(self,'_turntable2_turn',None)} belt_state={getattr(self,'_turntable2_belt',None)}"
            )

    # =============== [END ADD] ===============
