"""Generación de ensamblador GNU Xtensa LX6 para ESP32 clásico."""

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

TStatement = TypeVar("TStatement", bound=Statement)


class XtensaAssemblyCodeGenerator:
    """Genera una función Xtensa que llama a rutinas de hardware externas."""

    def generate(self, program: Program) -> str:
        self._next_label = 0
        self._buttons = self._find_declarations(program.body, ButtonDeclaration)
        self._displays = self._find_declarations(program.body, Display7Declaration)
        self._variables = self._collect_variables(program.body)
        repeat_slots = self._max_repeat_depth(program.body)
        self._repeat_base = len(self._variables) * 4
        frame_size = ((max(16, 8 + self._repeat_base + repeat_slots * 4) + 15) // 16) * 16
        self._frame_size = frame_size
        self._variable_offsets = {name: index * 4 for index, name in enumerate(self._variables)}
        lines = [
            ".text",
            ".align 4",
            ".global luma_program",
            ".type luma_program, @function",
            ".extern luma_led_write",
            ".extern luma_wait_ms",
            ".extern luma_buttons_setup",
            ".extern luma_display_setup",
            ".extern luma_read_buttons",
            ".extern luma_display_show",
            ".extern luma_display_clear",
            "# Hardware hooks use a2 and subsequent ABI argument registers.",
            "luma_program:",
            *self._stack_adjustment(frame_size, allocate=True),
            f"    s32i a0, a1, {frame_size - 4}",
        ]
        for declaration in self._buttons:
            lines.extend(
                [
                    f"    l32r a2, .Lbuttons_ptr_{declaration.name}",
                    "    call0 luma_buttons_setup",
                ]
            )
        for declaration in self._displays:
            lines.extend(
                [
                    f"    l32r a2, .Ldisplay_ptr_{declaration.name}",
                    "    call0 luma_display_setup",
                ]
            )
        self._emit_statements(program.body, lines, 0)
        lines.extend(
            [
                f"    l32i a0, a1, {frame_size - 4}",
                *self._stack_adjustment(frame_size, allocate=False),
                "    ret",
                ".size luma_program, .-luma_program",
            ]
        )
        rodata = self._emit_data_tables()
        if rodata:
            lines.extend(["", ".section .rodata", ".align 4", *rodata])
        return "\n".join(lines) + "\n"

    def _emit_statements(self, statements: tuple[Statement, ...], lines: list[str], repeat_depth: int) -> None:
        indent = "    "
        for statement in statements:
            if isinstance(statement, LedStatement):
                self._emit_constant(lines, "a2", statement.pin, indent)
                self._emit_constant(lines, "a3", int(statement.enabled), indent)
                lines.append(f"{indent}call0 luma_led_write")
            elif isinstance(statement, WaitStatement):
                self._emit_constant(lines, "a2", statement.milliseconds, indent)
                lines.append(f"{indent}call0 luma_wait_ms")
            elif isinstance(statement, ButtonDeclaration):
                continue
            elif isinstance(statement, Display7Declaration):
                continue
            elif isinstance(statement, RepeatStatement):
                label = self._new_label()
                counter_offset = self._repeat_base + repeat_depth * 4
                self._emit_constant(lines, "a4", statement.count, indent)
                lines.extend([f"{indent}s32i a4, a1, {counter_offset}", f".Lrepeat_start_{label}:"])
                self._emit_statements(statement.body, lines, repeat_depth + 1)
                lines.extend(
                    [
                        f"{indent}l32i a4, a1, {counter_offset}",
                        f"{indent}addi a4, a4, -1",
                        f"{indent}s32i a4, a1, {counter_offset}",
                        f"{indent}beqz a4, .Lrepeat_end_{label}",
                        f"{indent}j .Lrepeat_start_{label}",
                        f".Lrepeat_end_{label}:",
                    ]
                )
            elif isinstance(statement, ForeverStatement):
                label = self._new_label()
                lines.append(f".Lforever_start_{label}:")
                self._emit_statements(statement.body, lines, repeat_depth)
                lines.append(f"{indent}j .Lforever_start_{label}")
            elif isinstance(statement, ReadBinaryStatement):
                lines.extend(
                    [
                        f"{indent}l32r a2, .Lbuttons_ptr_{statement.button_name}",
                        f"{indent}call0 luma_read_buttons",
                        f"{indent}s32i a2, a1, {self._variable_offsets[statement.variable]}",
                    ]
                )
            elif isinstance(statement, ShowDigitStatement):
                lines.extend(
                    [
                        f"{indent}l32r a2, .Ldisplay_ptr_{statement.display_name}",
                        f"{indent}l32i a3, a1, {self._variable_offsets[statement.variable]}",
                        f"{indent}call0 luma_display_show",
                    ]
                )
            elif isinstance(statement, ClearDisplayStatement):
                lines.extend(
                    [
                        f"{indent}l32r a2, .Ldisplay_ptr_{statement.display_name}",
                        f"{indent}call0 luma_display_clear",
                    ]
                )
            elif isinstance(statement, IfStatement):
                else_label = self._new_label()
                end_label = self._new_label()
                lines.extend(
                    [
                        f"{indent}l32i a4, a1, {self._variable_offsets[statement.variable]}",
                    ]
                )
                self._emit_constant(lines, "a5", statement.value, indent)
                inverse_branch = {"<": "bge", "<=": "blt", ">": "bge", ">=": "blt", "==": "bne", "!=": "beq"}[
                    statement.operator
                ]
                left, right = ("a5", "a4") if statement.operator in ("<=", ">") else ("a4", "a5")
                lines.append(f"{indent}{inverse_branch} {left}, {right}, .Lelse_{else_label}")
                self._emit_statements(statement.body, lines, repeat_depth)
                lines.append(f"{indent}j .Lendif_{end_label}")
                lines.append(f".Lelse_{else_label}:")
                self._emit_statements(statement.else_body, lines, repeat_depth)
                lines.append(f".Lendif_{end_label}:")

    def _emit_data_tables(self) -> list[str]:
        lines: list[str] = []
        for declaration in self._buttons:
            lines.extend(
                [
                    f".Lbuttons_ptr_{declaration.name}:",
                    f"    .long .Lbuttons_{declaration.name}",
                    f".Lbuttons_{declaration.name}:",
                    "    .long " + ", ".join(str(pin) for pin in declaration.pins),
                ]
            )
        for declaration in self._displays:
            lines.extend(
                [
                    f".Ldisplay_ptr_{declaration.name}:",
                    f"    .long .Ldisplay_{declaration.name}",
                    f".Ldisplay_{declaration.name}:",
                    "    .long " + ", ".join(str(pin) for pin in declaration.pins),
                ]
            )
        return lines

    def _stack_adjustment(self, frame_size: int, allocate: bool) -> list[str]:
        if frame_size <= 127:
            adjustment = -frame_size if allocate else frame_size
            return [f"    addi a1, a1, {adjustment}"]
        operation = "sub" if allocate else "add"
        return [f"    movi a8, {frame_size}", f"    {operation} a1, a1, a8"]

    def _emit_constant(self, lines: list[str], register: str, value: int, indent: str) -> None:
        if value <= 2047:
            lines.append(f"{indent}movi {register}, {value}")
            return
        chunks: list[int] = []
        while value:
            chunks.append(value & 0xFF)
            value >>= 8
        lines.append(f"{indent}movi {register}, {chunks.pop()}")
        for chunk in reversed(chunks):
            lines.append(f"{indent}slli {register}, {register}, 8")
            if chunk:
                lines.append(f"{indent}movi a7, {chunk}")
                lines.append(f"{indent}or {register}, {register}, a7")

    def _collect_variables(self, statements: tuple[Statement, ...]) -> list[str]:
        variables: list[str] = []
        for statement in statements:
            if isinstance(statement, ReadBinaryStatement) and statement.variable not in variables:
                variables.append(statement.variable)
            elif isinstance(statement, (RepeatStatement, ForeverStatement)):
                for name in self._collect_variables(statement.body):
                    if name not in variables:
                        variables.append(name)
            elif isinstance(statement, IfStatement):
                for name in (*self._collect_variables(statement.body), *self._collect_variables(statement.else_body)):
                    if name not in variables:
                        variables.append(name)
        return variables

    def _max_repeat_depth(self, statements: tuple[Statement, ...]) -> int:
        maximum = 0
        for statement in statements:
            if isinstance(statement, RepeatStatement):
                maximum = max(maximum, 1 + self._max_repeat_depth(statement.body))
            elif isinstance(statement, ForeverStatement):
                maximum = max(maximum, self._max_repeat_depth(statement.body))
            elif isinstance(statement, IfStatement):
                maximum = max(
                    maximum,
                    self._max_repeat_depth(statement.body),
                    self._max_repeat_depth(statement.else_body),
                )
        return maximum

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

    def _new_label(self) -> int:
        label = self._next_label
        self._next_label += 1
        return label
