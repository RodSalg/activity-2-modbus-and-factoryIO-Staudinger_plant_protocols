# simuladores/servidor_modbus_eventos.py
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Callable
from pyModbusTCP.server import ModbusServer

from collections import deque

blue_line_running = False
green_line_running = False
empty_line_running = False



class Coils:
    Start = 24
    Emergency = 9
    resetButton = 27

    Sensor_1_Caixote_Verde = 77
    Sensor_2_Caixote_Verde = 78

    Sensor_1_Caixote_Azul = 80
    Sensor_2_Caixote_Azul = 81

    Sensor_1_Caixote_Vazio = 83
    Sensor_2_Caixote_Vazio = 84

    Sensor_Final_Producao = 86

    Sensor_Write = 10
    Emitter_Blue_Button = 26

class Inputs:
    EntryConveyor = 10

    Caixote_Verde_Conveyor_1 = 78
    Caixote_Verde_Conveyor_2 = 79
    Caixote_Verde_Conveyor_3 = 80
    Caixote_Verde_Conveyor_4 = 81
    Emmiter_Caixote_Verde_1 = 23
    Emmiter_Caixote_Verde_2 = 24

    Caixote_Azul_Conveyor_1 = 82
    Caixote_Azul_Conveyor_2 = 83
    Emmiter_Caixote_Azul_1 = 20
    Emmiter_Caixote_Azul_2 = 21
    
    Caixote_Vazio_Conveyor_1 = 84
    Caixote_Vazio_Conveyor_2 = 85
    Caixote_Vazio_Conveyor_3 = 86
    Caixote_Vazio_Conveyor_4 = 87
    Emmiter_Caixote_Vazio_1 = 23

    Turntable1_turn = 93
    Turntable1_row_forward = 94
    Turntable1_row_backward = 95

    Emitter_Blue_Light = 27


