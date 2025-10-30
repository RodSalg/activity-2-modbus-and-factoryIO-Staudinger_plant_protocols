# simuladores/sumuladorModbusTCP.py
import time
import math
import random
import threading
from datetime import datetime
from typing import Optional, List
from pyModbusTCP.server import ModbusServer

from time import sleep

__all__ = ["FactoryModbusSimulator"]


class FactoryModbusSimulator:
    """
    Simulador Modbus TCP (pyModbusTCP)
    - Holding Registers 0..11 (40001..40012)
    - HR 0 e 1 fixos (status/alarme)
    - HR 2..11 dinâmicos (atualizados a cada update_period_s)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5020, update_period_s: float = 5.0, verbose: bool = True):
        self.host = host
        self.port = port
        self.update_period_s = update_period_s
        self.verbose = verbose

        self._server: Optional[ModbusServer] = None
        self._thread: Optional[threading.Thread] = None
        
        self._stop_evt = threading.Event()

        self._lock = threading.Lock()

    # ---------------- Public API ----------------
    def start(self) -> None:
        if self._server is not None:
            return  # já está iniciado

        self._server = ModbusServer(host=self.host, port=self.port, no_block=True)
        self._server.start()

        db = self._server.data_bank
        #db.set_coils...




        if self.verbose:
            print(f"[{datetime.now().isoformat(timespec='seconds')}] Modbus em {self.host}:{self.port}")
            print("HR 0..11 prontos; HR 2..11 atualizados a cada 5s.")

        # inicia thread de atualização
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._update_loop, name="modbus-sim-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._server:
            self._server.stop()
            self._server = None
        if self.verbose:
            print("Simulador parado.")

    def snapshot(self, count: int = 12) -> List[int]:
        """Retorna uma lista com os primeiros 'count' HRs (default 12)."""
        db = self._require_db()
        with self._lock:
            print(db.get_holding_registers(0, count))
            print(db.get_coils(0, 4))

    # ---------------- Internals ----------------
    def _require_db(self):
        if not self._server:
            raise RuntimeError("Servidor não iniciado. Chame start().")
        return self._server.data_bank

    def _update_loop(self):
        db = self._require_db()

    # def _update_loop(self):
    #     db = self._require_db()
    #     next_tick = time.time() + self.update_period_s

    #     while not self._stop_evt.is_set():
    #         # espera até o próximo ciclo
    #         wait_s = max(0.05, next_tick - time.time())
    #         self._stop_evt.wait(wait_s)

    #         if self._stop_evt.is_set():
    #             break

    #         next_tick += self.update_period_s

    #         with self._lock:
    #             # Atualiza HR 2..11 (10 registradores)
                
    #             pass

    #         if self.verbose:
    #             print(f"[{datetime.now().isoformat(timespec='seconds')}]")



def main():
    CONFIG = {
        "update_period": 5.0,
        "verbose": True,
        "modbus": {
            "host": "0.0.0.0",
            "port": 5020
        },
    } 
    
    modbus = FactoryModbusSimulator(
        host=CONFIG["modbus"]["host"],
        port=CONFIG["modbus"]["port"],
        update_period_s=CONFIG["update_period"],
        verbose=CONFIG["verbose"]
    )
    
    print("========== Iniciando servidor modbus ==========")
    modbus.start()

    try:
        print("Simuladores ativos. Pressione Ctrl+C para parar.")
        while True:
            modbus.snapshot(12)

            print("="*60, '\n')
            time.sleep(5)

            
    except KeyboardInterrupt:
        print("\nEncerrando simuladores...")
        
    finally:
        print("Parando simuladores...")
        try:
            modbus.stop()
        except Exception as e:
            print(f"Erro ao parar Modbus: {e}")
        
        print("todos os simuladores parados.")

if __name__ == "__main__":
    main()
