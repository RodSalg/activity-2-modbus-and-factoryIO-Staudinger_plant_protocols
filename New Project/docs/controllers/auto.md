# Documentação das Funções — AutoController

## Sumário
- Estrutura Geral
- Métodos principais (`start`, `stop`, `_arrival_worker`, `hal_sequence`)
- Fluxo principal

Este documento complementa o arquivo `auto.py`, explicando **o que cada função faz**, seu papel dentro do fluxo geral de automação e como interage com outros componentes.

---

## 📌 Estrutura Geral

A classe `AutoController` é responsável por:

* Gerenciar o ciclo automático do sistema (turntable, esteiras, HAL, pedidos, estoque)
* Controlar filas de chegada (`arrival_q`) e de saída (`tt2_q`)
* Executar workers em threads independentes
* Integrar lógica de classificação HAL + encaminhamento para estoque ou pedido
* Orquestrar o comportamento da **Turntable 1** e da **Turntable 2**

---

## 🔍 Métodos e Explicações

### `__init__(...)`

Inicializa toda a estrutura de controle automático, incluindo filas, flags de estado, threads e parâmetros de tempo. Não executa nada — só configura o ambiente.

Criado para permitir que o fluxo automático seja inicializado e interrompido de forma segura, com locks e variáveis consistentes.

---

### `start()`

Inicia o ciclo automático:

* Cria a thread principal (`_auto_cycle`)
* Inicializa o worker de chegada (`_arrival_worker`)
* Inicializa o worker da turntable 2 (`_tt2_worker`)
* Garante que o sistema só é iniciado uma vez mesmo com múltiplas chamadas

Função responsável por ativar o sistema de forma assíncrona.

---

### `stop()`

Interrompe o controlador automático:

* Seta evento de parada
* Envia `None` para fila da TT2 (sentinela)
* Realiza `join()` nas threads caso ainda estejam rodando

Função de desligamento seguro — evita threads zumbis ou filas travadas.

---

### `join(timeout)`

Método utilitário: permite sincronizar e aguardar término das threads do sistema.

---

### `_read(coil_enum)`

Função helper usada para ler sensores/atuadores com fallback seguro. Evita que exceções interrompam o ciclo.

Retorna sempre um booleano, mesmo se o servidor lançar erro.

---

### `enqueue_arrival(tipo, sensor_addr)`

Insere um evento (caixote azul/verde/vazio ou HAL) na fila `arrival_q`. Essa fila ativa o fluxo da Turntable 1.

Chamada tipicamente por eventos externos capturados via bordas de sensores.

---

### `enqueue_arrival_delayed(...)`

Agenda a entrada de um item na fila, porém com atraso — útil para casos onde múltiplas bordas ocorrem rapidamente e devem ser deduplicadas.

Evita duplicação via `self._pending_enq`.

---

### `_arrival_worker()`

Worker que consome a fila `arrival_q`:

1. Aguarda mesa giratória livre
2. Executa lógica específica por tipo (blue/green/empty)
3. Dispara a parte 2 da sequência (`_post_limit_sequence`)
4. Libera linha de produção
5. Lida com eventos HAL separadamente

É o núcleo da lógica da **Turntable 1**.

---

### `_auto_cycle()`

Thread principal que mantém o ciclo de execução enquanto `machine_state == "running"`.

Não executa ações de controle — apenas mantém o loop vivo. Serve como "coração" do sistema.

---

### `_post_limit_sequence(policy)`

Executa **Fase 2** do processo da Turntable 1 depois que o limite foi atingido:

* Aguarda watcher iniciar e terminar
* Retorna mesa ao centro
* Descarga para linha final
* Espera sensor final ou timeout

É responsável pelo transporte final da peça após classificação.

---

### `hal_sequence(...)`

Executa a lógica de classificação HAL:

* Alinha peça
* Amostra `Vision_Blue` e `Vision_Green` por janela de tempo
* Aplica debounce e define classe (`BLUE`, `GREEN`, `EMPTY`)
* Encaminha resultado via `on_hal_classified`

Função central para visão artificial + decisão de rota.

---

### `on_hal_classified(klass)`

Decide se a peça será enviada para pedido (ORDER) ou estoque (NO_ORDER).
Interage com `OrderManager`.

Resultado vai para `tt2_q` (Turntable 2).

---

### `_tt2_worker()`

Worker da Turntable 2 — consome fila `tt2_q` e executa:

* `_tt2_cycle_order()` para pedidos
* `_tt2_cycle_no_order()` para estoque

Mantém TT2 independente da Turntable principal.

---

### `_tt2_cycle_no_order()`

Fluxo completo da TT2 **sem pedido**:

1. Liga esteira final
2. Descarrega até *Discharg_Sensor*
3. Gira mesa (`turn ON`)
4. Descarrega até *Sensor_Final_Producao*
5. Para belt e retorna mesa

Representa o ciclo padrão de armazenamento.

---

### `_tt2_cycle_order(klass)`

Fluxo TT2 **com pedido**:

* Não gira mesa
* Descarrega diretamente para esteira central
* Aguarda ciclo do sensor de descarga
* Dá baixa no pedido (`orders.consume()`)

Prioriza entrega em vez de estocagem.

---

### `arm_tt2_if_idle(...)`

Permite agendar um `NO_ORDER` caso TT2 esteja ociosa — usado para manter fluxo contínuo quando não há pedidos.

---

### `_set_mode_order()` / `_set_mode_stock()`

Define política global do sistema:

* `order` → prioriza atender pedidos
* `stock` → ignora pedidos e envia tudo para estoque

Controlado automaticamente quando pedidos acabam.

---

### `_has_any_open_order()`

Wrapper seguro para verificar se ainda existem pedidos em aberto.

---

### `_should_route_to_order(klass)`

Define se uma peça deve ser enviada para CENTRAL (pedido) ou ESTOQUE.
Só retorna *True* quando:

* Modo atual é `order`
* Há pedidos pendentes
* A peça atende o pedido (ex: BLUE pedido, peça BLUE classificada)

---

## 🧩 Resumo do Fluxo Principal

```
Sensor → enqueue_arrival → _arrival_worker → turntable1
                                     ↓
                                hal_sequence
                                     ↓
                             on_hal_classified
                                     ↓
                                   tt2_q → _tt2_worker
```

---