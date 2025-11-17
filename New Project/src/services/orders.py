# orders.py
from collections import deque
from dataclasses import dataclass
from services.DAO import MES


@dataclass
class Order:
    color: str  # "BLUE" | "GREEN" | "OTHER"
    boxes_total: int  # quantas caixas esse pedido precisa
    boxes_done: int = 0  # progresso

    @property
    def done(self) -> bool:
        return self.boxes_done >= self.boxes_total

    def can_fulfill(self, klass: str) -> bool:
        # atende somente se a cor bate e ainda falta caixa
        return (klass == self.color) and (not self.done)

    def consume_one_box(self) -> None:
        if not self.done:
            self.boxes_done += 1


class OrderManager:
    def __init__(self, verbose: bool = True):
        self.q = deque()
        self.verbose = verbose

    def has_pending(self) -> bool:
        return any(not o.done for o in self.q)

    def create_order(self, color: str, boxes: int, count: int = 1) -> None:
        # empilha N pedidos iguais (count)
        for _ in range(max(1, int(count))):
            self.q.append(Order(color=color, boxes_total=int(boxes)))
        if self.verbose:
            print(f"[ORDER] criados: {count} pedido(s) - cor={color} caixas={boxes}")

    def can_fulfill(self, klass: str) -> bool:
        # Retorna True se EXISTE algum pedido aberto que possa ser atendido
        # (não apenas o primeiro da fila). Isso permite que a HAL classifique
        # como ORDER quando qualquer pedido pendente compatível existir.
        for o in self.q:
            if not o.done and o.can_fulfill(klass):
                return True
        return False

    def consume(self, klass: str) -> None:
        # consome no primeiro pedido compatível/aberto
        for o in self.q:
            if o.can_fulfill(klass):
                o.consume_one_box()
                if self.verbose:
                    print(
                        f"[ORDER] consumido 1 caixa {klass} -> {o.boxes_done}/{o.boxes_total}"
                    )
                # atualiza o armazenamento persistente (orders.json)
                try:
                    cfg = MES()
                    consumed = cfg.consume_persistent_order_by_color(klass)
                    if self.verbose and consumed:
                        print(f"[ORDER] ordem persistida atualizada para cor={klass}")
                except Exception:
                    # não interrompe o fluxo de execução principal se falhar
                    if self.verbose:
                        print(
                            f"[ORDER] aviso: não foi possível atualizar orders persistido para {klass}"
                        )
                break
        # limpeza de pedidos finalizados à esquerda
        while self.q and self.q[0].done:
            finished = self.q.popleft()
            if self.verbose:
                print(f"[ORDER] pedido concluído (cor={finished.color})")
