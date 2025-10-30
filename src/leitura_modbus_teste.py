from pyModbusTCP.client import ModbusClient
import time


class ModbusClientApp:
    def __init__(self, host, port):
        self.client = ModbusClient(host=host, port=port, auto_open=True, auto_close=True)

    def read_registers(self, start, count):
        """
        Lê 'count' registradores a partir de 'start'.
        """
        regs = self.client.read_holding_registers(start, count)
        if regs:
            print(f"Leitura [{start}..{start+count-1}]: {regs}")
        else:
            print("Falha na leitura dos registradores.")

    def set_register(self, address, value):
        """
        Altera o valor de um registrador no servidor Modbus.
        """
        if self.client.write_single_register(address, value):
            print(f"Registrador {address} alterado para {value}.")
        else:
            print(f"Falha ao alterar o registrador {address}.")

    def close_connection(self):
        """
        Fecha a conexão com o servidor Modbus.
        """
        self.client.close()
        print("Conexão com o servidor fechada.")


def main():
    server_ip = "127.0.0.1" 
    server_port = 5020       

    client = ModbusClientApp(host=server_ip, port=server_port)

    try:
        while True:
            client.read_registers(0, 12)
            time.sleep(2)  
    except KeyboardInterrupt:
        print("Cliente encerrado.")
        client.close_connection()


if __name__ == "__main__":
    main()
