# simulators/random_feeder.py
import random
import threading
import time
from typing import Optional, Iterable, Tuple
from addresses import Esteiras, Inputs  # seus DIs


class RandomFeeder:
    """
        Emite aleatoriamente:
            - BLUE  = Caixote azul + Produto azul
            - GREEN = Caixote verde + Produto verde
            - OTHER = Caixote vazio
    Agora com suporte a offset entre pulsos (produto antes/depois do caixote).
    """

    def __init__(
        self, server, period_s: tuple[float, float] = (2.0, 5.0), pulse_ms: int = 180
    ):
        self.server = server
        self._th: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.period_s = period_s
        self.pulse_ms = pulse_ms

        # Cada item: (addr, offset_ms)
        # offset_ms > 0  -> aciona depois do primeiro
        # offset_ms < 0  -> aciona antes do primeiro
        # Dica: ajuste os offsets do GREEN para acertar a sobreposição física.
        self.combos = {
            "BLUE": [
                (Inputs.Emmiter_Caixote_Azul, 0),
                (Inputs.Emmiter_Product_Azul, 0),
            ]
        }

    def _pulse(self, di_addr: int):
        self.server.set_actuator(di_addr, True)
        time.sleep(self.pulse_ms / 1000.0)
        self.server.set_actuator(di_addr, False)

    def _pulse_combo(self, items: Iterable[Tuple[int, int]]):
        """
        Dispara todos os emissores do combo respeitando offsets relativos ao PRIMÁRIO (offset==0).
        Implementação simples: cria threads por item, dorme o offset e pulsa.
        """
        # 1) descubra o menor offset (pode ser negativo)
        min_off = min((off for _, off in items), default=0)

        # 2) defina um "marco" no futuro que garanta que até o menor offset tenha tempo
        base = time.time() + max(0.0, (-min_off) / 1000.0)

        threads = []

        def _runner(addr: int, off_ms: int):
            fire_at = base + (off_ms / 1000.0)
            delay = fire_at - time.time()
            if delay > 0:
                time.sleep(delay)
            self._pulse(addr)

        for addr, off_ms in items:
            t = threading.Thread(target=_runner, args=(addr, off_ms), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def start(self):
        if self._th and self._th.is_alive():
            return
        self._stop.clear()
        self._th = threading.Thread(
            target=self._loop, name="random-feeder", daemon=True
        )
        self._th.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        min_gap = 0.2  # 200 ms para não empilhar pulsos
        last = 0.0
        while not self._stop.is_set():
            if self.server.machine_state == "running":

                pick = "BLUE"
                combo = [
                    (addr, off) for (addr, off) in self.combos[pick] if addr is not None
                ]

                now = time.time()
                if now - last < min_gap:
                    time.sleep(min_gap - (now - last))

                if combo:
                    if getattr(self.server, "verbose", False):
                        print(f"[feeder] {pick} -> {combo}")
                    self._pulse_combo(combo)
                    last = time.time()

            time.sleep(random.uniform(*self.period_s))
