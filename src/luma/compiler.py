"""Orquestación de las etapas del compilador Luma."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .ast import Program
from .arduino_codegen import ArduinoCodeGenerator
from .assembly_codegen import XtensaAssemblyCodeGenerator
from .codegen import MicroPythonCodeGenerator
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer


@dataclass(frozen=True)
class CompilationResult:
    program: Program
    generated_code: str
    generated_arduino: str
    generated_assembly: str


def compile_source(
    source: str, *, board: Literal["esp32", "arduino-mega"] = "esp32"
) -> CompilationResult:
    """Analiza una fuente Luma y genera sus salidas para la placa indicada."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    SemanticAnalyzer(board).analyze(program)
    return CompilationResult(
        program,
        MicroPythonCodeGenerator().generate(program),
        ArduinoCodeGenerator().generate(program),
        XtensaAssemblyCodeGenerator().generate(program),
    )


def write_wokwi_main(
    generated_code: str, project_dir: str | Path, *, overwrite: bool = False
) -> Path:
    """Escribe código MicroPython generado en el main.py de un proyecto Wokwi."""
    directory = Path(project_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe el directorio del proyecto Wokwi: {directory}")
    if not (directory / "diagram.json").is_file():
        raise ValueError(f"No se encontró diagram.json en el proyecto Wokwi: {directory}")

    output_path = directory / "main.py"
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Ya existe {output_path}; confirma la sobrescritura para reemplazarlo")
    output_path.write_text(generated_code, encoding="utf-8")
    return output_path


def write_wokwi_sketch(
    generated_code: str, project_dir: str | Path, *, overwrite: bool = False
) -> Path:
    """Escribe el sketch Arduino en un proyecto Wokwi local."""
    directory = Path(project_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe el directorio del proyecto Wokwi: {directory}")
    if not (directory / "diagram.json").is_file():
        raise ValueError(f"No se encontró diagram.json en el proyecto Wokwi: {directory}")

    output_path = directory / "sketch.ino"
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Ya existe {output_path}; confirma la sobrescritura para reemplazarlo")
    output_path.write_text(generated_code, encoding="utf-8")
    return output_path
