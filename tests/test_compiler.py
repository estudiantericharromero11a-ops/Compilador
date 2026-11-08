import unittest

from luma.ast import LedStatement, RepeatStatement, WaitStatement
from luma.compiler import compile_source
from luma.errors import LumaError
from luma.lexer import Lexer
from luma.tokens import TokenKind


SAMPLE = """INICIAR
REPETIR 5
    LED 2 ENCENDER
    ESPERAR 500
    LED 2 APAGAR
    ESPERAR 500
FIN_REPETIR
FINALIZAR
"""

SWITCH_DISPLAY = """INICIAR
BOTONES 13 12 14 27 COMO switches
DISPLAY7 15 2 4 5 18 19 21 ACTIVO_BAJO COMO display
REPETIR_SIEMPRE
    LEER_BINARIO switches COMO numero
    SI numero <= 9
        MOSTRAR numero EN display
    SINO
        LIMPIAR display
    FIN_SI
    ESPERAR 50
FIN_REPETIR_SIEMPRE
FINALIZAR
"""


class LexerTests(unittest.TestCase):
    def test_keywords_numbers_comments_and_lines(self):
        tokens = Lexer("iniciar # comienzo\nLED 2 ENCENDER\r\n").tokenize()
        self.assertEqual(
            [token.kind for token in tokens],
            [
                TokenKind.START,
                TokenKind.EOL,
                TokenKind.LED,
                TokenKind.NUMBER,
                TokenKind.ON,
                TokenKind.EOL,
                TokenKind.EOF,
            ],
        )

    def test_rejects_non_ascii_or_invalid_character(self):
        with self.assertRaisesRegex(LumaError, "Carácter no permitido"):
            Lexer("INICIAR\nLED 2 @").tokenize()


class ParserTests(unittest.TestCase):
    def test_builds_nested_program_ast(self):
        result = compile_source(SAMPLE)
        repeat = result.program.body[0]
        self.assertIsInstance(repeat, RepeatStatement)
        self.assertEqual(repeat.count, 5)
        self.assertIsInstance(repeat.body[0], LedStatement)
        self.assertIsInstance(repeat.body[1], WaitStatement)

    def test_reports_missing_repeat_end(self):
        source = "INICIAR\nREPETIR 2\nLED 2 ENCENDER\nFINALIZAR"
        with self.assertRaisesRegex(LumaError, "Falta FIN_REPETIR"):
            compile_source(source)

    def test_requires_one_instruction_per_line(self):
        with self.assertRaisesRegex(LumaError, "final de línea"):
            compile_source("INICIAR\nLED 2 ENCENDER ESPERAR 1\nFINALIZAR")

    def test_reports_integer_too_large_as_compiler_error(self):
        source = f"INICIAR\nESPERAR {'9' * 5000}\nFINALIZAR"
        with self.assertRaisesRegex(LumaError, "demasiado grande"):
            compile_source(source)


class SemanticTests(unittest.TestCase):
    def test_rejects_input_only_gpio(self):
        with self.assertRaisesRegex(LumaError, "no disponible como salida"):
            compile_source("INICIAR\nLED 34 ENCENDER\nFINALIZAR")

    def test_rejects_flash_gpio(self):
        with self.assertRaisesRegex(LumaError, "no disponible como salida"):
            compile_source("INICIAR\nLED 6 ENCENDER\nFINALIZAR")

    def test_rejects_unreasonable_repeat_count(self):
        with self.assertRaisesRegex(LumaError, "entre 1 y 10000"):
            compile_source("INICIAR\nREPETIR 0\nFIN_REPETIR\nFINALIZAR")


