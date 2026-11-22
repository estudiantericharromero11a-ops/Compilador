"""Generación de sketches Arduino para Arduino Mega."""

from typing import TypeVar

from .ast import (
    AssignmentStatement,
    ButtonDeclaration,
    ClearDisplayStatement,
    Display7Declaration,
    ForeverStatement,
    IfStatement,
    LedStatement,
    Lcd16x2Declaration,
    LcdClearStatement,
    LcdCursorStatement,
    LcdWriteStatement,
    Program,
    ReadBinaryStatement,
    ReadButtonStatement,
    RepeatStatement,
    ServoDeclaration,
    ServoMoveStatement,
    SingleButtonDeclaration,
    ShowDigitStatement,
    Statement,
    WaitStatement,
)

DIGITS = (
    (0, 0, 0, 0, 0, 0, 1),
    (1, 0, 0, 1, 1, 1, 1),
    (0, 0, 1, 0, 0, 1, 0),
    (0, 0, 0, 0, 1, 1, 0),
    (1, 0, 0, 1, 1, 0, 0),
    (0, 1, 0, 0, 1, 0, 0),
    (0, 1, 0, 0, 0, 0, 0),
    (0, 0, 0, 1, 1, 1, 1),
    (0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 1, 0, 0),
)
TStatement = TypeVar("TStatement", bound=Statement)


