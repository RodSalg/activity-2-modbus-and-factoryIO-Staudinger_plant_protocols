# Staudinger Plant - Protocols & Simulators

Este diretório contém a implementação e a documentação para os exercícios da atividade sobre protocolos (Modbus) e integração com o Factory I/O — incluindo simuladores, controladores e serviços auxiliares.

**Visão geral:**
- Código principal em `src/`.
- Documentação em `docs/`.
- Dados de exemplo em `orders/`.

**Pré-requisitos**
- Python 3.8+ instalado
- Dependências: execute `pip install -r requirements.txt` a partir da raiz do projeto (ou do diretório `New Project` se preferir).

**Instalação rápida**
1. Abra um terminal na pasta `New Project`:

```powershell
cd "New Project"
pip install -r ..\requirements.txt
```

2. Rodar a aplicação principal (modo de desenvolvimento):

```powershell
cd "New Project"
python -m src.main
```

Ou rodar apenas o servidor (separadamente):

```powershell
python -m src.server
```

Observação: os módulos também podem ser executados diretamente (por exemplo, `python src/simulators/random_feeder.py`) — ver `docs/simulators/random_feeder.md` para detalhes.

**Estrutura dos diretórios**
- `src/` — código-fonte: `addresses.py`, `main.py`, `server.py`, `utils.py`, controllers, services, simulators.
- `docs/` — documentação detalhada por módulo.
- `orders/` — arquivos de exemplo/fixtures.

**Onde começar**
- Leia `docs/main.md` para entender o fluxo geral.
- Depois leia `docs/server.md` e `docs/addresses.md` para configurar a comunicação.
- Use `docs/simulators/random_feeder.md` para iniciar um simulador local e `docs/services/orders.md` para ver o formato de pedidos.

Contribuições e correções são bem-vindas — abra uma issue ou um PR no repositório.
# Fluxograma Geral do Sistema

Abaixo está um fluxograma **Mermaid** que representa o caminho completo do sinal: dos sensores (ou simulador) até as decisões de automação e atuadores (esteiras/turntables).

```mermaid
flowchart LR
    subgraph Origem
      RF[RandomFeeder]
      HW[Sensores e Botoes]
    end

    subgraph Servidor_Modbus
      EV[EventProcessor events.py]
      SRV[FactoryModbusEventServer server.py]
    end

    subgraph Controle_Automatico
      AUTO[AutoController auto.py]
      ORD[OrderManager orders.py]
    end

    subgraph Acionamentos
      LINES[LineController lines.py]
      TT[Turntable principal]
      TT2[Turntable 2]
    end

    RF -->|Inputs| SRV
    HW -->|Coils| SRV

    SRV -->|polling| EV
    EV -->|bordas Start Stop Emergency Restart| SRV
    EV -->|chegada e HAL| AUTO

    AUTO -->|turntable async| LINES
    AUTO -->|hal sequence| AUTO
    AUTO -->|classificacao| AUTO
    AUTO <-->|consulta pedidos| ORD

    LINES --> TT
    AUTO --> TT2

    TT --> SRV
    TT2 --> SRV

    SRV <--> AUTO
```

> **Leitura do diagrama:**
>
> * **EventProcessor** lê bordas e decide **o que** sinalizar: ligar linha azul/verde/vazio, enfileirar chegada, acionar HAL ou botões.
> * **AutoController** decide **para onde** enviar a peça (estoque ou pedido) e orquestra a turntable principal e **Turntable 2** (TT2).
> * **LineController** traduz decisões em **atuadores** (giro e esteiras), com **watcher** para desligar belt ao atingir limites.
> * **OrderManager** informa se há pedidos e consome caixas atendidas.
> * **Server** faz o **polling**, mantém estados globais e expõe leitura/escrita do banco Modbus.

---

# README (Resumo do Projeto)

## Visão Geral

Este projeto implementa uma **célula de automação** simulada com Modbus, turntables e esteiras, suportando **classificação HAL**, **estoque** e **atendimento de pedidos**. Inclui um **feeder aleatório** para testes sem hardware.

**Principais módulos:**

* `server.py`        — Servidor Modbus + loop de eventos + estados globais
* `events.py`        — Detecção de bordas e despacho de callbacks
* `auto.py`          — Lógica automática (fila de chegadas, HAL, turntable principal e TT2)
* `lines.py`         — Acionamento físico (giro, belt, watchers)
* `orders.py`        — Fila de pedidos (FIFO) e consumo por cor
* `random_feeder.py` — Simulador de entradas (caixote/produto) com offsets
* `addresses.py`     — Mapa de **Coils/Inputs/Esteiras**
* `utils.py`         — Utilidades (`now()`, `Stoppable`)

## Arquitetura (resumo)

1. **Server** (Modbus) faz polling dos **coils** e repassa para o `EventProcessor`.
2. **EventProcessor** detecta bordas (Start/Stop/Emergency/HAL/Arrivals) e chama `AutoController` ou handlers do `Server`.
3. **AutoController** decide rotas (**ORDER** ou **NO_ORDER**) com apoio do `OrderManager`, aciona `LineController` para a turntable principal e coordena **TT2**.
4. **LineController** traduz comandos em **atuadores** (`set_actuator`) e executa watchers de limite.
5. **RandomFeeder** injeta eventos (`Inputs`) simulando hardware real.

## Fluxo alto nível

* **Chegada** → `EventProcessor.enqueue_arrival(...)` → `AutoController` ativa a turntable principal, move peça e executa **pós-limite** até o final da produção.
* **HAL** → `hal_sequence()` amostra `Vision_Blue/Green` → `on_hal_classified()` → **TT2** (pedido) ou **estoque**.
* **Pedidos** → `OrderManager.create_order(...)` → consumidos por `_tt2_cycle_order()`.

## Execução (exemplo minimal)

```bash
python main.py
```

* `main.py` cria `FactoryModbusEventServer`, `AutoController` e `RandomFeeder`.
* Para iniciar a automação, acione o **Start** (coil/button).
* `Ctrl+C` encerra com **stop** limpo de threads e atuadores.

> **Dica:** Ajuste `period_s` e `pulse_ms` no `RandomFeeder` para calibrar a cadência de testes.

## Operação (botões)

* **Start**: entra em `running`, habilita automação
* **Stop**: para as linhas (sem emergência)
* **Emergency (toggle)**: entra/retorna de `emergency` e desliga atuadores
* **Restart**: restabelece estados e religa atuadores
* **Create_OP**: cria pedidos (usar via `events`/lógica do operador)

## Estrutura de Pastas (sugestão)

```
.
├─ controllers/
│  ├─ auto.py
│  ├─ events.py
│  └─ lines.py
├─ simulators/
│  └─ random_feeder.py
├─ services/
│  └─ orders.py
├─ addresses.py
├─ server.py
├─ utils.py
└─ main.py
```

---

**Autores:** 

1. Thiago Rodrigo Monteiro Salgado
2. Lukas Lujan Moreira
3. Nathalia Damasceno Colares