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
        pins = self._collect_led_pins(program.body)
        lines = ["from machine import Pin", "from time import sleep_ms", ""]
        for declaration in button_declarations:
            inputs = ", ".join(
                f"Pin({pin}, Pin.IN, Pin.PULL_DOWN)" for pin in declaration.pins
            )
            lines.append(f"luma_buttons_{declaration.name} = ({inputs},)")
        for declaration in display_declarations:
            outputs = ", ".join(f"Pin({pin}, Pin.OUT)" for pin in declaration.pins)
            lines.append(f"luma_display_{declaration.name} = ({outputs},)")
        for pin in pins:
            lines.append(f"luma_pin_{pin} = Pin({pin}, Pin.OUT)")
        if button_declarations or display_declarations or pins:
            lines.append("")
        if display_declarations:
            self._emit_display_helpers(lines)
        self._emit_statements(program.body, lines, 0)
        return "\n".join(lines).rstrip() + "\n"

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

    def _emit_statements(self, statements: tuple[Statement, ...], lines: list[str], depth: int) -> None:
        indent = "    " * depth
        for statement in statements:
            if isinstance(statement, LedStatement):
                value = 1 if statement.enabled else 0
                lines.append(f"{indent}luma_pin_{statement.pin}.value({value})")
            elif isinstance(statement, WaitStatement):
                lines.append(f"{indent}sleep_ms({statement.milliseconds})")
            elif isinstance(statement, RepeatStatement):
                lines.append(f"{indent}for _ in range({statement.count}):")
                if statement.body:
                    self._emit_statements(statement.body, lines, depth + 1)
                else:
                    lines.append(f"{indent}    pass")
            elif isinstance(statement, ForeverStatement):
                lines.append(f"{indent}while True:")
                if statement.body:
                    self._emit_statements(statement.body, lines, depth + 1)
                else:
                    lines.append(f"{indent}    pass")
            elif isinstance(statement, ReadBinaryStatement):
                inputs = f"luma_buttons_{statement.button_name}"
                target = f"luma_value_{statement.variable}"
                lines.append(
                    f"{indent}{target} = ({inputs}[0].value() << 3) | "
                    f"({inputs}[1].value() << 2) | "
                    f"({inputs}[2].value() << 1) | {inputs}[3].value()"
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
                self._emit_block(statement.body, lines, depth)
                if statement.else_body:
                    lines.append(f"{indent}else:")
                    self._emit_block(statement.else_body, lines, depth)

    def _emit_block(self, statements: tuple[Statement, ...], lines: list[str], depth: int) -> None:
        if statements:
            self._emit_statements(statements, lines, depth + 1)
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
