import time
import subprocess
from pathlib import Path
from simulators import RandomFeeder
from server import FactoryModbusEventServer
from controllers import AutoController


def main():
    def print_banner():
        banner = r"""
 __  __           _ ____              _____ ____ ____   _____ ____
|  \/  | ___   __| | __ ) _   _ ___  |_   _/ ___|  _ \ / /_ _|  _ \
| |\/| |/ _ \ / _` |  _ \| | | / __|   | || |   | |_) / / | || |_) |
| |  | | (_) | (_| | |_) | |_| \__ \   | || |___|  __/ /  | ||  __/
|_|  |_|\___/ \__,_|____/ \__,_|___/   |_| \____|_| /_/  |___|_|

    Staudinger Plant - Simulator
"""
        print(banner)

        # imprime informações básicas e instrução
        print("Pressione CTRL+C para encerrar")

        # tenta descobrir o diretório do repositório (procura .git até 5 níveis acima)
        try:
            p = Path(__file__).resolve()
            repo_dir = None
            for parent in [p] + list(p.parents)[:5]:
                if (Path(parent) / ".git").exists():
                    repo_dir = Path(parent)
                    break
            if repo_dir is None:
                # fallback: subir dois níveis (New Project/ src -> repo)
                repo_dir = p.parents[1]

            # executa git shortlog para obter lista de contribuidores
            try:
                res = subprocess.run(
                    ["git", "shortlog", "-sne", "HEAD"],
                    cwd=str(repo_dir),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    print("\nContribuidores (top):")
                    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
                    # mostra até 6 contribuidores
                    for ln in lines[:6]:
                        print("  " + ln)
                else:
                    # sem git ou sem histórico
                    pass
            except Exception:
                pass
        except Exception:
            # não bloquear a inicialização caso algo falhe
            pass

    # imprime o banner de início
    print_banner()

    srv = FactoryModbusEventServer(
        host="0.0.0.0", port=5020, scan_time=0.05, verbose=True
    )

    auto = AutoController(srv, verbose=False)
    srv.auto = auto

    feeder = RandomFeeder(srv, period_s=(10, 30), pulse_ms=360)

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
