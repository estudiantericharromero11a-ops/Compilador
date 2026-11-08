"""Orquestación de las etapas del compilador Luma."""

from dataclasses import dataclass

from .ast import Program
from .assembly_codegen import XtensaAssemblyCodeGenerator
from .codegen import MicroPythonCodeGenerator
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer


@dataclass(frozen=True)
class CompilationResult:
    program: Program
    generated_code: str
    generated_assembly: str


def compile_source(source: str) -> CompilationResult:
    """Analiza, valida y genera código MicroPython desde una fuente Luma."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    SemanticAnalyzer().analyze(program)
    return CompilationResult(
        program,
        MicroPythonCodeGenerator().generate(program),
        XtensaAssemblyCodeGenerator().generate(program),
    )
