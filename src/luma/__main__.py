"""Interfaz de línea de comandos de Luma."""

import argparse
from pathlib import Path

from .compiler import compile_source
from .errors import LumaError


def main() -> None:
    parser = argparse.ArgumentParser(description="Compilador Luma para ESP32 y Arduino Mega")
    parser.add_argument("--gui", action="store_true", help="Abrir el entorno gráfico")
    parser.add_argument("source", nargs="?", help="Archivo .luma para compilar")
    parser.add_argument(
        "--target",
        choices=("micropython", "arduino", "xtensa"),
        default="micropython",
        help="Formato de salida Arduino Mega para sketch.ino, MicroPython para main.py o módulo Xtensa",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-o", "--output", help="Archivo destino para el código generado")
    output_group.add_argument(
        "--wokwi-dir",
        metavar="DIRECTORIO",
        help="Exportar al archivo principal adecuado del proyecto Wokwi",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Permitir sobrescribir el archivo principal al exportar a Wokwi",
    )
    args = parser.parse_args()

    if args.gui or not args.source:
        from .gui import main as gui_main

        gui_main()
        return
    if args.wokwi_dir and args.target == "xtensa":
        parser.error("--wokwi-dir no admite el módulo --target xtensa")

    source_path = Path(args.source)
    try:
        board = "arduino-mega" if args.target == "arduino" else "esp32"
        result = compile_source(source_path.read_text(encoding="utf-8"), board=board)
    except (OSError, LumaError) as error:
        parser.exit(1, f"Error: {error}\n")

    generated_code = {
        "micropython": result.generated_code,
        "arduino": result.generated_arduino,
        "xtensa": result.generated_assembly,
    }[args.target]
    if args.wokwi_dir:
        from .compiler import write_wokwi_main, write_wokwi_sketch

        try:
            writer = write_wokwi_sketch if args.target == "arduino" else write_wokwi_main
            output_path = writer(generated_code, args.wokwi_dir, overwrite=args.force)
        except (OSError, ValueError) as error:
            parser.exit(1, f"Error al exportar a Wokwi: {error}\n")
        print(f"Código {args.target} exportado a {output_path}")
        return
    if args.output:
        Path(args.output).write_text(generated_code, encoding="utf-8")
    else:
        print(generated_code, end="")


if __name__ == "__main__":
    main()
