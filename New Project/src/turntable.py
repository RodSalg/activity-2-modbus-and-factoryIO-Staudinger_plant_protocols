from pyModbusTCP.server import ModbusServer
import time

HOST = "0.0.0.0"
PORT = 5020

TURN_ADDR = 96        # Inputs.Turntable1_turn
FWD_ADDR  = 98        # Inputs.Turntable1_row_forward
SENSOR_TT3 = 18
ESTEIRA_PEDIDO = 55
SENSOR_TT2 = 3
SENSOR_HALL_1_5 = 5
SENSOR_HALL_1_6 = 6
PICK_PLACE = 45
ESTEIRA_CARREGAMENTO = 50   # conferir!
SENSOR_HALL_1_4 = 49
SENSOR_WAREHOUSE = 14

server = ModbusServer(host=HOST, port=PORT, no_block=True)
server.start()
db = server.data_bank

print("Servidor Modbus ligado, controle da turntable pelos discrete inputs.")

def get_sensor(addr):
    """Lê coil (sensor no Factory I/O)"""
    return db.get_coils(addr, 1)[0]


mesa_ocupada = False
prev_sensor = False
prev_hall_1_5 = False
prev_hall_1_6 = False
prev_hall_1_4 = False  
prev_sensor_warehouse = False 

def ciclo_esteira_principal():

    sensor_tt2_state = get_sensor(SENSOR_TT2)

    if sensor_tt2_state:
        db.set_discrete_inputs(FWD_ADDR, [1])


def ciclo_esteira_cliente(sensor1):


    sensor_state = get_sensor(sensor1)
    print(f"DEBUG: sensor {sensor1} = {sensor_state}")

    if sensor_state:
        db.set_discrete_inputs(ESTEIRA_PEDIDO, [0])
        time.sleep(3.5)
        db.set_discrete_inputs(ESTEIRA_PEDIDO, [1])
        print("ESPERA .....")


def pick():
    print("acionando pick/place...")
    db.set_discrete_inputs(PICK_PLACE, [1])  # ou set_coils se estiver no mapeamento de coils
    time.sleep(2.0)
    db.set_discrete_inputs(PICK_PLACE, [0])


def ciclo_turntable():
    global mesa_ocupada

    mesa_ocupada = True

    print("Girando 90°...")
    db.set_discrete_inputs(TURN_ADDR, [1])
    time.sleep(2.5)        # ajustar até dar 90°


    print("Ligando esteira roll forward...")
    db.set_discrete_inputs(FWD_ADDR, [1])
    db.set_discrete_inputs(ESTEIRA_PEDIDO, [1])
    time.sleep(2.5)        # tempo para a caixa sair
    db.set_discrete_inputs(FWD_ADDR, [0])

    time.sleep(2.5)
    
    db.set_discrete_inputs(TURN_ADDR, [0])  # se tiver sentido inverso; se não tiver, usar outro giro de +90
    db.set_discrete_inputs(ESTEIRA_PEDIDO, [0])

    mesa_ocupada = False
    



try:
    while True:

        ciclo_esteira_principal()

        caixa_no_sensor = get_sensor(SENSOR_TT3)

        if caixa_no_sensor and not prev_sensor and not mesa_ocupada:
            print("📦 Caixa detectada – iniciando sequência da turntable")

            time.sleep(1.5)

            db.set_discrete_inputs(FWD_ADDR, [0])
            ciclo_turntable()

        hall_1_6 = get_sensor(SENSOR_HALL_1_6)
        if hall_1_6 and not prev_hall_1_6:
            print("ESPERA HALL_1_6 .....")
            db.set_discrete_inputs(ESTEIRA_PEDIDO, [0])
            time.sleep(3)
        prev_hall_1_6 = hall_1_6
        db.set_discrete_inputs(ESTEIRA_PEDIDO, [1])


        hall_1_5 = get_sensor(SENSOR_HALL_1_5)
        if hall_1_5 and not prev_hall_1_5:
            print("ESPERA HALL_1_5 .....")
            db.set_discrete_inputs(ESTEIRA_PEDIDO, [0])
            pick()
            #time.sleep(3)
            db.set_discrete_inputs(ESTEIRA_PEDIDO, [1])
        prev_hall_1_5 = hall_1_5

        hall_1_4 = get_sensor(SENSOR_HALL_1_4)
        if hall_1_4 and not prev_hall_1_4:
            print("ENTROU .....")
            db.set_discrete_inputs(ESTEIRA_CARREGAMENTO, [1])
            time.sleep(1)
           
        prev_hall_1_4 = hall_1_4


        
        sensor_warehouse = get_sensor(SENSOR_WAREHOUSE)
        if sensor_warehouse and not prev_sensor_warehouse:
            print("PARANDO .....")
            db.set_discrete_inputs(ESTEIRA_CARREGAMENTO, [0])
            time.sleep(3)
           
        prev_sensor_warehouse = sensor_warehouse


        
            #ciclo_esteira_cliente(SENSOR_HALL_1_6)
            #ciclo_esteira_cliente(SENSOR_HALL_1_5)

        prev_sensor = caixa_no_sensor
        time.sleep(0.05)

        

except KeyboardInterrupt:
    server.stop()
    print("Servidor encerrado.")