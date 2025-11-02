# Documentação — utils.py (funções e classe utilitária)

Este documento descreve o conteúdo e o propósito do arquivo `utils.py`, que contém utilitários simples usados por vários módulos do sistema.

Arquivo de referência: `utils.py`

---

## 🧩 Visão Geral

O arquivo `utils.py` fornece duas funcionalidades essenciais, reutilizadas em múltiplas partes do projeto:

1. **Função `now()`** – Utilitário simples para gerar timestamp padronizado
2. **Classe `Stoppable`** – Classe base para threads ou loops que podem ser parados de forma segura

Esses recursos são usados especialmente no `FactoryModbusEventServer`, `RandomFeeder`, threads de turntable, entre outros.

---

## 📌 Função `now()`

```python
def now():
    return datetime.now().isoformat(timespec="seconds")
```

### ✅ O que faz:

* Retorna um timestamp no formato ISO 8601, ex: `2025-11-02T14:38:32`
* `timespec="seconds"` remove milissegundos, tornando a saída mais limpa para logs

### 📍 Uso típico:

```python
print(f"[{now()}] Servidor iniciado...")
```

Serve para padronizar logs sem necessidade de `datetime.utcnow()` ou `strftime()` repetidos.

---

## 📌 Classe `Stoppable`

```python
class Stoppable:
    def __init__(self):
        self._stop_evt = threading.Event()
```

### ✅ Propósito

Classe base para componentes que rodam loops contínuos (worker threads, servidores, feeders...) e precisam oferecer uma forma segura de parada.

### 🔍 Atributos e métodos:

| Método / Property | O que faz                                                   |
| ----------------- | ----------------------------------------------------------- |
| `stop_event`      | Retorna o objeto `threading.Event` interno                  |
| `stopped()`       | Retorna `True` se o evento de parada foi ativado            |
| `stop()`          | Aciona o evento, sinalizando para o loop principal encerrar |

### 📍 Padrão de uso:

```python
class Worker(Stoppable):
    def run(self):
        while not self.stopped():
            ... # processamento
```

Esse padrão evita `while True:` sem condição de saída, ajudando no desligamento seguro.

---

## 🔁 Onde é utilizado?

| Módulo             | Uso                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------ |
| `server.py`        | `FactoryModbusEventServer` herda `Stoppable` para encerrar thread do loop de eventos |
| `random_feeder.py` | Worker usa `stoppable` para sair do loop de emissão                                  |
| `auto.py`          | Utilizado para loops internos da automação                                           |

---

## ✅ Benefícios do padrão `Stoppable`

✔ Evita `KeyboardInterrupt` descontrolado dentro de threads
✔ Não requer `daemon=True` (mas pode complementar)
✔ Facilita shutdown limpo: `stop(); join()`
✔ Permite múltiplas threads compartilharem o mesmo sinal de parada

---