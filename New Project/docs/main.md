# Documentação — main.py (Fluxo de Inicialização do Sistema)

## Sumário
- Visão Geral
- Função principal: `main()`
- Fluxo de Inicialização
- Tratamento de interrupção

Arquivo de referência: `main.py`

---

## Fluxograma de Inicialização

```mermaid
flowchart TD
    A[main] --> B[Create FactoryModbusEventServer — srv]
    B --> C[Create AutoController — auto (attach to srv)]
    C --> D[Create RandomFeeder — feeder (optional)]
    D --> E[Start srv and feeder]
    E --> F[Main loop: snapshot every 2s]
    F --> G[Ctrl+C (KeyboardInterrupt)]
    G --> H[auto.stop / srv.stop / feeder.stop — clean shutdown]
    style A fill:#f9f,stroke:#333,stroke-width:1px
    style H fill:#fdd,stroke:#333,stroke-width:1px
```
```

> Observação: o `AutoController` só passa a executar o ciclo automático quando o operador aciona o botão `Start` (coil). O `RandomFeeder` é opcional e serve para testes sem hardware.

## 🧩 Função principal: `main()`

A função `main()` é responsável por iniciar todo o sistema de automação. O fluxo executado é o seguinte:

### 1️⃣ **Instancia o servidor Modbus com detecção de eventos**

```python
srv = FactoryModbusEventServer(
    host="0.0.0.0", port=5020, scan_time=0.05, verbose=True
)
```

* Inicia um servidor Modbus-TCP que fará polling dos sensores
* `scan_time=0.05` → leitura a cada 50ms
* `verbose=True` → imprime logs no terminal

### 2️⃣ **Cria o controlador automático**

```python
auto = AutoController(srv, verbose=True)
srv.auto = auto
```

* `AutoController` gerencia turntables, filas, pedidos, HAL, etc.
* A instância é anexada ao servidor para permitir integração com eventos

### 3️⃣ **Instancia o simulador de alimentação (opcional)**

```python
feeder = RandomFeeder(srv, period_s=(8, 12), pulse_ms=360)
```

* Simula chegada de caixas automaticamente
* `period_s=(8,12)` → uma peça a cada 8–12 s
* `pulse_ms=360` define largura do pulso digital (sensor ON)

### 4️⃣ **Inicia os módulos principais**

```python
srv.start()
feeder.start()
```

* Inicia o servidor Modbus e o simulador de peças
* `AutoController` só começa quando o operador aperta **Start** (coil físico)

### 5️⃣ **Loop principal da aplicação**

```python
while True:
    srv.snapshot()
    time.sleep(2)
```

* Executa snapshot do estado do servidor (para debug/log)
* Aguarda 2 segundos entre leituras

### 6️⃣ **Tratamento de interrupção (Ctrl+C)**

```python
except KeyboardInterrupt:
    pass
finally:
    auto.stop()
    srv.stop()
    feeder.stop()
```

* Finaliza o sistema com segurança
* Garante parada ordenada de threads e atuadores

---

## 🔁 Resumo do Fluxo Geral

```
main()
 ├─ Cria servidor Modbus (srv)
 ├─ Cria AutoController (auto)
 ├─ Anexa auto ao servidor
 ├─ Cria RandomFeeder (feeder)
 ├─ Inicia servidor e feeder
 └─ Loop de captura até Ctrl+C
        ↓
   Encerramento limpo (stop de todos)
```

---

## ✅ Observações Importantes

* O sistema **não inicia automaticamente a automação** — depende do botão `Start`
* O `RandomFeeder` apenas simula hardware real, pode ser removido em ambiente de produção
* Todos os elementos rodam em threads próprias (`FactoryModbusEventServer`, `AutoController`, `RandomFeeder`)