class CodeGenerationTests(unittest.TestCase):
    def test_generates_micro_python_with_pin_setup_and_loop(self):
        code = compile_source(SAMPLE).generated_code
        compile(code, "<generated MicroPython>", "exec")
        self.assertIn("from machine import Pin", code)
        self.assertIn("luma_pin_2 = Pin(2, Pin.OUT)", code)
        self.assertIn("for _ in range(5):", code)
        self.assertIn("luma_pin_2.value(1)", code)
        self.assertIn("luma_pin_2.value(0)", code)
        self.assertIn("sleep_ms(500)", code)

    def test_nested_blocks_are_indented(self):
        source = "INICIAR\nREPETIR 2\nREPETIR 3\nESPERAR 1\nFIN_REPETIR\nFIN_REPETIR\nFINALIZAR"
        code = compile_source(source).generated_code
        self.assertIn("        sleep_ms(1)", code)

    def test_generates_xtensa_assembly_with_hardware_runtime_calls(self):
        assembly = compile_source(SAMPLE).generated_assembly
        self.assertIn(".extern luma_led_write", assembly)
        self.assertIn(".extern luma_wait_ms", assembly)
        self.assertIn("luma_program:", assembly)
        self.assertIn("call0 luma_led_write", assembly)
        self.assertIn("call0 luma_wait_ms", assembly)
        self.assertIn(".Lrepeat_start_0:", assembly)
        self.assertIn("beqz a4, .Lrepeat_end_0", assembly)
        self.assertIn("j .Lrepeat_start_0", assembly)

    def test_xtensa_assembly_handles_nested_loops_and_large_constants(self):
        source = "INICIAR\nREPETIR 2\nREPETIR 3\nESPERAR 5000\nFIN_REPETIR\nFIN_REPETIR\nFINALIZAR"
        assembly = compile_source(source).generated_assembly
        self.assertIn("s32i a4, a1, 0", assembly)
        self.assertIn("s32i a4, a1, 4", assembly)
        self.assertIn("slli a2, a2, 8", assembly)

    def test_xtensa_assembly_allocates_deep_loop_stack_frame(self):
        source = "INICIAR\n" + "REPETIR 2\n" * 32 + "ESPERAR 1\n" + "FIN_REPETIR\n" * 32 + "FINALIZAR"
        assembly = compile_source(source).generated_assembly
        self.assertIn("movi a8, 144", assembly)
        self.assertIn("sub a1, a1, a8", assembly)

    def test_compiles_button_and_seven_segment_program(self):
        result = compile_source(SWITCH_DISPLAY)
        compile(result.generated_code, "<generated MicroPython>", "exec")
        self.assertIn("Pin(13, Pin.IN, Pin.PULL_DOWN)", result.generated_code)
        self.assertIn("Pin(15, Pin.OUT)", result.generated_code)
        self.assertIn("luma_value_numero = (luma_buttons_switches[0].value() << 3)", result.generated_code)
        self.assertIn("if luma_value_numero <= 9:", result.generated_code)
        self.assertIn("luma_show_digit(luma_display_display, luma_value_numero)", result.generated_code)
        self.assertIn("while True:", result.generated_code)

    def test_xtensa_backend_emits_button_and_display_runtime_calls(self):
        assembly = compile_source(SWITCH_DISPLAY).generated_assembly
        self.assertIn(".extern luma_read_buttons", assembly)
        self.assertIn(".extern luma_display_show", assembly)
        self.assertIn("call0 luma_read_buttons", assembly)
        self.assertIn("call0 luma_display_show", assembly)
        self.assertIn(".Lbuttons_switches:", assembly)
        self.assertIn(".Ldisplay_display:", assembly)

    def test_semantic_analysis_rejects_undeclared_display(self):
        source = "INICIAR\nMOSTRAR numero EN display\nFINALIZAR"
        with self.assertRaisesRegex(LumaError, "no está declarado"):
            compile_source(source)

    def test_semantic_analysis_rejects_pin_conflicts(self):
        source = (
            "INICIAR\n"
            "BOTONES 13 12 14 27 COMO switches\n"
            "DISPLAY7 15 2 4 5 18 19 13 ACTIVO_BAJO COMO display\n"
            "FINALIZAR"
        )
        with self.assertRaisesRegex(LumaError, "ya está ocupado"):
            compile_source(source)


if __name__ == "__main__":
    unittest.main()
