from pyModbusTCP.server import ModbusServer
import time

HOST = "0.0.0.0"
PORT = 5020

# --------------------
# ENDEREÇOS
# --------------------
TURN_ADDR = 96
FWD_ADDR = 98
SENSOR_TT3 = 18
ESTEIRA_PEDIDO = 55
SENSOR_TT2 = 3
SENSOR_HALL_1_5 = 5
SENSOR_HALL_1_6 = 6
PICK_PLACE = 45
ESTEIRA_CARREGAMENTO = 50
SENSOR_HALL_1_4 = 49
SENSOR_WAREHOUSE = 14

# --------------------
# SERVIDOR MODBUS
# --------------------
server = ModbusServer(host=HOST, port=PORT, no_block=True)
server.start()
db = server.data_bank
print("Servidor Modbus ligado, controle da turntable pelos discrete inputs.")

# -----------------------
# VARIÁVEIS DE ESTADO (inicial)
# -----------------------
mesa_ocupada = False
prev_sensor = False
prev_hall_1_5 = False
prev_hall_1_6 = False
prev_hall_1_4 = False
prev_sensor_warehouse = False


# -----------------------------------
# FUNÇÕES AUXILIARES DE I/O
# -----------------------------------
def get_sensor(addr):
    """Lê coil (sensor no Factory I/O)"""
    return db.get_coils(addr, 1)[0]


def set_input(addr, value):
    """Define discrete input (compatível com seu uso atual)."""
    db.set_discrete_inputs(addr, [value])


# -----------------------------------
# CICLOS INDIVIDUAIS
# -----------------------------------
def ciclo_esteira_principal():
    if get_sensor(SENSOR_TT2):
        set_input(FWD_ADDR, 1)


def ciclo_esteira_cliente(sensor_addr):
    sensor_state = get_sensor(sensor_addr)
    print(f"DEBUG: sensor {sensor_addr} = {sensor_state}")

    if sensor_state:
        set_input(ESTEIRA_PEDIDO, 0)
        time.sleep(3.5)
        set_input(ESTEIRA_PEDIDO, 1)
        print("ESPERA .....")


def pick():
    print("acionando pick/place...")
    set_input(PICK_PLACE, 1)
    time.sleep(2.0)
    set_input(PICK_PLACE, 0)


def ciclo_turntable():
    # modifica a variável global que sinaliza mesa ocupada
    global mesa_ocupada
    mesa_ocupada = True

    print("Girando 90°...")
    set_input(TURN_ADDR, 1)
    time.sleep(2.5)  # ajustar até dar 90°

    print("Ligando esteira roll forward...")
    set_input(FWD_ADDR, 1)
    set_input(ESTEIRA_PEDIDO, 1)
    time.sleep(2.5)  # tempo para a caixa sair
    set_input(FWD_ADDR, 0)

    time.sleep(2.5)

    set_input(TURN_ADDR, 0)
    set_input(ESTEIRA_PEDIDO, 0)

    mesa_ocupada = False


# -----------------------------------
# HANDLERS (sensores com detecção de borda)
# -----------------------------------
def handle_tt3(prev):
    """Retorna novo estado de prev_sensor (True/False)."""
    caixa = get_sensor(SENSOR_TT3)
    if caixa and not prev and not mesa_ocupada:
        print("📦 Caixa detectada – iniciando sequência da turntable")
        time.sleep(1.5)
        set_input(FWD_ADDR, 0)
        ciclo_turntable()
    return caixa


def handle_hall_1_6(prev):
    estado = get_sensor(SENSOR_HALL_1_6)
    if estado and not prev:
        print("ESPERA HALL_1_6 .....")
        set_input(ESTEIRA_PEDIDO, 0)
        time.sleep(3)
    # conforme seu script original: garante que a esteira de pedido fique ligada depois
    set_input(ESTEIRA_PEDIDO, 1)
    return estado


def handle_hall_1_5(prev):
    estado = get_sensor(SENSOR_HALL_1_5)
    if estado and not prev:
        print("ESPERA HALL_1_5 .....")
        set_input(ESTEIRA_PEDIDO, 0)
        pick()
        set_input(ESTEIRA_PEDIDO, 1)
    return estado


def handle_hall_1_4(prev):
    estado = get_sensor(SENSOR_HALL_1_4)
    if estado and not prev:
        print("ENTROU .....")
        set_input(ESTEIRA_CARREGAMENTO, 1)
        time.sleep(1)
    return estado


def handle_warehouse(prev):
    estado = get_sensor(SENSOR_WAREHOUSE)
    if estado and not prev:
        print("PARANDO .....")
        set_input(ESTEIRA_CARREGAMENTO, 0)
        time.sleep(3)
    return estado


# -----------------------------------
# LOOP PRINCIPAL
# -----------------------------------
try:
    # usa as variáveis de estado definidas acima (como locais do escopo do módulo)
    prev_sensor = prev_sensor
    prev_hall_1_6 = prev_hall_1_6
    prev_hall_1_5 = prev_hall_1_5
    prev_hall_1_4 = prev_hall_1_4
    prev_sensor_warehouse = prev_sensor_warehouse

    while True:
        ciclo_esteira_principal()

        # Sensores com detecção de borda: chamamos os handlers e atualizamos os prevs
        prev_sensor = handle_tt3(prev_sensor)
        prev_hall_1_6 = handle_hall_1_6(prev_hall_1_6)
        prev_hall_1_5 = handle_hall_1_5(prev_hall_1_5)
        prev_hall_1_4 = handle_hall_1_4(prev_hall_1_4)
        prev_sensor_warehouse = handle_warehouse(prev_sensor_warehouse)

        time.sleep(0.05)

except KeyboardInterrupt:
    server.stop()
    print("Servidor encerrado.")
