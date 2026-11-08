"""Interfaz de línea de comandos de Luma."""

import argparse
from pathlib import Path

from .compiler import compile_source
from .errors import LumaError


def main() -> None:
    parser = argparse.ArgumentParser(description="Compilador Luma para ESP32")
    parser.add_argument("--gui", action="store_true", help="Abrir el entorno gráfico")
    parser.add_argument("source", nargs="?", help="Archivo .luma para compilar")
    parser.add_argument(
        "--target",
        choices=("micropython", "xtensa"),
        default="micropython",
        help="Formato de salida (xtensa genera un módulo que necesita un runtime de hardware)",
    )
    parser.add_argument("-o", "--output", help="Archivo destino para el código generado")
    args = parser.parse_args()

    if args.gui or not args.source:
        from .gui import main as gui_main

        gui_main()
        return

    source_path = Path(args.source)
    try:
        result = compile_source(source_path.read_text(encoding="utf-8"))
    except (OSError, LumaError) as error:
        parser.exit(1, f"Error: {error}\n")

    generated_code = result.generated_code if args.target == "micropython" else result.generated_assembly
    if args.output:
        Path(args.output).write_text(generated_code, encoding="utf-8")
    else:
        print(generated_code, end="")


if __name__ == "__main__":
    main()
