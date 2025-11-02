# Documentação — Mapa de Endereços (Coils, Inputs, Esteiras)

Arquivo de referência: `addresses.py`

---

## 🧩 Visão Geral

O módulo `addresses.py` define **constantes de endereçamento utilizadas para leitura e escrita de sinais digitais**, normalmente via Modbus ou driver equivalente.

Esses endereços representam:

* Sensores físicos (fotocélulas, fim de curso, vision, HAL)
* Botões e comandos de operação (Start, Stop, Emergency)
* Atuadores (esteiras, motores da turntable)
* Emissores virtuais para simulação (RandomFeeder)

Os endereços estão agrupados em três classes:

| Classe     | Função                                                                 |
| ---------- | ---------------------------------------------------------------------- |
| `Coils`    | Sinais **de escrita ou leitura rápida**, base lógica (inteiros soltos) |
| `Inputs`   | Sinais que representam entradas digitais do CLP (DI)                   |
| `Esteiras` | Enumeração com os endereços associados às esteiras do sistema          |

---

## 🔌 Classe `Coils`

Representa os **endereços de sinais observados no lado do servidor** para detecção de eventos.

### 🔴 Botões principais

| Endereço | Nome            | Função                                    |
| -------- | --------------- | ----------------------------------------- |
| `9`      | `Emergency`     | Botão físico de emergência (parada total) |
| `24`     | `Start`         | Inicia sistema automático                 |
| `26`     | `Stop`          | Para operação (sem emergência)            |
| `25`     | `RestartButton` | Reinicializa lógica após ciclo            |
| `28`     | `Create_OP`     | Botão para criação de pedido              |

### 📦 Sensores das linhas (Emitter e chegada)

| Cor   | Sensor 1 (emissor) | Sensor 2 (chegada) |
| ----- | ------------------ | ------------------ |
| Azul  | `80`               | `81`               |
| Verde | `77`               | `78`               |
| Vazio | `83`               | `84`               |

### 🎯 Sensores auxiliares

| Endereço | Nome                    | Função                                        |
| -------- | ----------------------- | --------------------------------------------- |
| `95`     | `Turntable1_FrontLimit` | Fim de curso frontal TT1                      |
| `94`     | `Turntable1_BackLimit`  | Fim de curso traseiro TT1                     |
| `86`     | `Sensor_Final_Producao` | Detecta saída da peça no final da linha       |
| `96`     | `Load_Sensor`           | Detecta peça parada na TT2                    |
| `97`     | `Discharg_Sensor`       | Detecta descarregamento                       |
| `88`     | `Vision_Blue`           | Resultado da visão computadorizada (azul)     |
| `89`     | `Vision_Green`          | Resultado da visão computadorizada (verde)    |
| `90`     | `Sensor_Hall`           | Sensor HAL — usado para acionar classificação |

---

## 🔍 Classe `Inputs`

Endereços que representam **entradas acionáveis** ou atuadores (ex: esteiras, motores, sensores do CLP).

### ⚙️ Estados gerais do sistema

| Endereço | Nome        |
| -------- | ----------- |
| `0`      | `Running`   |
| `1`      | `Stop`      |
| `2`      | `Emergency` |

### 🚚 Esteiras globais

| Endereço | Nome                 |
| -------- | -------------------- |
| `14`     | `Esteira_Estoque`    |
| `15`     | `Esteira_Central`    |
| `30`     | `Esteira_Producao_1` |
| `32`     | `Esteira_Producao_2` |

### 🔄 Turntable 1 (mesa rotativa principal)

| Endereço | Função                            |
| -------- | --------------------------------- |
| `93`     | Motor de giro (`Turntable1_turn`) |
| `94`     | Belt — Entrada→Saída (`forward`)  |
| `95`     | Belt — Saída→Entrada (`reverse`)  |

### 🔄 Turntable 2 (mesa secundária)

| Endereço | Nome              |
| -------- | ----------------- |
| `38`     | `Turntable2_turn` |
| `39`     | `Load_turn`       |
| `40`     | `Discharg_turn`   |

### 📦 Emissores simulados (RandomFeeder)

| Peça  | Caixote | Produto             |
| ----- | ------- | ------------------- |
| Azul  | `20`    | `21`                |
| Verde | `23`    | `24`                |
| Vazio | `22`    | *(não tem produto)* |

---

## 🏭 Classe `Esteiras (IntEnum)`

Enum opcional que referencia as mesmas entradas que `Inputs`, mas serve para permitir iteração ou uso direto em loops.

Exemplo:

```python
for e in Esteiras:
    server.set_actuator(e, True)
```