class ArduinoCodeGenerator:
    """Traduce el AST a un sketch Arduino compatible con Arduino Mega."""

    def __init__(self) -> None:
        self._repeat_index = 0

    def generate(self, program: Program) -> str:
        self._repeat_index = 0
        buttons = self._find_declarations(program.body, ButtonDeclaration)
        single_buttons = self._find_declarations(program.body, SingleButtonDeclaration)
        buttons_by_name = {declaration.name: declaration for declaration in buttons}
        single_buttons_by_name = {declaration.name: declaration for declaration in single_buttons}
        displays = self._find_declarations(program.body, Display7Declaration)
        lcds = self._find_declarations(program.body, Lcd16x2Declaration)
        servos = self._find_declarations(program.body, ServoDeclaration)
        output_pins = set(self._collect_led_pins(program.body))
        for display in displays:
            output_pins.update(display.pins)
        variables = self._collect_variables(program.body)
        lines = ["#include <Arduino.h>"]
        if servos:
            lines.append("#include <Servo.h>")
        if lcds:
            lines.append("#include <LiquidCrystal.h>")
        lines.append("")

        for declaration in servos:
            lines.append(f"Servo luma_servo_{declaration.name};")
        for variable in sorted(variables):
            lines.append(f"uint16_t luma_value_{variable} = 0;")
        for display in displays:
            pins = ", ".join(str(pin) for pin in display.pins)
            lines.append(f"const uint8_t luma_display_{display.name}[7] = {{{pins}}};")
        for lcd in lcds:
            pins = ", ".join(str(pin) for pin in lcd.pins)
            lines.append(f"LiquidCrystal luma_lcd_{lcd.name}({pins});")
        if servos or variables or displays or lcds:
            lines.append("")

        if displays:
            lines.extend(self._display_helpers(displays))
        lines.extend(["void setup() {"])
        for pin in sorted(output_pins):
            lines.append(f"    pinMode({pin}, OUTPUT);")
        for declaration in buttons:
            mode = "INPUT_PULLUP" if declaration.active_low else "INPUT"
            for pin in declaration.pins:
                lines.append(f"    pinMode({pin}, {mode});")
        for declaration in single_buttons:
            mode = "INPUT_PULLUP" if declaration.active_low else "INPUT"
            lines.append(f"    pinMode({declaration.pin}, {mode});")
        for lcd in lcds:
            lines.append(f"    luma_lcd_{lcd.name}.begin(16, 2);")
        for declaration in servos:
            lines.append(f"    luma_servo_{declaration.name}.attach({declaration.pin});")
        lines.extend(["}", "", "void loop() {"])
        self._emit_statements(program.body, lines, 1, buttons_by_name, single_buttons_by_name)
        lines.extend(["}", ""])
        return "\n".join(lines)

    def _display_helpers(self, displays: list[Display7Declaration]) -> list[str]:
        table = ",\n    ".join(
            "{" + ", ".join(str(segment) for segment in digit) + "}" for digit in DIGITS
        )
        lines = [f"const uint8_t luma_digits[10][7] = {{\n    {table}\n}};", ""]
        for display in displays:
            name = display.name
            lines.extend(
                [
                    f"void luma_clear_display_{name}() {{",
                    "    for (uint8_t index = 0; index < 7; ++index) {",
                    f"        digitalWrite(luma_display_{name}[index], HIGH);",
                    "    }",
                    "}",
                    "",
                    f"void luma_show_digit_{name}(uint8_t number) {{",
                    "    if (number < 10) {",
                    "        for (uint8_t index = 0; index < 7; ++index) {",
                    f"            digitalWrite(luma_display_{name}[index], luma_digits[number][index]);",
                    "        }",
                    "    } else {",
                    f"        luma_clear_display_{name}();",
                    "    }",
                    "}",
                    "",
                ]
            )
        return lines

    def _emit_statements(
        self,
        statements: tuple[Statement, ...],
        lines: list[str],
        depth: int,
        buttons: dict[str, ButtonDeclaration],
        single_buttons: dict[str, SingleButtonDeclaration],
    ) -> None:
        indent = "    " * depth
        for statement in statements:
            if isinstance(statement, LedStatement):
                value = "HIGH" if statement.enabled else "LOW"
                lines.append(f"{indent}digitalWrite({statement.pin}, {value});")
            elif isinstance(statement, AssignmentStatement):
                lines.append(f"{indent}luma_value_{statement.variable} = {statement.value};")
            elif isinstance(statement, ServoMoveStatement):
                lines.append(f"{indent}luma_servo_{statement.servo_name}.write({statement.angle});")
            elif isinstance(statement, ReadButtonStatement):
                declaration = single_buttons[statement.button_name]
                pressed_level = "LOW" if declaration.active_low else "HIGH"
                lines.append(
                    f"{indent}luma_value_{statement.variable} = "
                    f"(digitalRead({declaration.pin}) == {pressed_level}) ? 1 : 0;"
                )
            elif isinstance(statement, LcdClearStatement):
                lines.append(f"{indent}luma_lcd_{statement.lcd_name}.clear();")
            elif isinstance(statement, LcdCursorStatement):
                lines.append(
                    f"{indent}luma_lcd_{statement.lcd_name}.setCursor"
                    f"({statement.column}, {statement.row});"
                )
            elif isinstance(statement, LcdWriteStatement):
                escaped = statement.text.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{indent}luma_lcd_{statement.lcd_name}.print("{escaped}");')
            elif isinstance(statement, WaitStatement):
                lines.append(f"{indent}delay({statement.milliseconds});")
            elif isinstance(statement, RepeatStatement):
                index = self._repeat_index
                self._repeat_index += 1
                lines.append(
                    f"{indent}for (uint32_t luma_repeat_{index} = 0; "
                    f"luma_repeat_{index} < {statement.count}; ++luma_repeat_{index}) {{"
                )
                self._emit_statements(statement.body, lines, depth + 1, buttons, single_buttons)
                lines.append(f"{indent}}}")
            elif isinstance(statement, ForeverStatement):
                lines.append(f"{indent}while (true) {{")
                self._emit_statements(statement.body, lines, depth + 1, buttons, single_buttons)
                lines.append(f"{indent}}}")
            elif isinstance(statement, ReadBinaryStatement):
                declaration = buttons[statement.button_name]
                pressed_level = "LOW" if declaration.active_low else "HIGH"
                terms = [
                    f"((digitalRead({pin}) == {pressed_level}) ? 1 : 0)"
                    for pin in declaration.pins
                ]
                lines.append(
                    f"{indent}luma_value_{statement.variable} = "
                    f"({terms[0]} << 3) | ({terms[1]} << 2) | "
                    f"({terms[2]} << 1) | {terms[3]};"
                )
            elif isinstance(statement, ShowDigitStatement):
                lines.append(
                    f"{indent}luma_show_digit_{statement.display_name}"
                    f"(luma_value_{statement.variable});"
                )
            elif isinstance(statement, ClearDisplayStatement):
                lines.append(f"{indent}luma_clear_display_{statement.display_name}();")
            elif isinstance(statement, IfStatement):
                lines.append(
                    f"{indent}if (luma_value_{statement.variable} "
                    f"{statement.operator} {statement.value}) {{"
                )
                self._emit_statements(statement.body, lines, depth + 1, buttons, single_buttons)
                if statement.else_body:
                    lines.append(f"{indent}}} else {{")
                    self._emit_statements(statement.else_body, lines, depth + 1, buttons, single_buttons)
                lines.append(f"{indent}}}")

    def _collect_led_pins(self, statements: tuple[Statement, ...]) -> set[int]:
        pins: set[int] = set()
        for statement in statements:
            if isinstance(statement, LedStatement):
                pins.add(statement.pin)
            elif isinstance(statement, (RepeatStatement, ForeverStatement)):
                pins.update(self._collect_led_pins(statement.body))
            elif isinstance(statement, IfStatement):
                pins.update(self._collect_led_pins(statement.body))
                pins.update(self._collect_led_pins(statement.else_body))
        return pins

    def _collect_variables(self, statements: tuple[Statement, ...]) -> set[str]:
        variables: set[str] = set()
        for statement in statements:
            if isinstance(statement, (ReadBinaryStatement, ReadButtonStatement, AssignmentStatement)):
                variables.add(statement.variable)
            elif isinstance(statement, (RepeatStatement, ForeverStatement)):
                variables.update(self._collect_variables(statement.body))
            elif isinstance(statement, IfStatement):
                variables.update(self._collect_variables(statement.body))
                variables.update(self._collect_variables(statement.else_body))
        return variables

    def _find_declarations(
        self, statements: tuple[Statement, ...], kind: type[TStatement]
    ) -> list[TStatement]:
        declarations: list[TStatement] = []
        for statement in statements:
            if isinstance(statement, kind):
                declarations.append(statement)
            elif isinstance(statement, (RepeatStatement, ForeverStatement)):
                declarations.extend(self._find_declarations(statement.body, kind))
            elif isinstance(statement, IfStatement):
                declarations.extend(self._find_declarations(statement.body, kind))
                declarations.extend(self._find_declarations(statement.else_body, kind))
        return declarations