class FactoryModbusEventServer:

    def __init__(self, host: str = "0.0.0.0", port: int = 5020, scan_time: float = 0.05, verbose: bool = True):
        self.host = host
        self.port = port
        self.scan_time = scan_time
        self.verbose = verbose

        self._server: Optional[ModbusServer] = None
        self._event_thread: Optional[threading.Thread] = None
        self._auto_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._prev_coils: Dict[int, int] = {}

        self.machine_state = "idle"
        self.sequence_step = "idle"

    def start(self) -> None:
        if self._server is not None:
            return
        self._server = ModbusServer(host=self.host, port=self.port, no_block=True)
        self._server.start()
        db = self._server.data_bank

        # with self._lock:
        #     db.set_coils(0, [0] * 64)
        #     db.set_holding_registers(0, [0] * 64)

        self._stop_evt.clear()

        self._event_thread = threading.Thread(target=self._event_loop, name="modbus-event-loop", daemon=True)
        self._event_thread.start()

        if self.verbose:
            print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Servidor Modbus em {self.host}:{self.port}")

    def stop(self) -> None:
        self._stop_evt.set()
        if self._event_thread and self._event_thread.is_alive():
            self._event_thread.join(timeout=2.0)
        if self._auto_thread and self._auto_thread.is_alive():
            self._auto_thread.join(timeout=2.0)
        if self._server:
            self._server.stop()
            self._server = None
        if self.verbose:
            print("Servidor parado.")

    def _db(self):
        if not self._server:
            raise RuntimeError("Servidor não iniciado.")
        return self._server.data_bank

    def _event_loop(self):
        db = self._db()
        while not self._stop_evt.is_set():
            coils = db.get_coils(0, 120) or []
            if coils:

                # ==================  Eventos dos sensores =================

                self._handle_edge(Coils.Sensor_1_Caixote_Azul, coils, self._run_blue_line)
                
                self._handle_edge(Coils.Sensor_1_Caixote_Verde, coils, self._run_green_line)

                self._handle_edge(Coils.Sensor_1_Caixote_Vazio, coils, self._run_empty_line)

                # ====================  Botoes principais =================

                if(self._handle_edge(Coils.Emergency, coils, self._on_emergency_toggle)):
                    continue

                if(self._handle_edge(Coils.resetButton, coils, self._on_reset)):
                    continue

                if(self._handle_edge(Coils.Start, coils, self._on_start)):
                    continue

            self._stop_evt.wait(self.scan_time)

    def _handle_edge(self, addr: int, coils: List[int], callback: Callable[[], None]) -> None:

        flag_acionou = False
        cur = int(bool(coils[addr])) if addr < len(coils) else 0

        if addr == Coils.Sensor_1_Caixote_Vazio:
            prev = self._prev_coils.get(addr, 1) 

            if cur != prev:
                print(f"Sensor vazio mudou vazio de estado: {prev} → {cur}")
                if(cur == 0):
                    print('vou na linha vazio')
                    callback()
                flag_acionou = True

            self._prev_coils[addr] = cur

            return flag_acionou

        if addr == Coils.Sensor_1_Caixote_Azul :
            prev = self._prev_coils.get(addr, 1) 

            if cur != prev:
                print(f"Sensor azul mudou de estado: {prev} → {cur}")
                if(cur == 0):
                    print('vou na linha azul')
                    callback()
                flag_acionou = True

            self._prev_coils[addr] = cur

            return flag_acionou


        if  addr == Coils.Sensor_1_Caixote_Verde:
            prev = self._prev_coils.get(addr, 1) 

            if cur != prev:
                print(f"Sensor verde mudou de estado: {prev} → {cur}")
                if(cur == 0):
                    print('vou atuar na linha verde')
                    callback()
                flag_acionou = True

            self._prev_coils[addr] = cur

            return flag_acionou


        if addr == Coils.Emergency:
            prev = self._prev_coils.get(addr, 1) 

            if cur != prev:
                print(f"Emergência mudou: {prev} → {cur}")
                callback()
                flag_acionou = True

            self._prev_coils[addr] = cur

            return flag_acionou

        prev = self._prev_coils.get(addr, 0)

        if cur == 1 and prev == 0 :
            callback()
            flag_acionou = True

        self._prev_coils[addr] = cur

        return flag_acionou

    # ================ Buttons ===================

    def _on_start(self):
        
        if self.verbose:
            print("Start")
        
        if self.machine_state == "emergency":
            return
        
        if self.machine_state == "running":
            return
        
        self.machine_state = "running"
        self.sequence_step = "idle"

        self._auto_thread = threading.Thread(target=self._auto_cycle, name="auto-cycle", daemon=True)
        self._auto_thread.start()


    def _on_stop(self):
        if self.verbose:
            print("Stop")
        self.machine_state = "idle"
        self._all_off()

    def _on_reset(self):
        if self.verbose:
            print("Reset")

        print(self.get_sensor(Coils.Emergency))
        if(self.get_sensor(Coils.Emergency) == True):
            self.sequence_step = "idle"
            self.machine_state = "idle"

    def _on_emergency_toggle(self):

        print('valor da emergencia: ', self.get_sensor(Coils.Emergency))

        if self.machine_state != "emergency"  and self.get_sensor(Coils.Emergency) == False:
            if self.verbose:
                print("Emergency ON")

            self.machine_state = "emergency"
            print('settando emergencia')
            self._all_off()
        elif self.machine_state != "emergency"  and self.get_sensor(Coils.Emergency) == True:
            if self.verbose:
                print("Emergency OFF")


    # ================ funcoes auxiliares ===================

    def get_sensor(self, sensor_address)-> bool:
        db = self._db()
        return db.get_coils(sensor_address, 1)[0]
    
    def set_actuator(self, coil_adress: int, value: bool)-> bool:
        db = self._db()
        db.set_discrete_inputs(coil_adress, [int(value)])


    def t_run_blue_line(self):
    
        global blue_line_running

        if(blue_line_running == True):
            return
        
        blue_line_running = True

        self.set_actuator(Inputs.Caixote_Azul_Conveyor_1, True)
        self.set_actuator(Inputs.Caixote_Azul_Conveyor_2, True)

        while(self.get_sensor(Coils.Sensor_2_Caixote_Azul) == False):
            time.sleep(0.1)
            pass

        print('tocou o sensor blue, vou pausar')

        time.sleep(0.5)
        self.set_actuator(Inputs.Caixote_Azul_Conveyor_1, False)
        self.set_actuator(Inputs.Caixote_Azul_Conveyor_2, False)

        blue_line_running = False

    def t_run_green_line(self):

        global green_line_running

        if(green_line_running == True):
            return
        
        green_line_running = True

        self.set_actuator(Inputs.Caixote_Verde_Conveyor_1, True)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_2, True)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_3, True)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_4, True)

        while(self.get_sensor(Coils.Sensor_2_Caixote_Verde) == False):
            time.sleep(0.1)
            pass

        print('tocou o sensor green, vou pausar')

        time.sleep(0.5)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_1, False)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_2, False)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_3, False)
        self.set_actuator(Inputs.Caixote_Verde_Conveyor_4, False)

        green_line_running = False

    def t_run_empty_line(self):
        global empty_line_running
        print(empty_line_running)

        if(empty_line_running == True):
            return
        
        empty_line_running = True

        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_1, True)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_2, True)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_3, True)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_4, True)

        while(self.get_sensor(Coils.Sensor_2_Caixote_Vazio) == False):
            time.sleep(0.1)
            pass

        print('tocou o sensor, vou pausar')

        time.sleep(0.5)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_1, False)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_2, False)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_3, False)
        self.set_actuator(Inputs.Caixote_Vazio_Conveyor_4, False)

        empty_line_running = False


    def _run_blue_line(self):
        if(self.machine_state != 'running'): return
        print('ligando linha azul')

        blue_line = threading.Thread(target=self.t_run_blue_line, name="blue_line", daemon=True)
        blue_line.start()

    def _run_green_line(self):
        if(self.machine_state != 'running'): return
        print('ligando linha verde')

        green_line = threading.Thread(target=self.t_run_green_line, name="green_line", daemon=True)
        green_line.start()

    def _run_empty_line(self):
        if(self.machine_state != 'running'): return
        print('ligando linha empty')

        empty_line = threading.Thread(target=self.t_run_empty_line, name="empty_line", daemon=True)
        empty_line.start()

    

    # ================ modo automático ======================

    
    def _feeder_queue(self):
        fila = deque(['blue', 'green', 'empty'])
        print('minha fila: ', fila)
        while not self._stop_evt.is_set():
            for _ in range(len(fila)):
                tipo = fila[0]
                print(f"Checando: {tipo}")
                
                if tipo == 'blue':
                    sensor = Coils.Sensor_2_Caixote_Azul
                elif tipo == 'green':
                    sensor = Coils.Sensor_2_Caixote_Verde
                elif tipo == 'empty':
                    sensor = Coils.Sensor_2_Caixote_Vazio
                else:
                    sensor = None

                if sensor is not None and self.get_sensor(sensor) == True:
                    print(f"Ação tomada para: {tipo}")

                    time.sleep(7)


                    # Exemplo: self._run_line(tipo)
                    
                    fila.rotate(-1)
                    break
                else:
                    fila.rotate(-1)
            time.sleep(0.1)

    def _auto_cycle(self):

        if self.verbose:
            print("Ciclo automático iniciado")

        feeder = threading.Thread(target=self._feeder_queue, name="feeder", daemon=True)
        feeder.start()
        
        while self.machine_state == "running":
            step = self.sequence_step
            if step == "idle":

                # se o sensor de uma determinada

                time.sleep(0.1)
                pass
            elif step == "wait_inspection":
                time.sleep(0.1)
                pass
            elif step in ("sorter1", "sorter2"):
                time.sleep(0.1)
                pass
            elif step == "exit_wait":
                time.sleep(0.1)
                pass
            else:
                time.sleep(0.05)
        if self.verbose:
            print("Ciclo automático encerrado")

    def _write_coil(self, addr: int, value: bool) -> None:
        db = self._db()
        with self._lock:
            db.set_coils(addr, [1 if value else 0])

    def _all_off(self) -> None:
        self._write_coil(Inputs.EntryConveyor, False)

    def snapshot(self):
        db = self._db()
        print(f"[{datetime.now().strftime('%H:%M:%S')}]")
        print(f"estado={self.machine_state} passo={self.sequence_step}")

        print("=" * 60, "\n")

def main():
    srv = FactoryModbusEventServer(host="0.0.0.0", port=5020, scan_time=0.05, verbose=True)
    srv.start()
    try:
        while True:
            srv.snapshot()
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()

if __name__ == "__main__":
    main()
