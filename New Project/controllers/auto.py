# auto.py
from queue import Queue
import threading, time
from addresses import Coils, Inputs
from services.orders import OrderManager


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
        self._hal_busy = False

        # ======= Turntable 2 e Pedidos =======
        self.orders = OrderManager()  # gerencia pedidos A/B

        self.tt2_q: Queue[str] = Queue()  # fila própria da turntable 2
        self._tt2_worker_th = None
        self.turntable2_busy = False

        # Tempos e timeouts (ajuste conforme Factory I/O)
        self.TT2_GIRO_S = 1.6
        self.TT2_RETORNO_S = 1.6
        self.TT2_ENTRADA_TOUT = 8.0
        self.TT2_SAIDA_TOUT = 10.0

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

        if not self._tt2_worker_th or not self._tt2_worker_th.is_alive():
            self._tt2_worker_th = threading.Thread(
                target=self._tt2_worker, name="tt2-worker", daemon=True
            )
            self._tt2_worker_th.start()

        self._thread.start()

        # inicia consumidor da fila de chegadas
        if not self._arrival_worker_th or not self._arrival_worker_th.is_alive():
            self._arrival_worker_th = threading.Thread(
                target=self._arrival_worker, name="arrival-worker", daemon=True
            )
            self._arrival_worker_th.start()

        # inicia worker da Turntable 2
        if not self._tt2_worker_th or not self._tt2_worker_th.is_alive():
            self._tt2_worker_th = threading.Thread(
                target=self._tt2_worker, name="tt2-worker", daemon=True
            )
            self._tt2_worker_th.start()

    def stop(self, join_timeout: float = 2.0):
        """Para o consumidor da fila e aguarda as threads finalizarem."""
        try:
            # Envia sentinela para destravar o arrival_worker
            self.arrival_q.put(("__HALT__", -1))
            self.tt2_q.put("__HALT__")  # <<< adiciona essa linha
        except Exception:
            pass
        self.join(timeout=join_timeout)

    def _read(self, coil_enum):
        """Helper simples para ler coil/sensor (True/False)"""
        try:
            return bool(self.server.get_sensor(coil_enum.value))
        except Exception:
            return False

    # <<< OPCIONAL: implemente o que fazer com a classificação >>>
    def on_hal_classified(self, klass: str):
        # Se NÃO houver pedido -> TT2 ciclo padrão
        try:
            no_orders = not self.orders.has_pending()
        except Exception:
            no_orders = True  # fallback (se orders não tiver has_pending)

        if no_orders:
            self.tt2_q.put("NO_ORDER")
            if self.verbose:
                print("[HAL] sem pedido -> enfileirando ciclo padrão Turntable2")
        else:
            if self.verbose:
                print("[HAL] há pedidos -> fluxo por destino (A/B)")

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

    def enqueue_hal(self, sensor_addr: int) -> None:
        self.arrival_q.put(("HAL", sensor_addr))

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
                "return_time": 8.0,
                "exit_timeout": 100.0,
            },
            "green": {
                "turn": True,
                "belt": "forward",
                "stop_limit": "back",
                "belt_tout": 3.0,
                "feed_delay": 1.0,
                "return_time": 8.0,
                "exit_timeout": 100.0,
            },
            "empty": {
                "turn": True,
                "belt": "backward",
                "stop_limit": "front",
                "belt_tout": 3.0,
                "feed_delay": 1.0,
                "return_time": 8.0,
                "exit_timeout": 100.0,
            },
        }

        while not (stop_evt and stop_evt.is_set()):
            tipo, sensor_addr = self.arrival_q.get()

            if tipo == "__HALT__":
                self.arrival_q.task_done()
                break

            if tipo == "HAL":
                if self.server.verbose:
                    print("[arrival] HAL -> parar Esteira_Producao_2 e classificar")

                # 1) Para esteira produção 2 imediatamente
                self.server.set_actuator(Inputs.Esteira_Producao_2, False)

                # 2) Executa a rotina de classificação (aguarda resultado)
                result = self.hal_sequence()

                # 3) Após classificar (seja azul, verde ou vazio), religa a esteira
                if self.server.verbose:
                    print(
                        f"[HAL] classificação concluída ({result}), religando Esteira_Producao_2"
                    )
                self.server.set_actuator(Inputs.Esteira_Producao_2, True)

                self.arrival_q.task_done()
                continue

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

                # Dispara a FASE 2 (retorno + descarga) em paralelo
                threading.Thread(
                    target=self._post_limit_sequence,
                    args=(POLICY,),
                    name="post-limit",
                    daemon=True,
                ).start()

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

    def _post_limit_sequence(self, policy: dict):
        """
        Fase 2: só entra DEPOIS do watcher começar e terminar.
        1) Espera watcher iniciar (_belt_watching=True) com timeout curto.
        2) Espera watcher terminar (_belt_watching=False).
        3) Volta mesa ao centro (turn OFF) sem belt (tempo fixo).
        4) Descarrega: belt oposta + esteira final.
        5) Espera Sensor_Final_Producao (ou timeout) e para tudo.
        """

        # 0) aguarda o watcher COMEÇAR (evita atropelar o giro inicial)
        start_deadline = time.time() + 1.0  # até 1s para o watcher levantar
        while (
            not getattr(self.lines, "_belt_watching", False)
            and time.time() < start_deadline
        ):
            time.sleep(0.01)

        if not getattr(self.lines, "_belt_watching", False):
            if self.server.verbose:
                print(
                    "[post] watcher não iniciou; abortando pós-limite para não atropelar o giro."
                )
            self.turntable_busy = False
            return

        # 1) agora espera o watcher TERMINAR (limite atingido ou timeout interno)
        end_deadline = time.time() + 12.0  # segurança
        while (
            getattr(self.lines, "_belt_watching", False) and time.time() < end_deadline
        ):
            time.sleep(0.01)

        # 2) retorna mesa ao centro (sem belt)
        return_time = policy.get("return_time", 1.1)
        if self.server.verbose:
            print(f"[post] retornando turntable ao centro por ~{return_time}s")
        self.lines.set_turntable_async(turn_on=False, belt="stop")
        time.sleep(return_time)

        # 3) descarregar: esteira final produção
        if self.server.verbose:
            print(
                "[post] descarregando: belt=forward (SaidaEntrada) + esteira final produção ON"
            )

        self.lines._t_set_turntable(
            turn_on=None,
            belt="forward",  # descarregar
            stop_limit="back",  # quando belt=forward, vigia limite de trás
            belt_timeout_s=1.0,  # pode ajustar; 1.0–1.2 costuma ir bem
        )  # exemplo indicativo

        self.lines._activate(Inputs.Esteira_Producao_2, Inputs.Esteira_Estoque)  # já liga produção final

        self.lines.set_turntable_async(turn_on=None, belt="forward", stop_limit=None)

        # 4) espera saída na produção (ou timeout)
        exit_tout = policy.get("exit_timeout", 100.0)
        t0 = time.time()
        while (
            not self.server.get_sensor(Coils.Sensor_Final_Producao)
            and (time.time() - t0) < exit_tout
        ):
            time.sleep(0.02)

        # 5) para belt interna e produção; libera fila
        if self.server.verbose:
            print(
                "[post] Sensor_Final_Producao detectado ou timeout: parando belt interna e ligando esteira produção"
            )
        self.lines.turntable_belt_stop()
        self.lines.run_production_line()
        self.turntable_busy = False

    # ========== HAL Sequence ==========
    def hal_sequence(self, window_ms: int = 300, debounce: int = 2):
        """
        Janela de decisão após HAL=1:
          - Para Esteira_Producao_2 imediatamente
          - Observa Vision_Blue e Vision_Green por 'window_ms'
          - Se azul ≥ debounce -> BLUE
            senão, se verde ≥ debounce -> GREEN
            senão -> EMPTY
        """
        if self._hal_busy:
            return
        self._hal_busy = True
        try:
            print("[HAL] sequence: parando Esteira_Producao_2 e abrindo janela…")
            self.server.set_actuator(Inputs.Esteira_Producao_2, False)

            t_end = time.time() + (window_ms / 1000.0)
            seen_blue = 0
            seen_green = 0

            # amostragem rápida com “debounce” por contagem
            while time.time() < t_end and self.server.machine_state == "running":
                if self._read(Coils.Vision_Blue):
                    seen_blue += 1
                if self._read(Coils.Vision_Green):
                    seen_green += 1
                time.sleep(0.01)  # 10ms

            if seen_blue >= debounce:
                klass = "BLUE"
            elif seen_green >= debounce:
                klass = "GREEN"
            else:
                klass = "EMPTY"

            print(f"[HAL] classificado: {klass} (blue={seen_blue}, green={seen_green})")

            # gancho para sua lógica pós-classificação
            self.on_hal_classified(klass)
        finally:
            self._hal_busy = False

        # ========== TURN TABLE 2 ==========

    def _tt2_worker(self):
        stop_evt = getattr(self.server, "_stop_evt", None)
        while not (stop_evt and stop_evt.is_set()):
            job = self.tt2_q.get()
            if job == "__HALT__":
                self.tt2_q.task_done()
                break

            # aguarda mesa ficar livre
            while self.turntable2_busy and not (stop_evt and stop_evt.is_set()):
                time.sleep(0.01)

            self.turntable2_busy = True
            try:
                if job == "NO_ORDER":
                    self._tt2_cycle_no_order()
            finally:
                self.turntable2_busy = False
                self.tt2_q.task_done()

    def _tt2_cycle_no_order(self):
        """
        Sequência padrão quando não há pedidos:
        1) Liga Esteira Final 2.
        2) Liga discharge até detectar Discharg_Sensor, então para.
        3) Gira turntable (turn ON) por TT2_GIRO_S.
        4) Liga discharge novamente até Sensor_Final_Producao ou timeout.
        5) Desliga tudo e retorna mesa (turn OFF).
        """
        if self.server.machine_state != "running":
            return

        # 1) garante esteira final ligada
        self.server.set_actuator(Inputs.Esteira_Producao_2, True)

        # 2) entrada: discharge até sensor
        self.server.set_actuator(Inputs.Discharg_turn, True)
        t0 = time.time()
        while (not self.server.get_sensor(Coils.Discharg_Sensor)) and (
            time.time() - t0
        ) < self.TT2_ENTRADA_TOUT:
            time.sleep(0.02)
        self.server.set_actuator(Inputs.Discharg_turn, False)

        # 3) giro
        self.server.set_actuator(Inputs.Turntable2_turn, True)
        time.sleep(self.TT2_GIRO_S)

        # 4) descarga
        self.server.set_actuator(Inputs.Discharg_turn, True)
        t1 = time.time()
        while (not self.server.get_sensor(Coils.Sensor_Final_Producao)) and (
            time.time() - t1
        ) < self.TT2_SAIDA_TOUT:
            time.sleep(0.02)
        self.server.set_actuator(Inputs.Discharg_turn, False)

        # 5) retorno
        self.server.set_actuator(Inputs.Turntable2_turn, False)
        time.sleep(self.TT2_RETORNO_S)
        if self.verbose:
            print("[TT2] ciclo padrão concluído.")

    def _arm_tt2_if_idle(self, motivo: str):
        if not self.turntable2_busy:
            self.tt2_q.put("NO_ORDER")
            if self.verbose:
                print(f"[TT2] armado via {motivo} -> enfileirado NO_ORDER")

    # auto.py (dentro de AutoController)

    def arm_tt2_if_idle(self, motivo: str = "Load_Sensor"):
        """Arma o ciclo padrão da TT2 se ela não estiver ocupada."""
        return self._arm_tt2_if_idle(motivo)

    # Mantém a esteira de estoque ligada; não há desligamento automático aqui
    def _start_stock_belt(self):
        # Substitua Inputs.Esteira_Estoque pelo enum/ID que você usa de fato
        self._activate(Inputs.Esteira_Estoque)
        if self.verbose:
            print("[STOCK] Esteira_Estoque ON (mantém ligada)")

    def start_stock_belt(self):
        return self._start_stock_belt()
