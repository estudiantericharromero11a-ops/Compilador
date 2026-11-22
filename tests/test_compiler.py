import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from luma.ast import LedStatement, RepeatStatement, WaitStatement
from luma.compiler import compile_source, write_wokwi_main, write_wokwi_sketch
from luma.errors import LumaError
from luma.lexer import Lexer
from luma.tokens import TokenKind
from luma.wokwi_browser import WokwiBrowserError, _select_wokwi_window, _wokwi_coordinates


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

    def test_scans_lcd_strings_with_comments_and_escaped_quotes(self):
        tokens = Lexer('ESCRIBIR_LCD pantalla "A # \\"B\\"" # comment').tokenize()
        string = next(token for token in tokens if token.kind is TokenKind.STRING)
        self.assertEqual(string.lexeme, 'A # "B"')

    def test_rejects_non_ascii_lcd_text(self):
        with self.assertRaisesRegex(LumaError, "ASCII imprimibles"):
            Lexer('ESCRIBIR_LCD pantalla "Bebida ñ"').tokenize()


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
    def test_rejects_input_only_gpio_on_esp32(self):
        with self.assertRaisesRegex(LumaError, "no disponible como salida"):
            compile_source("INICIAR\nLED 34 ENCENDER\nFINALIZAR")

    def test_rejects_flash_gpio(self):
        with self.assertRaisesRegex(LumaError, "no disponible como salida"):
            compile_source("INICIAR\nLED 6 ENCENDER\nFINALIZAR")

    def test_rejects_unreasonable_repeat_count(self):
        with self.assertRaisesRegex(LumaError, "entre 1 y 10000"):
            compile_source("INICIAR\nREPETIR 0\nFIN_REPETIR\nFINALIZAR")

    def test_rejects_servo_angle_outside_supported_range(self):
        source = "INICIAR\nSERVOMOTOR 18 COMO puerta\nMOVER puerta ANGULO 181\nFINALIZAR"
        with self.assertRaisesRegex(LumaError, "entre 0 y 180 grados"):
            compile_source(source)

    def test_rejects_servo_pin_conflicts(self):
        source = (
            "INICIAR\n"
            "SERVOMOTOR 18 COMO puerta\n"
            "LED 18 ENCENDER\n"
            "FINALIZAR"
        )
        with self.assertRaisesRegex(LumaError, "ya está ocupado"):
            compile_source(source)

    def test_validates_arduino_mega_pin_range(self):
        source = (
            "INICIAR\n"
            "SERVOMOTOR 9 COMO puerta\n"
            "BOTONES 2 3 12 13 ACTIVO_BAJO COMO controles\n"
            "LED 6 ENCENDER\n"
            "LED 7 APAGAR\n"
            "FINALIZAR"
        )
        result = compile_source(source, board="arduino-mega")
        self.assertIn("pinMode(6, OUTPUT);", result.generated_arduino)
        with self.assertRaisesRegex(LumaError, "Arduino Mega"):
            compile_source("INICIAR\nLED 70 ENCENDER\nFINALIZAR", board="arduino-mega")

    def test_rejects_conflicting_button_and_lcd_pins(self):
        source = (
            "INICIAR\n"
            "LCD16X2 12 11 5 4 3 2 COMO pantalla\n"
            "BOTON 12 ACTIVO_BAJO COMO tecla\n"
            "FINALIZAR\n"
        )
        with self.assertRaisesRegex(LumaError, "ya está ocupado"):
            compile_source(source, board="arduino-mega")

    def test_validates_lcd_cursor_position(self):
        source = (
            "INICIAR\n"
            "LCD16X2 12 11 5 4 3 2 COMO pantalla\n"
            "CURSOR_LCD pantalla 0 2\n"
            "FINALIZAR\n"
        )
        with self.assertRaisesRegex(LumaError, "fila.*0 o 1"):
            compile_source(source, board="arduino-mega")


