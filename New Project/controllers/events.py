import threading
from typing import Callable, Dict, List
from addresses import Coils, Inputs

DEFAULT_ORDER_COUNT  = 1      # "Quantos pedidos?"
DEFAULT_ORDER_COLOR  = "BLUE" # "BLUE" | "GREEN" | "EMPTY"
DEFAULT_ORDER_BOXES  = 3      # "Quantidade de caixas"

class EventProcessor:
    """
    Processa bordas de sensores e botões, chamando callbacks.
    Mantém o estado anterior das coils relevantes.
    """

    def __init__(self, server, lines_controller, verbose: bool = True):
        self.server = server
        self.lines = lines_controller
        self.verbose = verbose
        self._prev: Dict[int, int] = {}
        self._hal_prev = False
        self._hal_prev = 0

    def handle_scan(self, coils_snapshot: List[int]) -> None:
        # Sensores que verificam a presença de caixotes no emmiter
        self._handle_edge(
            Coils.Sensor_1_Caixote_Azul,
            coils_snapshot,
            lambda: self.lines.run_blue_line(),
        )
        self._handle_edge(
            Coils.Sensor_1_Caixote_Verde,
            coils_snapshot,
            lambda: self.lines.run_green_line(),
        )
        self._handle_edge(
            Coils.Sensor_1_Caixote_Vazio,
            coils_snapshot,
            lambda: self.lines.run_empty_line(),
        )

        self._handle_edge(
            Coils.Sensor_2_Caixote_Azul,
            coils_snapshot,
            lambda: self._on_arrival(
                "blue", Coils.Sensor_2_Caixote_Azul, self.lines.stop_blue_line
            ),
        )

        self._handle_edge(
            Coils.Sensor_2_Caixote_Verde,
            coils_snapshot,
            lambda: self._on_arrival(
                "green", Coils.Sensor_2_Caixote_Verde, self.lines.stop_green_line
            ),
        )

        self._handle_edge(
            Coils.Sensor_2_Caixote_Vazio,
            coils_snapshot,
            lambda: self._on_arrival(
                "empty", Coils.Sensor_2_Caixote_Vazio, self.lines.stop_empty_line
            ),
        )

        self._handle_edge(
            Coils.Load_Sensor,
            coils_snapshot,
            lambda: self.server.auto.arm_tt2_if_idle("Load_Sensor"),
        )

        self._handle_edge(Coils.Create_OP, coils_snapshot, self._on_create_op)

        # Botões (Start/Reset/Emergency)
        if self._handle_edge(
            Coils.Emergency, coils_snapshot, self.server._on_emergency_toggle
        ):
            return
        if self._handle_edge(
            Coils.RestartButton, coils_snapshot, self.server._on_reset
        ):
            return
        if self._handle_edge(Coils.Start, coils_snapshot, self.server._on_start):
            return
        if self._handle_edge(Coils.Stop, coils_snapshot, self.server._on_stop):
            return

        # ---- HAL por BORDA de subida e delega ao AutoController ----
        try:
            cur_hal = 1 if (Coils.Sensor_Hall < len(coils_snapshot) and coils_snapshot[Coils.Sensor_Hall]) else 0
            if (self._hal_prev == 0) and (cur_hal == 1):
                # Delega ao AutoController — ele cuida da inibição e janela
                if hasattr(self.server, "auto"):
                    self.server.auto.enqueue_hal(Coils.Sensor_Hall)
        except Exception as _e:
            # opcional: log leve sem quebrar o loop
            if getattr(self, "verbose", False):
                print(f"[EVENTS] HAL edge err: {_e}")
        finally:
            self._hal_prev = cur_hal

    # ---------- detecção de borda (idêntica à lógica original, com casos especiais) ----------
    def _handle_edge(
        self, addr: int, coils: List[int], callback: Callable[[], None]
    ) -> bool:
        acionou = False
        cur = int(bool(coils[addr])) if addr < len(coils) else 0

        # Casos especiais (sensores 1 das três linhas): detectar transição e acionar apenas quando cur==0
        if addr in (
            Coils.Sensor_1_Caixote_Vazio,
            Coils.Sensor_1_Caixote_Azul,
            Coils.Sensor_1_Caixote_Verde,
        ):
            prev = self._prev.get(addr, 1)
            if cur != prev:
                if self.verbose:
                    nome = {
                        Coils.Sensor_1_Caixote_Vazio: "vazio",
                        Coils.Sensor_1_Caixote_Azul: "azul",
                        Coils.Sensor_1_Caixote_Verde: "verde",
                    }[addr]
                    # print(f"Sensor {nome} mudou de estado: {prev} → {cur}")
                if cur == 0:
                    callback()
                acionou = True
            self._prev[addr] = cur
            return acionou

        # Emergência: sempre chama no toggle
        if addr == Coils.Emergency:
            prev = self._prev.get(addr, 1)
            if cur != prev:
                if self.verbose:
                    print(f"Emergência mudou: {prev} → {cur}")
                callback()
                acionou = True
            self._prev[addr] = cur

            self.server.turntable_state1 = self.server.get_actuator(
                Inputs.Turntable1_Esteira_EntradaSaida
            )
            self.server.turntable_state2 = self.server.get_actuator(
                Inputs.Turntable1_Esteira_SaidaEntrada
            )
            return acionou

        if addr == Coils.RestartButton:
            prev = self._prev.get(addr, 0)
            if cur != prev:
                if self.verbose:
                    print(f"Restart process mudou: {prev} → {cur}")
                callback()
                acionou = True
            self._prev[addr] = cur
            return acionou

        # Demais: borda de subida
        prev = self._prev.get(addr, 0)
        if cur == 1 and prev == 0:
            callback()
            acionou = True
        self._prev[addr] = cur
        return acionou

    def _on_arrival(self, tipo: str, sensor_addr: int, stop_fn) -> None:
        stop_fn()
        self.server.auto.enqueue_arrival(tipo, sensor_addr)

    def _handle_edge_fall(
        self, addr: int, coils: List[int], callback: Callable[[], None]
    ) -> bool:
        """Aciona callback na borda de QUEDA (1->0)."""
        acionou = False
        cur = int(bool(coils[addr])) if addr < len(coils) else 0
        prev = self._prev.get(addr, cur)
        if cur == 0 and prev == 1:
            callback()
            acionou = True
        self._prev[addr] = cur
        return acionou

    def _on_create_op(self):
        # cadastra N pedidos com {cor, caixas}; insumo=1 fixo (implícito)
        if self.verbose:
            print("[EVENTS] Create_OP → cadastrando pedidos…")
        self.server.auto.orders.create_order(
            color=DEFAULT_ORDER_COLOR,
            boxes=DEFAULT_ORDER_BOXES,
            count=DEFAULT_ORDER_COUNT
        )
