"""Comunicación USB/Serial con MicroPython Raw REPL en ESP32."""

from __future__ import annotations

import time


class SerialTransportError(Exception):
    """Fallo al conectar o intercambiar datos con la placa."""


def list_serial_ports() -> list[tuple[str, str]]:
    """Devuelve pares (nombre de puerto, descripción); requiere pyserial."""
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise SerialTransportError("Falta pyserial. Instálalo con: pip install pyserial") from error
    return [(port.device, port.description) for port in list_ports.comports()]


class MicroPythonSerial:
    """Cliente simple del protocolo Raw REPL; requiere firmware MicroPython."""

    def __init__(self, port: str, baudrate: int = 115200):
        try:
            import serial
        except ImportError as error:
            raise SerialTransportError("Falta pyserial. Instálalo con: pip install pyserial") from error
        try:
            self._serial = serial.Serial(port, baudrate=baudrate, timeout=0.1, write_timeout=3)
        except (serial.SerialException, OSError) as error:
            raise SerialTransportError(f"No se pudo abrir {port}: {error}") from error
        time.sleep(1.5)
        self._serial.reset_input_buffer()

    @property
    def is_open(self) -> bool:
        return self._serial.is_open

    def execute(self, source: str, timeout: float = 30.0) -> str:
        """Ejecuta código en Raw REPL y devuelve stdout/stderr del dispositivo."""
        self._serial.timeout = 0.1
        self._serial.write(b"\x03\x03\x01")
        self._serial.flush()
        self._read_until(b">", time.monotonic() + 5.0, "No se pudo entrar en MicroPython Raw REPL")
        self._serial.write(source.encode("utf-8") + b"\x04")
        self._serial.flush()

        deadline = time.monotonic() + timeout
        output = bytearray()
        while time.monotonic() < deadline:
            chunk = self._serial.read(256)
            if not chunk:
                continue
            output.extend(chunk)
            if output.endswith(b"\x04>"):
                break
        else:
            raise SerialTransportError(
                f"Tiempo de espera agotado ({timeout:g} s); el programa puede seguir ejecutándose en la placa"
            )

        response = bytes(output[:-2])
        if response.startswith(b"\x04"):
            response = response[1:]
        stdout, separator, stderr = response.partition(b"\x04")
        if stderr.strip():
            message = stderr.decode("utf-8", errors="replace").strip()
            raise SerialTransportError(f"Error reportado por MicroPython:\n{message}")
        return stdout.decode("utf-8", errors="replace").strip()

    def close(self) -> None:
        """Cierra el puerto serial."""
        if self._serial.is_open:
            self._serial.close()

    def _read_until(self, marker: bytes, deadline: float, message: str) -> bytes:
        output = bytearray()
        while time.monotonic() < deadline:
            chunk = self._serial.read(128)
            output.extend(chunk)
            if marker in output:
                return bytes(output)
        raise SerialTransportError(message)
