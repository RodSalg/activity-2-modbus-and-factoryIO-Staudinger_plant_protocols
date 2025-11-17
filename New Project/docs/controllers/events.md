# Documentação das Funções — EventProcessor

## Sumário
- Visão Geral
- Funções públicas (`handle_scan`)
- Detecção de bordas
- Sensores monitorados

Este documento descreve o funcionamento do arquivo `events.py`.

---

## 🧩 Visão Geral

A classe **EventProcessor** é responsável por:

* Monitorar sensores e botões via leitura de coils
* Detectar **bordas (transições) de sinais** e disparar callbacks
* Acionar rotinas do controlador automático (`AutoController`) quando necessário
* Parar e iniciar linhas de produção de acordo com sensores

Este módulo é o "tradutor" entre o hardware (sensores Modbus/IO) e a lógica do sistema.

---

## 🔍 Atributos e Inicialização

### `__init__(self, server, lines_controller, verbose=True)`

Configura o objeto que:

* Recebe o `server` (interface que acessa sensores/atuadores)
* Recebe `lines_controller` (responsável por acionar esteiras/motores)
* Armazena histórico de valores anteriores das coils (`_prev`), necessário para detecção de bordas
* Mantém estado anterior da HAL (`_hal_prev`) para detectar entrada de peça

Não inicia threads nem executa fluxo — apenas prepara o estado.

---

## 📌 Funções Públicas

### `handle_scan(self, coils_snapshot)`

Função principal chamada a cada ciclo de leitura dos sensores.

* Recebe um snapshot da entrada digital (`coils_snapshot`)
* Detecta borda em sensores do **emitter** → inicia linha correspondente
* Detecta chegada de caixas no sensor 2 → chama `_on_arrival()`
* Detecta Load_Sensor → aciona TT2 caso esteja ociosa
* Detecta botões físicos (Start / Stop / Emergency / Restart)
* Detecta borda do sensor HAL e delega para `AutoController.enqueue_hal`

É responsável por conectar sinais físicos com o restante do sistema.

---

### `_handle_edge(self, addr, coils, callback)`

Função genérica para detectar borda **de subida** (0→1) ou caso especial:

* Trata sensores de CAIXOTE 1 com borda invertida (1→0)
* Trata emergência com log especial
* Para demais coils, dispara callback apenas quando **cur==1 e prev==0**

Retorna `True` caso a borda tenha sido acionada.

---

### `_on_arrival(self, tipo, sensor_addr, stop_fn)`

Chamado quando um caixote passa no segundo conjunto de sensores.

* Executa `stop_fn()` para parar a esteira da cor correspondente
* Chama `server.auto.enqueue_arrival(...)` para mandar o item para o fluxo da turntable

É o ponto onde a chegada física vira evento lógico na automação.

---

### `_handle_edge_fall(self, addr, coils, callback)`

Detecção de **borda de descida** (1→0).
Usado em situações em que o callback deve acontecer **quando o sensor apaga**, não quando acende.

---

### `_on_create_op(self)`

Chamado quando o coil `Create_OP` sofre borda.
Ele:

1. Cria um novo pedido (`orders.create_order()`)
2. Alterna o modo do AutoController para `order` para priorizar atendimento

Simula operação iniciada por operador físico.

---

## ⚙️ Sensores Monitorados

| Endereço                       | Função                        | Ação disparada                            |
| ------------------------------ | ----------------------------- | ----------------------------------------- |
| `Sensor_1_Caixote_*`           | Detecta caixote no emissor    | Liga linha azul/verde/vazio               |
| `Sensor_2_Caixote_*`           | Detecta chegada               | Para linha + envia para AutoController    |
| `Load_Sensor`                  | Detecta peça parada sobre TT2 | TT2 faz descarte automático se ociosa     |
| `Emergency`                    | Botão físico de emergência    | Aciona callback de parada total           |
| `Start / Stop / RestartButton` | Comandos físicos              | Alteram estado do servidor                |
| `Sensor_Hall`                  | HAL de classificação          | Envia evento para processamento da câmera |

---

## 🔄 Fluxo Resumido

```
leitura coils → handle_scan → detecta bordas
                                 ↓
                      _handle_edge / _handle_edge_fall
                                 ↓
        [linhas] run_blue_line(), stop_green_line(), etc
        [auto] enqueue_arrival() / enqueue_hal()
```

---

## ✅ Pontos Importantes

* O módulo **não controla atuadores diretamente**, apenas chama callbacks
* A responsabilidade dele é **detecção de evento**, não decisão
* A tabela `_prev` permite edge detection mesmo em polling
* A lógica HAL é tratada separadamente para evitar múltiplos triggers

---