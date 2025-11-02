# Documentação — FactoryModbusEventServer (servidor Modbus + loop de eventos)

Este documento explica o funcionamento do arquivo `server.py`, que implementa o servidor Modbus responsável por:

* Fazer leitura cíclica dos sensores (coils)
* Encaminhar eventos para o `EventProcessor`
* Controlar estados globais da máquina (running, emergency, stopped)
* Integrar os controladores (`LineController`, `AutoController`, `EventProcessor`)
* Armazenar e expor o estado dos atuadores (esteiras, turntables etc.)

Arquivo referenciado: `server.py`

---

## 🧩 Visão Geral da Classe

A classe principal é:

```python
class FactoryModbusEventServer(Stoppable):
```

Ela herda de `Stoppable`, que fornece suporte a `stop_event` (thread-safe).

Esse servidor é **o núcleo do sistema**, porque:

* É ele quem recebe e armazena os valores de I/O
* Roda o event loop que detecta mudança nos coils
* Expõe funções para leitura/escrita de sensores e atuadores
* Gerencia o estado de operação da máquina industrial

---

## 🔍 Atributos Principais

| Atributo        | Finalidade                                                         |
| --------------- | ------------------------------------------------------------------ |
| `host`, `port`  | Configura o servidor Modbus TCP                                    |
| `scan_time`     | Tempo entre leituras de sensores (polling)                         |
| `machine_state` | Estado global: `running`, `stopped`, `emergency`, etc.             |
| `sequence_step` | Etapa atual da sequência automática                                |
| `lines`         | Instância de `LineController` (controle físico das esteiras/mesas) |
| `auto`          | Instância de `AutoController` (lógica automática completa)         |
| `events`        | Instância de `EventProcessor` (detecção de bordas e eventos)       |
| `_server`       | Instância real do `ModbusServer` da lib `pyModbusTCP`              |
| `_event_thread` | Thread que executa `_event_loop()`                                 |

---

## 🚀 Ciclo de Vida (start/stop)

### `start()`

1. Cria o servidor Modbus TCP
2. Inicia thread de polling (`_event_loop`)
3. Exibe log de inicialização

### `stop()`

1. Sinaliza fim via `stop_event`
2. Finaliza thread de eventos
3. Finaliza `AutoController`
4. Interrompe servidor Modbus real
5. Opcionalmente imprime "Servidor parado."

---

## 📡 Acesso aos Sensores e Atuadores

### `get_sensor(addr)`

Lê **coil** no endereço `addr` → retorna `True/False`.

### `get_actuator(addr)`

Lê entrada discreta (DI) no endereço `addr` — usado para debug ou telemetria.

### `set_actuator(addr, value)`

Escreve em entrada discreta (simulação de atuador).
Usado por: `LineController`, `AutoController`, `RandomFeeder`.

### `_write_coil(addr, value)`

Escreve coil real no datobank (trava com mutex `_lock`).

---

## 🔄 Loop de Eventos — `_event_loop()`

Executado continuamente em thread separada:

```
while not stop_event.is_set():
    coils = db.get_coils(0, 120)
    if coils:
        self.events.handle_scan(coils)
    sleep(scan_time)
```

Esse método **não decide nada** — apenas coleta dados e repassa para `EventProcessor`.

---

## 🛎️ Handlers de Botões Físicos

Chamados pelo `EventProcessor` quando sensores detectam borda:

| Função                   | Quando é chamada              | Efeito                                                           |
| ------------------------ | ----------------------------- | ---------------------------------------------------------------- |
| `_on_start()`            | Botão Start → borda de subida | Troca estado p/ `running`, liga atuadores, inicia AutoController |
| `_on_stop()`             | Botão Stop                    | Para linhas, desliga tudo, mantém sistema não emergencial        |
| `_on_reset()`            | Botão Restart                 | Retorna máquina a `Running`, religando atuadores                 |
| `_on_emergency_toggle()` | Botão Emergency alternado     | Entra/sai do modo `emergency`, desliga tudo imediatamente        |

---

## 🧪 Função de Debug — `snapshot()`

Imprime o estado global **somente quando houver mudança**:

```
[14:38:32] estado=running passo=idle
============================================================
```

Útil para reduzir spam no terminal.

---

## 🔗 Relação com Outros Módulos

```
FactoryModbusEventServer
 ├── LineController  -> controla esteiras e turntable
 ├── AutoController  -> gerencia fila, HAL, pedidos, TT1 e TT2
 └── EventProcessor  -> detecta eventos e chama callbacks
```

O servidor atua como **hub central**: todos os controladores compartilham acesso ao banco Modbus.

---