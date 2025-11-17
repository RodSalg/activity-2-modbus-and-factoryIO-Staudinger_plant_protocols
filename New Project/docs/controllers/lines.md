# Documentação das Funções — LineController

## Sumário
- Visão Geral
- Funções principais (run_/stop_*)
- Controle da Turntable 1
- Watcher da esteira

Arquivo de referência: `lines.py`

---

## 🧩 Visão Geral

A classe **LineController** é responsável por:

* Ligar e desligar as linhas de esteiras (azul, verde, vazio e produção)
* Controlar **Turntable 1** (mesa giratória principal) com motor + esteira interna
* Oferecer API de controle assíncrono para evitar bloqueio no fluxo do servidor
* Implementar watcher automático para parar a esteira da mesa ao atingir limite físico
* Expor API paralela para **Turntable 2** (mesa secundária)

Essa classe atua como "camada de acionamento físico" do sistema.

---

## 🔍 Atributos principais

| Atributo                                            | Função                                                     |
| --------------------------------------------------- | ---------------------------------------------------------- |
| `_blue_running`, `_green_running`, `_empty_running` | Flags para saber se cada linha está ligada                 |
| `_production_running`                               | Flag global da linha de produção                           |
| `_lock`                                             | Mutex para sincronizar acesso a atuadores                  |
| `_turntable_turn`                                   | Indica se TT1 está girando (True) ou parada (False)        |
| `_turntable_belt`                                   | Direção da esteira da mesa: `forward`, `backward`, `stop`  |
| `_belt_watching`                                    | Indica se há watcher de limite ativo                       |
| `turntable1_busy`                                   | Evita que dois comandos TT1 sejam enviados simultaneamente |

---

## ⚙️ Funções Públicas de Linha

### `run_blue_line()` / `stop_blue_line()`

Liga ou desliga esteiras da linha azul. Sempre executa em thread separada.

* `run_*` só liga se máquina estiver em `running` e ainda não estiver ligada
* `_t_run_*` ativa os atuadores correspondentes
* `_t_stop_*` desativa os atuadores e libera flag

Mesma estrutura se repete para as funções:

* `run_green_line()` / `stop_green_line()`
* `run_empty_line()` / `stop_empty_line()`

---

### `run_production_line()` / `stop_production_line()`

Controla **esteira de produção global**, não relacionada às cores.
Usada no final da sequência da turntable.

---

### `is_production_running(color)`

Retorna estado da linha de produção. Implementada com padrão de API, mesmo que cor não altere lógica.

---

## ♻️ Controle da Turntable 1

### `set_turntable_async(turn_on, belt, stop_limit, belt_timeout_s)`

API principal da TT1. Envia comando assíncrono para giro ou esteira interna.

Fluxo:

1. Verifica se máquina está rodando
2. Garante que TT1 não está ocupada (`turntable1_busy` ou watcher ativo)
3. Se livre, cria thread `_t_set_turntable(...)`

Uso típico:

```python
self.lines.set_turntable_async(True, "forward", "back", 3.0)
```

---

### `_t_set_turntable(...)`

Executa comando real da TT1:

* Liga/desliga motor de giro (`Turntable1_turn`)
* Liga esteira interna (`BELT_FWD` ou `BELT_REV`)
* Se `stop_limit` for definido, inicia watcher
* Se não for definido, apenas aciona e sai

Watcher é iniciado via `_start_belt_watcher(...)`, responsável por desligar belt automaticamente.

---

### `turntable_on()`, `turntable_off()`, `turntable_belt_forward()`, `turntable_belt_backward()`, `turntable_belt_stop()`

Apenas atalhos convenientes para `set_turntable_async`.

---

## 🛰️ Watcher da esteira da mesa

### `_start_belt_watcher(direction, limit_addr, timeout_s, grace_s, min_on_s)`

Cria thread que monitora sensor de limite e desliga a belt automaticamente.
Regras:

* Espera pequeno `grace` antes de começar a ler
* Requer borda estável (2 leituras consecutivas) antes de parar
* Se `timeout_s` expirar, belt é desligada por segurança

### `_stop_belt_watcher()`

Cancela watcher ativo, se existir.

---

## 🧲 Funções Auxiliares

### `_activate(*actuators)` / `_deactivate(*actuators)`

Liga ou desliga múltiplos atuadores com lock de thread.

---

## 🧭 Turntable 2 API

### `set_turntable2_async(...)

Mesma lógica da TT1, mas endereços diferentes.
Usada pelo AutoController para descarte ou pedidos.

### `_t2_set_turntable(...)`

Versão dedicada da TT2:

* Usa `Turntable2_turn` como coil de giro
* Belt controlada normalmente, mas com fallback caso hardware não tenha belt reversa
* Recicla watcher de limite da TT1

---

## 🔄 Resumo de Fluxo do Controle de Mesa

```
AutoController → set_turntable_async → _t_set_turntable
                                            ↓
                               (se stop_limit) start watcher
                                            ↓
                               watcher detecta limite → desliga belt
```

---