class CodeGenerationTests(unittest.TestCase):
    def test_compiles_led_presentation_example(self):
        source = Path("examples/presentacion_leds.luma").read_text(encoding="utf-8")
        code = compile_source(source).generated_code
        compile(code, "<generated MicroPython>", "exec")
        self.assertIn("while True:", code)
        self.assertIn("Pin(32, Pin.IN, Pin.PULL_DOWN)", code)
        self.assertIn("if luma_value_habilitado == 8:", code)
        for pin in (13, 14, 18, 19, 21, 22, 23):
            self.assertIn(f"luma_pin_{pin} = Pin({pin}, Pin.OUT)", code)

    def test_compiles_servo_door_example_for_both_backends(self):
        source = Path("examples/servo_door.luma").read_text(encoding="utf-8")
        result = compile_source(source, board="arduino-mega")
        compile(result.generated_code, "<generated MicroPython>", "exec")
        self.assertIn("Pin(2, Pin.IN, Pin.PULL_UP)", result.generated_code)
        self.assertIn("(1 - luma_buttons_controles[0].value())", result.generated_code)
        self.assertIn("luma_servo_set_angle(luma_servo_puerta, 0)", result.generated_code)
        self.assertIn("luma_servo_set_angle(luma_servo_puerta, 90)", result.generated_code)
        self.assertIn("#include <Servo.h>", result.generated_arduino)
        self.assertIn("Servo luma_servo_puerta;", result.generated_arduino)
        self.assertIn("pinMode(2, INPUT_PULLUP);", result.generated_arduino)
        self.assertIn("(digitalRead(2) == LOW)", result.generated_arduino)
        self.assertIn("luma_servo_puerta.attach(9);", result.generated_arduino)
        self.assertIn("luma_servo_puerta.write(0);", result.generated_arduino)
        self.assertIn("luma_servo_puerta.write(90);", result.generated_arduino)
        self.assertIn("if (luma_value_estado >= 8)", result.generated_arduino)
        self.assertIn("digitalWrite(6, HIGH);", result.generated_arduino)
        self.assertIn("digitalWrite(7, LOW);", result.generated_arduino)
        self.assertIn(".extern luma_servo_set_angle", result.generated_assembly)
        self.assertIn("call0 luma_servo_setup", result.generated_assembly)
        self.assertIn("call0 luma_servo_set_angle", result.generated_assembly)

    def test_compiles_vending_machine_for_all_backends(self):
        source = Path("examples/maquina_bebidas.luma").read_text(encoding="utf-8")
        result = compile_source(source, board="arduino-mega")

        compile(result.generated_code, "<generated MicroPython>", "exec")
        self.assertIn("class LumaLCD16x2:", result.generated_code)
        self.assertIn("luma_button_btnCocaCola = Pin(54, Pin.IN, Pin.PULL_UP)", result.generated_code)
        self.assertIn("luma_lcd_pantalla.write('Bienvenido!')", result.generated_code)

        self.assertIn("#include <LiquidCrystal.h>", result.generated_arduino)
        self.assertIn("LiquidCrystal luma_lcd_pantalla(12, 11, 5, 4, 3, 2);", result.generated_arduino)
        self.assertIn("luma_lcd_pantalla.begin(16, 2);", result.generated_arduino)
        self.assertIn("pinMode(13, OUTPUT);", result.generated_arduino)
        self.assertIn("pinMode(58, INPUT_PULLUP);", result.generated_arduino)
        self.assertIn('luma_lcd_pantalla.print("Mountain Dew");', result.generated_arduino)
        self.assertIn("luma_value_estado = 0;", result.generated_arduino)

        self.assertIn(".extern luma_lcd_write", result.generated_assembly)
        self.assertIn("call0 luma_button_read", result.generated_assembly)
        self.assertIn('    .asciz "Bienvenido!"', result.generated_assembly)
        with TemporaryDirectory() as project_dir:
            directory = Path(project_dir)
            (directory / "diagram.json").write_text("{}", encoding="utf-8")
            sketch = write_wokwi_sketch(result.generated_arduino, directory)
            self.assertIn("#include <LiquidCrystal.h>", sketch.read_text(encoding="utf-8"))

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

    def test_exports_generated_code_to_wokwi_project(self):
        with TemporaryDirectory() as project_dir:
            directory = Path(project_dir)
            (directory / "diagram.json").write_text("{}", encoding="utf-8")

            output_path = write_wokwi_main("print('Wokwi')\n", directory)

            self.assertEqual(output_path, directory / "main.py")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "print('Wokwi')\n")

    def test_wokwi_export_requires_project_diagram(self):
        with TemporaryDirectory() as project_dir:
            with self.assertRaisesRegex(ValueError, "diagram.json"):
                write_wokwi_main("print('Wokwi')\n", project_dir)

    def test_wokwi_export_requires_confirmation_to_replace_main(self):
        with TemporaryDirectory() as project_dir:
            directory = Path(project_dir)
            (directory / "diagram.json").write_text("{}", encoding="utf-8")
            main_path = directory / "main.py"
            main_path.write_text("original code\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_wokwi_main("generated code\n", directory)

            write_wokwi_main("generated code\n", directory, overwrite=True)
            self.assertEqual(main_path.read_text(encoding="utf-8"), "generated code\n")

    def test_exports_arduino_sketch_to_wokwi(self):
        with TemporaryDirectory() as project_dir:
            directory = Path(project_dir)
            (directory / "diagram.json").write_text("{}", encoding="utf-8")

            sketch = write_wokwi_sketch("#include <Servo.h>\nvoid setup() {}\n", directory)

            self.assertEqual(sketch, directory / "sketch.ino")
            with self.assertRaises(FileExistsError):
                write_wokwi_sketch("replacement\n", directory)


class WokwiBrowserTests(unittest.TestCase):
    class FakeWindow:
        def __init__(self, title):
            self.title = title
            self.left = 100
            self.top = 40
            self.width = 1200
            self.height = 900

    def test_wokwi_controls_are_relative_to_the_browser_window(self):
        coordinates = _wokwi_coordinates(self.FakeWindow("PUERTA - Wokwi - Google Chrome"))
        self.assertEqual(coordinates["file_tab"], (148, 217))
        self.assertEqual(coordinates["save"], (220, 162))
        self.assertEqual(coordinates["run"], (735, 271))
        self.assertEqual(coordinates["editor"], (400, 458))

    def test_wokwi_controls_match_the_measured_maximized_chrome_layout(self):
        window = self.FakeWindow("esp32 Copy - Wokwi - Google Chrome")
        window.left = -9
        window.top = -9
        window.width = 1938
        window.height = 1098

        coordinates = _wokwi_coordinates(window)

        self.assertEqual(coordinates["file_tab"], (69, 190))
        self.assertEqual(coordinates["save"], (181, 135))
        self.assertEqual(coordinates["run"], (995, 244))
        self.assertEqual(coordinates["editor"], (475, 502))

    def test_selects_the_only_wokwi_window(self):
        target = self.FakeWindow("esp32 - Wokwi - Google Chrome")
        selected = _select_wokwi_window(
            [self.FakeWindow("esp32 - Wokwi - Visual Studio Code"), target]
        )
        self.assertIs(selected, target)

    def test_rejects_non_chrome_or_ambiguous_wokwi_windows(self):
        with self.assertRaisesRegex(WokwiBrowserError, "No se encontró"):
            _select_wokwi_window(
                [self.FakeWindow("esp32 - Wokwi - Visual Studio Code")]
            )
        with self.assertRaisesRegex(WokwiBrowserError, "varias ventanas"):
            _select_wokwi_window(
                [
                    self.FakeWindow("Wokwi - Google Chrome"),
                    self.FakeWindow("Wokwi - Google Chrome"),
                ]
            )


if __name__ == "__main__":
    unittest.main()
