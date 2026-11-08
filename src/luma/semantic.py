"""Validaciones semánticas para los nodos del lenguaje Luma."""

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
from .errors import LumaError


class SemanticAnalyzer:
    """Valida declaraciones, tipos de instrucción y límites del ESP32 clásico."""

    OUTPUT_GPIO = frozenset((0, 1, 2, 3, 4, 5, *range(12, 20), 21, 22, 23, 25, 26, 27, 32, 33))
    INPUT_GPIO = OUTPUT_GPIO
    MAX_WAIT_MS = 86_400_000
    MAX_REPEAT_COUNT = 10_000

    def analyze(self, program: Program) -> None:
        self._names: dict[str, str] = {}
        self._variables: set[str] = set()
        self._pins: dict[int, str] = {}
        self._analyze_statements(program.body, nested=False)

    def _analyze_statements(self, statements: tuple[Statement, ...], nested: bool) -> None:
        for statement in statements:
            if isinstance(statement, ButtonDeclaration):
                if nested:
                    self._error("BOTONES debe declararse fuera de los bloques", statement)
                self._declare_name(statement.name, "buttons", statement)
                self._validate_pins(
                    statement.pins, self.INPUT_GPIO, "entrada", statement, f"BOTONES {statement.name}"
                )
            elif isinstance(statement, Display7Declaration):
                if nested:
                    self._error("DISPLAY7 debe declararse fuera de los bloques", statement)
                self._declare_name(statement.name, "display", statement)
                self._validate_pins(
                    statement.pins, self.OUTPUT_GPIO, "salida", statement, f"DISPLAY7 {statement.name}"
                )
            elif isinstance(statement, LedStatement):
                if statement.pin not in self.OUTPUT_GPIO:
                    self._error(
                        "GPIO no disponible como salida segura en ESP32 clásico; consulta el pinout de tu placa",
                        statement,
                    )
                self._claim_pin(statement.pin, statement, "LED")
            elif isinstance(statement, WaitStatement):
                if not 0 <= statement.milliseconds <= self.MAX_WAIT_MS:
                    self._error(f"ESPERAR debe estar entre 0 y {self.MAX_WAIT_MS} milisegundos", statement)
            elif isinstance(statement, RepeatStatement):
                if not 1 <= statement.count <= self.MAX_REPEAT_COUNT:
                    self._error(f"REPETIR debe estar entre 1 y {self.MAX_REPEAT_COUNT}", statement)
                self._analyze_statements(statement.body, nested=True)
            elif isinstance(statement, ForeverStatement):
                self._analyze_statements(statement.body, nested=True)
            elif isinstance(statement, ReadBinaryStatement):
                self._require_name(statement.button_name, "buttons", statement)
                self._variables.add(statement.variable)
            elif isinstance(statement, ShowDigitStatement):
                self._require_name(statement.display_name, "display", statement)
                self._require_variable(statement.variable, statement)
            elif isinstance(statement, ClearDisplayStatement):
                self._require_name(statement.display_name, "display", statement)
            elif isinstance(statement, IfStatement):
                self._require_variable(statement.variable, statement)
                if statement.operator not in ("<", "<=", ">", ">=", "==", "!="):
                    self._error(f"Operador no admitido: {statement.operator}", statement)
                if not 0 <= statement.value <= 15:
                    self._error("El valor de comparación debe estar entre 0 y 15", statement)
                before = self._variables.copy()
                self._analyze_statements(statement.body, nested=True)
                then_variables = self._variables.copy()
                self._variables = before.copy()
                self._analyze_statements(statement.else_body, nested=True)
                self._variables &= then_variables

    def _declare_name(self, name: str, kind: str, statement: Statement) -> None:
        if name in self._names:
            self._error(f"El nombre {name!r} ya está declarado", statement)
        self._names[name] = kind

    def _require_name(self, name: str, kind: str, statement: Statement) -> None:
        if self._names.get(name) != kind:
            expected = "BOTONES" if kind == "buttons" else "DISPLAY7"
            self._error(f"{name!r} no está declarado como {expected}", statement)

    def _require_variable(self, name: str, statement: Statement) -> None:
        if name not in self._variables:
            self._error(f"La variable {name!r} no tiene un valor asignado", statement)

    def _validate_pins(
        self,
        pins: tuple[int, ...],
        allowed: frozenset[int],
        direction: str,
        statement: Statement,
        owner: str,
    ) -> None:
        if len(set(pins)) != len(pins):
            self._error(f"Un GPIO no puede repetirse en la misma declaración de {direction}", statement)
        for pin in pins:
            if pin not in allowed:
                self._error(f"GPIO {pin} no disponible como {direction} segura en ESP32 clásico", statement)
            self._claim_pin(pin, statement, owner)

    def _claim_pin(self, pin: int, statement: Statement, owner: str) -> None:
        if pin in self._pins and self._pins[pin] != owner:
            self._error(f"GPIO {pin} ya está ocupado por otra instrucción o dispositivo", statement)
        self._pins[pin] = owner

    @staticmethod
    def _error(message: str, statement: Statement) -> None:
        raise LumaError(message, statement.location)
