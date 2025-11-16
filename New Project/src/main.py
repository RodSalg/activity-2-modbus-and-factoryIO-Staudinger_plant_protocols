import time
from simulators import RandomFeeder
from server import FactoryModbusEventServer
from controllers import AutoController

def main():
    srv = FactoryModbusEventServer(
        host="0.0.0.0", port=5020, scan_time=0.05, verbose=True
    )

    auto = AutoController(srv, verbose=True)
    srv.auto = auto

    feeder = RandomFeeder(srv, period_s=(10, 20), pulse_ms=360)

    srv.start()
    feeder.start()
    try:
        while True:
            srv.snapshot()
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        auto.stop()
        srv.stop()
        feeder.stop()


if __name__ == "__main__":
    main()
