"""Entry point for the standalone FilmPen app (FilmPen.exe).

Double-click → starts the server and opens the gallery in the browser.
Any command-line arguments are passed straight to `python -m filmpen`.
"""
import socket
import sys
import webbrowser

from filmpen.__main__ import main

PORT = 8080


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        if port_in_use(PORT):
            # FilmPen is probably already running: just show it.
            print(f"FilmPen já está a correr. A abrir http://127.0.0.1:{PORT}")
            webbrowser.open(f"http://127.0.0.1:{PORT}")
            sys.exit(0)
        print("FilmPen")
        print("  1. Na câmara: ativa a ligação ao smartphone (menu de Reprodução)")
        print("  2. Liga este computador ao Wi-Fi da câmara (E-PL9-...)")
        print("  Para parar: fecha esta janela.\n")
        args = ["run", "--open", "--port", str(PORT)]
    try:
        sys.exit(main(args))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:  # keep the window open so the error can be read
        print(f"\nErro: {e}")
        input("Carrega Enter para fechar...")
        sys.exit(1)
