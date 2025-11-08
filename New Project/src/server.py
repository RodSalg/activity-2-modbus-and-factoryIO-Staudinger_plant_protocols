import inspect
import time
import threading
from datetime import datetime
from typing import Optional, List
from pyModbusTCP.server import ModbusServer

from utils import Stoppable, now
from addresses import Inputs, Coils, Esteiras
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

        # Estado das esteiras
        self.turntable_state1 = False
        self.turntable_state2 = False

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
    
    # ------------ to registers

    def read_input_register(self, address: int, count: int = 1) -> List[int]:
        """
        Lê Input Register(s) do banco de dados Modbus.
        
        Input Registers são registradores somente leitura (função 04),
        tipicamente usados para leitura de sensores analógicos e dados de telemetria.
        
        Args:
            address: Endereço inicial do Input Register (0-65535)
            count: Número de registradores a ler (padrão: 1)
        
        Returns:
            Lista de valores inteiros (16-bit unsigned) lidos
        
        Raises:
            RuntimeError: Se o servidor não estiver iniciado
            ValueError: Se address ou count forem inválidos
        
        Example:
            >>> temperature = server.read_input_register(100)
            >>> [2550]  # 25.5°C (scaled by 100)
        """
        if count < 1 or count > 125:
            raise ValueError(f"Count deve estar entre 1 e 125, recebido: {count}")
        
        if address < 0 or address > 65535:
            raise ValueError(f"Endereço inválido: {address}")
        
        db = self._db()
        values = db.get_input_registers(address, count)
        
        if values is None:
            return [0] * count
        
        return list(values)

    def write_input_register(self, address: int, value: int) -> None:
        """
        Escreve valor em Input Register.
        
        NOTA: Input Registers são tecnicamente somente leitura no protocolo Modbus,
        mas este método permite escrita interna para simulação de sensores ou
        atualização de telemetria no servidor.
        
        Args:
            address: Endereço do Input Register (0-65535)
            value: Valor a escrever (0-65535, 16-bit unsigned)
        
        Raises:
            RuntimeError: Se o servidor não estiver iniciado
            ValueError: Se address ou value forem inválidos
        
        Example:
            >>> server.write_input_register(100, 2550)  # Simular temperatura 25.5°C
        """
        if address < 0 or address > 65535:
            raise ValueError(f"Endereço inválido: {address}")
        
        if value < 0 or value > 65535:
            raise ValueError(f"Valor deve estar entre 0 e 65535, recebido: {value}")
        
        db = self._db()
        with self._lock:
            db.set_input_registers(address, [value])

    def read_holding_register(self, address: int, count: int = 1) -> List[int]:
        """
        Lê Holding Register(s) do banco de dados Modbus (função 03).
        
        Permite leitura de setpoints, configurações e valores de controle.
        
        Args:
            address: Endereço inicial do Holding Register (0-65535)
            count: Número de registradores a ler (padrão: 1)
        
        Returns:
            Lista de valores inteiros (16-bit unsigned) lidos
        
        Raises:
            RuntimeError: Se o servidor não estiver iniciado
            ValueError: Se address ou count forem inválidos
        
        Example:
            >>> setpoint = server.read_holding_register(200)
            >>> [3000]  # 30.0°C
        """
        if count < 1 or count > 125:
            raise ValueError(f"Count deve estar entre 1 e 125, recebido: {count}")
        
        if address < 0 or address > 65535:
            raise ValueError(f"Endereço inválido: {address}")
        
        db = self._db()
        values = db.get_holding_registers(address, count)
        
        if values is None:
            return [0] * count
        
        return list(values)

    def write_holding_register(self, address: int, value: int) -> None:
        """
        Escreve valor em Holding Register (função 06/16).
        
        Holding Registers são registradores de leitura/escrita,
        tipicamente usados para setpoints, configurações e controle analógico.
        
        Args:
            address: Endereço do Holding Register (0-65535)
            value: Valor a escrever (0-65535, 16-bit unsigned)
        
        Raises:
            RuntimeError: Se o servidor não estiver iniciado
            ValueError: Se address ou value forem inválidos
        
        Example:
            >>> server.write_holding_register(200, 3000)  # Setpoint 30.0°C
        """
        if address < 0 or address > 65535:
            raise ValueError(f"Endereço inválido: {address}")
        
        if value < 0 or value > 65535:
            raise ValueError(f"Valor deve estar entre 0 e 65535, recebido: {value}")
        
        db = self._db()
        with self._lock:
            db.set_holding_registers(address, [value])

    # ------------ to digital inputs and ouputs
    
    def get_sensor(self, sensor_address: int) -> bool:
        db = self._db()
        return bool(db.get_coils(sensor_address, 1)[0])

    def get_actuator(self, di_address: int) -> bool:
        """Lê o estado do Discrete Input no endereço informado (debug/telemetria)."""
        db = self._db()
        val = db.get_discrete_inputs(di_address, 1)
        return bool(val and val[0])

    def set_actuator(self, coil_address: int, value: bool) -> None:
        # print(
        #     f"[DEBUG ACTUATOR] {coil_address} <= {value}  (chamado por {inspect.stack()[1].function})"
        # )
        db = self._db()
        db.set_discrete_inputs(coil_address, [int(value)])

    def _write_coil(self, addr: int, value: bool) -> None:
        db = self._db()
        with self._lock:
            db.set_coils(addr, [1 if value else 0])

    def _all_off(self) -> None:
        self._write_coil(Inputs.EntryConveyor, False)

        for name, addr in Esteiras.__members__.items():
            self.set_actuator(addr.value, False)

    def _all_on(self) -> None:
        # self._write_coil(Inputs.EntryConveyor, False)
        self.set_actuator(Inputs.Running, True)
        for name, addr in Esteiras.__members__.items():
            self.set_actuator(addr.value, True)

        self.set_actuator(Inputs.Turntable1_Esteira_EntradaSaida, self.turntable_state1)            
        self.set_actuator(Inputs.Turntable1_Esteira_SaidaEntrada, self.turntable_state2)

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
        #self.machine_state = "running"                      ##### comentar
        self.sequence_step = "idle"
        self.set_actuator(Inputs.Stop, False)
        self.set_actuator(Inputs.Running, True)
        self.auto.start()

    def _on_stop(self):
        if self.verbose:
            print("Stop")
        self.machine_state = "Stopped"
        self.sequence_step = "idle"
        self.set_actuator(Inputs.Emergency, False)
        self.set_actuator(Inputs.Running, False)
        self.set_actuator(Inputs.Stop, True)
        self._all_off()

    def _on_reset(self):
        if self.verbose:
            print("Restart Process")
        if self.get_sensor(Coils.RestartButton) is True:
            self.sequence_step = "idle"
            self.machine_state = "Running"
            self.set_actuator(Inputs.Emergency, False)
            self.set_actuator(Inputs.Stop, False)
            self.set_actuator(Inputs.Running, True)
            self._all_on()

    def _on_emergency_toggle(self):
        print("valor da emergencia: ", self.get_sensor(Coils.Emergency))

        # turntable_state1 = self.get_actuator(Inputs.Turntable1_Esteira_EntradaSaida)
        # turntable_state2 = self.get_actuator(Inputs.Turntable1_Esteira_SaidaEntrada)

        # Emergência ON (coil False)
        if (
            self.machine_state != "emergency"
            and self.get_sensor(Coils.Emergency) is False
        ):
            if self.verbose:
                print("Emergency ON")
            self.machine_state = "emergency"
            self.sequence_step = "idle"
            self.set_actuator(Inputs.Stop, True)
            self.set_actuator(Inputs.Running, False)
            self.set_actuator(Inputs.Emergency, True)
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



    def controle_turntable_3(self, alvo_90_graus: bool):

    
        atuador_giro = Inputs.Turntable3_turn  # Input 42
        sensor_alvo = Coils.tt3_limit_90 # Coil 16 (Alvo é sempre 90)
        
        # 2. Checa se a mesa já está na posição
        if self.server.get_sensor(sensor_alvo):
            print("[TT3] Mesa já está em 90 graus. Pulando giro.")
            return True

        # 3. Lógica de Rotação
        print("[TT3] Iniciando giro para 90 graus.")
        self.server.set_actuator(atuador_giro, True) # Liga o atuador de giro

        # Espera até que o sensor de limite 90 seja ativado
        timeout = time.time() + 1.0 
        while self.server.get_sensor(sensor_alvo) == False and time.time() < timeout:
            time.sleep(self.server.scan_time)
            
        self.server.set_actuator(atuador_giro, False) # Desliga o atuador de giro

        if self.server.get_sensor(sensor_alvo) == False:
            print("[TT3] ERRO DE GIRO: Tempo esgotado ou sensor de limite falhou.")
            return False

        print("[TT3] Giro concluído com sucesso.")
        return True





    def _process_turntable3(self):
        """
        Controla a entrada de uma caixa na Turntable 3, a centraliza 
        e inicia o processo de envio para a Esteira Pedido (2).
        """
        print("Caixa detectada na entrada. Iniciando processamento da TT3.")

        
        # 2. CENTRALIZAR A CAIXA NA MESA
        print("Movendo caixa para o centro da mesa.")
        self.set_actuator(Inputs.Turntable3_roll, True) 
        
        # Espera até o sensor central (Coil 20) ser ativado
        timeout = time.time() + 1.0 
        while self.get_sensor(Coils.Sensor_turntable3) == False and time.time() < timeout:
            time.sleep(self.scan_time)
                     
        if self.get_sensor(Coils.Sensor_turntable3) == False:
            print("⚠️ ERRO: Caixa não chegou ao sensor central da TT3 (Coil 20). Abortando.")
            return 

        # 3. CHAMAR A LÓGICA DE MOVIMENTO PARA O PEDIDO (Já está simplificada)
        print("Caixa centralizada. Iniciando giro e envio para Pedido (2).")

        self.mover_para_cliente(esteira_destino=Inputs.esteira_pedido)



    def retorno_turntable_3(self) -> bool:
    
    # 1. Definições de Mapeamento (Fixo 0 graus)
        atuador_giro = Inputs.Turntable3_turn  # Input 42
        sensor_alvo = Coils.tt3_limit_0  # Coil 17 (Alvo é sempre 0)
        
        # 2. Checa se a mesa já está na posição
        if self.server.get_sensor(sensor_alvo):
            print("[TT3] Mesa já está em 0 graus. Não precisa retornar.")
            return True

        # 3. Lógica de Rotação
        print("[TT3] Iniciando retorno para 0 graus.")
        self.server.set_actuator(atuador_giro, True) 

        # Espera até que o sensor de limite 0 seja ativado
        timeout = time.time() + 1.0 
        while self.server.get_sensor(sensor_alvo) == False and time.time() < timeout:
            time.sleep(self.server.scan_time)
            
        self.server.set_actuator(atuador_giro, False) 

        if self.server.get_sensor(sensor_alvo) == False:
            print("⚠️ [TT3] ERRO DE RETORNO: Tempo esgotado ou sensor de limite 0 falhou.")
            return False

        print("[TT3] Retorno para 0 graus concluído com sucesso.")
        return True

        

    def mover_para_cliente(self, esteira_destino: int ) -> bool:

        if not self.controle_turntable_3(): 
            print("[PEDIDO] Falha no giro. Abortando.")
            return False

        sensor_parada_destino = Coils.sensor_hall_1_6
        
        self.server.set_actuator(esteira_destino, True) # Inputs.esteira_pedido (Input 47)
        print(f"[PEDIDO] Esteira de Pedido (Input {esteira_destino}) LIGADA.")

        # 3. EMPURRAR A CAIXA (Roll Forward)
        atuador_roll = Inputs.Turntable3_roll 
        print("[PEDIDO] Acionando Roll Forward para empurrar a caixa.")
        self.server.set_actuator(atuador_roll, True)
        
        # Espera a caixa SAIR da Turntable (Coils.Sensor_turntable3, Coil 20)
        timeout = time.time() + 5.0 
        while self.server.get_sensor(Coils.Sensor_turntable3) == True and time.time() < timeout:
            time.sleep(self.server.scan_time)

        self.server.set_actuator(atuador_roll, False) # Desliga o Roll Forward
        
        if self.server.get_sensor(Coils.Sensor_turntable3) == True:
            print("⚠️ [PEDIDO] ERRO: Caixa não saiu da mesa após o tempo limite.")
            self.server.set_actuator(esteira_destino, False) 
            return False

        print("[PEDIDO] Caixa saiu da Turntable 3. Aguardando parada no destino.")

        # 4. AGUARDAR PARADA NO DESTINO (Sensor Coil 6)
        timeout = time.time() + 2.0 
        while self.server.get_sensor(sensor_parada_destino) == False and time.time() < timeout:
            time.sleep(self.server.scan_time)
            
        self.server.set_actuator(esteira_destino, False) # DESLIGA a esteira de destino
        
        if self.server.get_sensor(sensor_parada_destino) == False:
            print("⚠️ [PEDIDO] ERRO: Caixa não chegou ao sensor de parada no destino (Coil 6).")
            return False
        
        print("[PEDIDO] Caixa parada no sensor de destino (Coil 6). Processo concluído.")
        
        if self.server.get_sensor(sensor_parada_destino) == False:
            print("⚠️ [PEDIDO] ERRO: Caixa não chegou ao sensor de parada no destino (Coil 6).")
            return False
        
        print("[PEDIDO] Caixa parada no sensor de destino (Coil 6). Processo concluído.")

        # --- NOVO PASSO: RETORNAR A MESA ---
        self.retorno_turntable_3()

        return True
    
    