# orders.py
from collections import deque
from dataclasses import dataclass


@dataclass
class Order:
    color: str  # "BLUE" | "GREEN" | "EMPTY"
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
        # olha o primeiro pedido aberto
        for o in self.q:
            if not o.done:
                return o.can_fulfill(klass)
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
                break
        # limpeza de pedidos finalizados à esquerda
        while self.q and self.q[0].done:
            finished = self.q.popleft()
            if self.verbose:
                print(f"[ORDER] pedido concluído (cor={finished.color})")
