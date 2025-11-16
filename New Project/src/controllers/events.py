import threading
from typing import Callable, Dict, List, TYPE_CHECKING
from addresses import Coils, Inputs
from controllers.lines import LineController
import time

from services.DAO import ConfigManager, OrderConfig
if TYPE_CHECKING:
    from server import FactoryModbusEventServer

DEFAULT_ORDER_COUNT  = 1      # "Quantos pedidos?"
DEFAULT_ORDER_COLOR  = "GREEN" # "BLUE" | "GREEN" | "EMPTY"
DEFAULT_ORDER_BOXES  = 5      # "Quantidade de caixas"
DEFAULT_ORDER_RESOURCE  = 5      # "Quantidade de caixas"
DEFAULT_ORDER_CLIENT = "rafael_ltda"


class EventProcessor:
    """
    Processa bordas de sensores e botões, chamando callbacks.
    Mantém o estado anterior das coils relevantes.
    """

    def __init__(self, server: "FactoryModbusEventServer", lines_controller: LineController, verbose: bool = True):
        self.server = server
        self.lines = lines_controller
        self.verbose = verbose
        self._prev: Dict[int, int] = {}
        self._hal_prev = False
        self._hal_prev = 0

        self.config = ConfigManager()

        self.first_time = True

        t_handle_storage = threading.Thread(target = self.handle_storage)
        t_handle_storage.start()

        # t_handle_conveyor_storage = threading.Thread(target = self.handle_conveyor_storage)
        # t_handle_conveyor_storage.start()

        t_conveyor_1 = threading.Thread(target = self.handle_conveyor_storage_1)
        t_conveyor_1.start()

        t_conveyor_2 = threading.Thread(target = self.handle_conveyor_storage_2)
        t_conveyor_2.start()

        t_conveyor_3 = threading.Thread(target = self.handle_conveyor_storage_3)
        t_conveyor_3.start()

        t_conveyor_4 = threading.Thread(target = self.handle_conveyor_storage_4)
        t_conveyor_4.start()

    def handle_storage(self):

        if(self.first_time):
            time.sleep(2)
            self.first_time = False

        # ---------------------------------------------
        # ---------------------------------------------

        # ----- eventos da warehouse

        while(True):

            if(self.server.get_sensor(Coils.sensor_client_warehouse) == True):
                print("Sensor client é true")
                self.lines._t_save_on_client_warehouse()
                

            time.sleep(1)

            if(self.server.get_sensor(Coils.sensor_storage_warehouse) == True):
                print("Sensor storage é true")
                self.lines._t_save_on_storage_warehouse()

            time.sleep(0.500)

    def handle_conveyor_storage_1(self):
        """
        Gerencia a ESTEIRA 1: Recebe do hall_1_0
        Continua rodando se tiver caixa no meio (is_box_conveyor_1) até chegar na ponta
        """
        while True:
            try:
                hall_1_0 = self.server.get_sensor(Coils.sensor_hall_1_0)
                sensor_1 = self.server.get_sensor(Coils.sensor_conveyor_storage_1)
                is_box_1 = self.server.get_sensor(Coils.is_box_conveyor_1)

                if hall_1_0 and not sensor_1:
                    self.server.set_actuator(Inputs.conveyor_storage_1, True)

                    while self.server.get_sensor(Coils.sensor_conveyor_storage_1) == False:
                        if self.verbose:
                            print('preso aqui no 1')
                        self.server.set_actuator(Inputs.conveyor_storage_1, True)
                        time.sleep(0.1)

                    time.sleep(1)
                    self.server.set_actuator(Inputs.conveyor_storage_1, False)
                
                elif is_box_1 and not sensor_1:
                    self.server.set_actuator(Inputs.conveyor_storage_1, True)
                    if self.verbose:
                        print('Movendo caixa do meio da esteira 1 até a ponta')
                    time.sleep(0.1)
                else:
                    self.server.set_actuator(Inputs.conveyor_storage_1, False)
                
                time.sleep(2)
                
            except Exception as e:
                if self.verbose:
                    print(f"[EVENTS] Erro no handle_conveyor_storage_1: {e}")
                time.sleep(0.5)


    def handle_conveyor_storage_2(self):
        """
        Gerencia a ESTEIRA 2: Recebe da esteira 1
        Continua rodando se tiver caixa no meio (is_box_conveyor_2) até chegar na ponta
        """
        while True:
            try:
                sensor_1 = self.server.get_sensor(Coils.sensor_conveyor_storage_1)
                sensor_2 = self.server.get_sensor(Coils.sensor_conveyor_storage_2)
                is_box_2 = self.server.get_sensor(Coils.is_box_conveyor_2)

                if sensor_1 and not sensor_2:
                    self.server.set_actuator(Inputs.conveyor_storage_2, True)

                    self.server.set_actuator(Inputs.conveyor_storage_1, True)
                    time.sleep(2)
                    self.server.set_actuator(Inputs.conveyor_storage_1, False)
                    
                    while self.server.get_sensor(Coils.sensor_conveyor_storage_2) == False:
                        self.server.set_actuator(Inputs.conveyor_storage_2, True)
                        if self.verbose:
                            print('preso aqui no 2')
                        time.sleep(0.1)

                    time.sleep(1)
                    self.server.set_actuator(Inputs.conveyor_storage_2, False)
                
                elif is_box_2 and not sensor_2:
                    self.server.set_actuator(Inputs.conveyor_storage_2, True)
                    if self.verbose:
                        print('Movendo caixa do meio da esteira 2 até a ponta')
                    time.sleep(0.1)
                else:
                    self.server.set_actuator(Inputs.conveyor_storage_2, False)
                
                time.sleep(2)
                
            except Exception as e:
                if self.verbose:
                    print(f"[EVENTS] Erro no handle_conveyor_storage_2: {e}")
                time.sleep(0.5)


    def handle_conveyor_storage_3(self):
        """
        Gerencia a ESTEIRA 3: Recebe da esteira 2
        Continua rodando se tiver caixa no meio (is_box_conveyor_3) até chegar na ponta
        """
        while True:
            try:
                sensor_2 = self.server.get_sensor(Coils.sensor_conveyor_storage_2)
                sensor_3 = self.server.get_sensor(Coils.sensor_conveyor_storage_3)
                is_box_3 = self.server.get_sensor(Coils.is_box_conveyor_3)

                if sensor_2 and not sensor_3:
                    self.server.set_actuator(Inputs.conveyor_storage_3, True)

                    self.server.set_actuator(Inputs.conveyor_storage_2, True)
                    time.sleep(2)
                    self.server.set_actuator(Inputs.conveyor_storage_2, False)

                    while self.server.get_sensor(Coils.sensor_conveyor_storage_3) == False:
                        self.server.set_actuator(Inputs.conveyor_storage_3, True)
                        if self.verbose:
                            print('preso aqui no 3')
                        time.sleep(0.1)

                    time.sleep(0.3)
                    self.server.set_actuator(Inputs.conveyor_storage_3, False)
                
                elif is_box_3 and not sensor_3:
                    self.server.set_actuator(Inputs.conveyor_storage_3, True)
                    if self.verbose:
                        print('Movendo caixa do meio da esteira 3 até a ponta')
                    time.sleep(0.1)
                else:
                    self.server.set_actuator(Inputs.conveyor_storage_3, False)
                
                time.sleep(2)
                
            except Exception as e:
                if self.verbose:
                    print(f"[EVENTS] Erro no handle_conveyor_storage_3: {e}")
                time.sleep(0.5)


    def handle_conveyor_storage_4(self):
        """
        Gerencia a ESTEIRA 4 (FINAL): Recebe da esteira 3 e entrega no warehouse
        Esta esteira não tem is_box sensor intermediário
        """
        while True:
            try:
                sensor_3 = self.server.get_sensor(Coils.sensor_conveyor_storage_3)
                sensor_storage = self.server.get_sensor(Coils.sensor_storage_warehouse)

                if sensor_3 and not sensor_storage:
                    self.server.set_actuator(Inputs.conveyor_storage_4, True)

                    self.server.set_actuator(Inputs.conveyor_storage_3, True)
                    time.sleep(2)
                    self.server.set_actuator(Inputs.conveyor_storage_3, False)

                    while self.server.get_sensor(Coils.sensor_storage_warehouse) == False:

                        if(self.server.get_sensor(Coils.sensor_conveyor_storage_3)):
                            self.server.set_actuator(Inputs.conveyor_storage_3, True)
                            time.sleep(0.7)
                            self.server.set_actuator(Inputs.conveyor_storage_3, False)
                            
                        self.server.set_actuator(Inputs.conveyor_storage_4, True)
                        if self.verbose:
                            print('preso aqui no 4')
                        time.sleep(0.1)

                    self.server.set_actuator(Inputs.conveyor_storage_4, False)
                
                time.sleep(1)
                
            except Exception as e:
                if self.verbose:
                    print(f"[EVENTS] Erro no handle_conveyor_storage_4: {e}")
                time.sleep(0.5)


    def handle_scan(self, coils_snapshot: List[int]) -> None:


        self._handle_edge( Coils.button_box_from_storage, coils_snapshot, lambda: self.lines.remove_from_storage_warehouse(), )

        # ---> Eventos da esteira do estoque
        # self._handle_edge( Coils.sensor_hall_1_0, coils_snapshot, lambda: self.lines.run_conveyor_client(), )

        # ---------------------------------------------
        # ---------------------------------------------
                
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
                "blue", Coils.Sensor_2_Caixote_Azul, self.lines.run_esteira_producao_2
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
        if self.verbose:
            print("[EVENTS] Create_OP → cadastrando pedidos…")
        
        configs = self.config.get_config()

        self.server.auto.orders.create_order(
            color = configs.order_color,
            boxes = configs.order_boxes,
            count = configs.order_count,
        )
        # CORRETO: mudar o modo no AutoController
        self.server.auto._set_mode_order()