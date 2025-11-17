# Documentação das Funções — OrderManager e Order

## Sumário
- Visão Geral
- `Order` (estrutura e métodos)
- `OrderManager` (fila, create_order, consume)
- Fluxo de pedidos

Arquivo de referência: `orders.py`

---

## 🧩 Visão Geral

O módulo `orders.py` implementa o sistema de **gerenciamento de pedidos** usado pelo `AutoController` para decidir se uma peça deve ir para **estoque (NO_ORDER)** ou **atendimento de pedido (ORDER)**.

Há duas estruturas principais:

| Classe         | Função                                                |
| -------------- | ----------------------------------------------------- |
| `Order`        | Representa um pedido individual (ex: 3 caixas verdes) |
| `OrderManager` | Mantém fila de pedidos, decide consumo e verificação  |

---

## 📌 Classe `Order`

Representa **um único pedido**, contendo:

* `color`: cor da caixa exigida (`"BLUE"`, `"GREEN"` ou `"EMPTY"`)
* `boxes_total`: quantidade total de caixas que o pedido requer
* `boxes_done`: progresso atual (quantas já foram atendidas)

### `done` (property)

Retorna `True` se o pedido já foi totalmente atendido:

```python
return self.boxes_done >= self.boxes_total
```

### `can_fulfill(klass)`

Retorna `True` se **essa peça** pode atender o pedido.
Regras:

1. A cor deve ser igual (`klass == self.color`)
2. O pedido ainda não pode estar completo

Usado antes de enviar peça para TT2.

### `consume_one_box()`

Incrementa o progresso do pedido **somente se ainda houver caixas faltando**.

---

## 📌 Classe `OrderManager`

Gerencia vários pedidos simultaneamente usando `deque` como fila FIFO.

### Atributos:

| Atributo       | Função                                         |
| -------------- | ---------------------------------------------- |
| `self.q`       | Fila de objetos `Order` (ordem de atendimento) |
| `self.verbose` | Se ativo, imprime logs sobre pedidos           |

---

### `has_pending()`

Retorna `True` se existe **pelo menos um pedido ainda não finalizado**.

Usado pelo `AutoController` na decisão: *modo order* vs *modo stock*.

### `create_order(color, boxes, count=1)`

Cria **N pedidos idênticos** e os adiciona à fila.
Exemplo: `create_order("GREEN", 4, 2)` cria 2 pedidos, cada um exigindo 4 caixas verdes.

### `can_fulfill(klass)`

Verifica apenas **o primeiro pedido aberto da fila**.
Retorna `True` se a peça atual pode ser usada nele.

Usado na lógica de:

```python
self.orders.can_fulfill(klass)
```

### `consume(klass)`

Consome uma caixa **do primeiro pedido compatível**.
Fluxo:

1. Percorre a fila até encontrar um pedido que aceite a cor
2. Chama `consume_one_box()`
3. Se o pedido for concluído, ele é removido da fila (`popleft()`)
4. Imprime logs de progresso se `verbose=True`

Esse método é chamado somente após a peça passar pela TT2 em modo pedido.

---

## 🔄 Resumo do Fluxo de Pedido

```
create_order → fila de pedidos
                ↓
on_hal_classified decide: ORDER ou NO_ORDER
                ↓
_tt2_cycle_order chama orders.consume(klass)
                ↓
Pedido concluído? → removido da fila
```

---

## ✅ Pontos Importantes

* O `OrderManager` **não decide rotas de peça**, apenas informa se pode atender
* A fila é processada em ordem FIFO: primeiro pedido aberto é sempre prioridade
* O sistema permite múltiplos pedidos simultâneos, mas TT2 atende um por vez
* Funções nunca removem pedidos parcialmente — só após conclusão

---