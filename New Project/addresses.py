from enum import IntEnum


class Coils:
    Emergency = 9

    Start = 24
    Stop = 26
    RestartButton = 25

    resetButton = 27

    Sensor_1_Caixote_Verde = 77
    Sensor_2_Caixote_Verde = 78

    Sensor_1_Caixote_Azul = 80
    Sensor_2_Caixote_Azul = 81

    Sensor_1_Caixote_Vazio = 83
    Sensor_2_Caixote_Vazio = 84

    Turntable1_FrontLimit = 95
    Turntable1_BackLimit = 94

    Sensor_Final_Producao = 86

    Vision_Blue           = 88
    Vision_Green          = 89
    Sensor_Hall           = 90

    Sensor_Write = 10
    Emitter_Blue_Button = 26


class Inputs:
    Running = 0
    Stop = 1
    Emergency = 2

    EntryConveyor = 10

    Esteira_Producao_1 = 30
    Esteira_Freio_Sensor = 31
    Esteira_Producao_2 = 32

    Emmiter_Caixote_Verde = 23
    Emmiter_Product_Verde = 24
    Caixote_Verde_Esteira_1 = 78
    Caixote_Verde_Esteira_2 = 79
    Caixote_Verde_Esteira_3 = 80
    Caixote_Verde_Esteira_4 = 81

    Emmiter_Caixote_Azul = 20
    Emmiter_Product_Azul = 21
    Caixote_Azul_Esteira_1 = 82
    Caixote_Azul_Esteira_2 = 83

    Emmiter_Caixote_Vazio = 22
    Caixote_Vazio_Esteira_1 = 84
    Caixote_Vazio_Esteira_2 = 85
    Caixote_Vazio_Esteira_3 = 86
    Caixote_Vazio_Esteira_4 = 87

    Turntable1_turn = 93
    Turntable1_Esteira_EntradaSaida = 94
    Turntable1_Esteira_SaidaEntrada = 95

    Emitter_Blue_Light = 27
    Vision_Sensor_0 = 97


class Esteiras(IntEnum):
    Esteira_Producao_1 = 30
    Esteira_Freio_Sensor = 31
    Esteira_Producao_2 = 32

    Emmiter_Caixote_Azul = 20
    Emmiter_Product_Azul = 21
    Caixote_Azul_Esteira_1 = 82
    Caixote_Azul_Esteira_2 = 83

    Emmiter_Caixote_Vazio   = 22
    Caixote_Vazio_Esteira_1 = 84
    Caixote_Vazio_Esteira_2 = 85
    Caixote_Vazio_Esteira_3 = 86
    Caixote_Vazio_Esteira_4 = 87

    Emmiter_Caixote_Verde = 23
    Emmiter_Product_Verde = 24
    Caixote_Verde_Esteira_1 = 78
    Caixote_Verde_Esteira_2 = 79
    Caixote_Verde_Esteira_3 = 80
    Caixote_Verde_Esteira_4 = 81

    Turntable1_Esteira_EntradaSaida = 94
    Turntable1_Esteira_SaidaEntrada = 95
