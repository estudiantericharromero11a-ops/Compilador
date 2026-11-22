"""Generación de código MicroPython para el ESP32."""

from typing import TypeVar

from .ast import (
    ButtonDeclaration,
    ClearDisplayStatement,
    Display7Declaration,
    ForeverStatement,
    IfStatement,
    LedStatement,
    Program,
    ReadBinaryStatement,
    RepeatStatement,
    ServoDeclaration,
    ServoMoveStatement,
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


class MicroPythonCodeGenerator:
    """Traduce el AST a un script ejecutable en MicroPython."""

    def generate(self, program: Program) -> str:
        button_declarations = self._find_declarations(program.body, ButtonDeclaration)
        display_declarations = self._find_declarations(program.body, Display7Declaration)
        servo_declarations = self._find_declarations(program.body, ServoDeclaration)
        pins = self._collect_led_pins(program.body)
        pin_import = "from machine import Pin, PWM" if servo_declarations else "from machine import Pin"
        lines = [pin_import, "from time import sleep_ms", ""]
        for declaration in button_declarations:
            pull = "Pin.PULL_UP" if declaration.active_low else "Pin.PULL_DOWN"
            inputs = ", ".join(
                f"Pin({pin}, Pin.IN, {pull})" for pin in declaration.pins
            )
            lines.append(f"luma_buttons_{declaration.name} = ({inputs},)")
        for declaration in display_declarations:
            outputs = ", ".join(f"Pin({pin}, Pin.OUT)" for pin in declaration.pins)
            lines.append(f"luma_display_{declaration.name} = ({outputs},)")
        for declaration in servo_declarations:
            lines.append(f"luma_servo_{declaration.name} = PWM(Pin({declaration.pin}), freq=50)")
        for pin in pins:
            lines.append(f"luma_pin_{pin} = Pin({pin}, Pin.OUT)")
        if button_declarations or display_declarations or servo_declarations or pins:
            lines.append("")
        if servo_declarations:
            self._emit_servo_helpers(lines)
        if display_declarations:
            self._emit_display_helpers(lines)
        button_polarities = {declaration.name: declaration.active_low for declaration in button_declarations}
        self._emit_statements(program.body, lines, 0, button_polarities)
        return "\n".join(lines).rstrip() + "\n"

    def _emit_servo_helpers(self, lines: list[str]) -> None:
        lines.extend(
            [
                "def luma_servo_set_angle(servo, angle):",
                "    pulse_us = 500 + (angle * 2000 // 180)",
                "    servo.duty_u16(pulse_us * 65535 // 20000)",
                "",
            ]
        )

    def _emit_display_helpers(self, lines: list[str]) -> None:
        table = ",\n    ".join(repr(digit) for digit in DIGITS)
        lines.extend(
            [
                f"luma_digits = (\n    {table},\n)",
                "",
                "def luma_show_digit(display, number):",
                "    if 0 <= number < len(luma_digits):",
                "        pattern = luma_digits[number]",
                "        for index in range(7):",
                "            display[index].value(pattern[index])",
                "    else:",
                "        luma_clear_display(display)",
                "",
                "def luma_clear_display(display):",
                "    for segment in display:",
                "        segment.value(1)",
                "",
            ]
        )

    def _emit_statements(
        self,
        statements: tuple[Statement, ...],
        lines: list[str],
        depth: int,
        button_polarities: dict[str, bool],
    ) -> None:
        indent = "    " * depth
        for statement in statements:
            if isinstance(statement, LedStatement):
                value = 1 if statement.enabled else 0
                lines.append(f"{indent}luma_pin_{statement.pin}.value({value})")
            elif isinstance(statement, ServoMoveStatement):
                lines.append(
                    f"{indent}luma_servo_set_angle(luma_servo_{statement.servo_name}, {statement.angle})"
                )
            elif isinstance(statement, WaitStatement):
                lines.append(f"{indent}sleep_ms({statement.milliseconds})")
            elif isinstance(statement, RepeatStatement):
                lines.append(f"{indent}for _ in range({statement.count}):")
                if statement.body:
                    self._emit_statements(statement.body, lines, depth + 1, button_polarities)
                else:
                    lines.append(f"{indent}    pass")
            elif isinstance(statement, ForeverStatement):
                lines.append(f"{indent}while True:")
                if statement.body:
                    self._emit_statements(statement.body, lines, depth + 1, button_polarities)
                else:
                    lines.append(f"{indent}    pass")
            elif isinstance(statement, ReadBinaryStatement):
                inputs = f"luma_buttons_{statement.button_name}"
                target = f"luma_value_{statement.variable}"
                bits = [
                    f"{inputs}[{index}].value()"
                    if not button_polarities[statement.button_name]
                    else f"(1 - {inputs}[{index}].value())"
                    for index in range(4)
                ]
                lines.append(
                    f"{indent}{target} = ({bits[0]} << 3) | "
                    f"({bits[1]} << 2) | ({bits[2]} << 1) | {bits[3]}"
                )
            elif isinstance(statement, ShowDigitStatement):
                lines.append(
                    f"{indent}luma_show_digit(luma_display_{statement.display_name}, "
                    f"luma_value_{statement.variable})"
                )
            elif isinstance(statement, ClearDisplayStatement):
                lines.append(f"{indent}luma_clear_display(luma_display_{statement.display_name})")
            elif isinstance(statement, IfStatement):
                lines.append(
                    f"{indent}if luma_value_{statement.variable} {statement.operator} {statement.value}:"
                )
                self._emit_block(statement.body, lines, depth, button_polarities)
                if statement.else_body:
                    lines.append(f"{indent}else:")
                    self._emit_block(statement.else_body, lines, depth, button_polarities)

    def _emit_block(
        self,
        statements: tuple[Statement, ...],
        lines: list[str],
        depth: int,
        button_polarities: dict[str, bool],
    ) -> None:
        if statements:
            self._emit_statements(statements, lines, depth + 1, button_polarities)
        else:
            lines.append(f"{'    ' * (depth + 1)}pass")

    def _collect_led_pins(self, statements: tuple[Statement, ...]) -> list[int]:
        pins: set[int] = set()
        for statement in statements:
            if isinstance(statement, LedStatement):
                pins.add(statement.pin)
            elif isinstance(statement, (RepeatStatement, ForeverStatement)):
                pins.update(self._collect_led_pins(statement.body))
            elif isinstance(statement, IfStatement):
                pins.update(self._collect_led_pins(statement.body))
                pins.update(self._collect_led_pins(statement.else_body))
        return sorted(pins)

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
