import time
from server import FactoryModbusEventServer

def main():
    srv = FactoryModbusEventServer(host="0.0.0.0", port=5020, scan_time=0.05, verbose=True)
    srv.start()
    try:
        while True:
            srv.snapshot()
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()

if __name__ == "__main__":
    main()
