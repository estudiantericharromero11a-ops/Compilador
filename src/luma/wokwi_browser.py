"""Automatización de la pestaña Wokwi abierta en el navegador de Windows."""

from __future__ import annotations

import sys
import time
from typing import Protocol, Sequence


class WokwiBrowserError(Exception):
    """Fallo al encontrar o controlar una ventana del navegador con Wokwi."""


class BrowserWindow(Protocol):
    title: str
    isMinimized: bool
    left: int
    top: int
    width: int
    height: int

    def activate(self) -> None: ...

    def maximize(self) -> None: ...

    def restore(self) -> None: ...


def _select_wokwi_window(windows: Sequence[BrowserWindow]) -> BrowserWindow:
    matches = [
        window
        for window in windows
        if "wokwi" in window.title.lower() and "google chrome" in window.title.lower()
    ]
    if not matches:
        raise WokwiBrowserError(
            "No se encontró Wokwi en Google Chrome. Abre el proyecto en Chrome y vuelve a intentar."
        )
    if len(matches) > 1:
        raise WokwiBrowserError(
            "Hay varias ventanas de Wokwi en Chrome. Deja solo una abierta para evitar editar el proyecto equivocado."
        )
    return matches[0]


def _wokwi_coordinates(window: BrowserWindow) -> dict[str, tuple[int, int]]:
    chrome_height = max(90, min(150, round(window.height * 0.108)))
    page_top = window.top + chrome_height
    page_height = max(1, window.height - chrome_height)
    # Calibrated to the Wokwi header, file tabs, and simulation toolbar in maximized Chrome.
    return {
        "file_tab": (window.left + round(window.width * 0.04), page_top + 80),
        "editor": (
            window.left + round(window.width * 0.25),
            page_top + max(180, round(page_height * 0.4)),
        ),
        "save": (window.left + min(round(window.width * 0.1), 190), page_top + 25),
        "run": (window.left + round(window.width * 0.5) + 35, page_top + 134),
    }


def paste_and_restart_wokwi(code: str, *, target_file: str = "main.py") -> None:
    """Reemplaza el archivo de código activo de Wokwi y reinicia su simulación."""
    if sys.platform != "win32":
        raise WokwiBrowserError("El envío automático a Wokwi está disponible solo en Windows.")
    if not code.strip():
        raise WokwiBrowserError("No hay código compilado para enviar a Wokwi.")
    if target_file not in ("main.py", "sketch.ino"):
        raise WokwiBrowserError(f"Archivo de destino no admitido: {target_file}")

    try:
        import pyautogui
        import pygetwindow
        import pyperclip
    except ImportError as error:
        raise WokwiBrowserError(
            f"Falta {error.name or 'una dependencia de automatización'} en el Python que ejecuta Luma. "
            f"Instálala en ese mismo entorno con: \"{sys.executable}\" -m pip install -e ."
        ) from error

    window = _select_wokwi_window(pygetwindow.getAllWindows())
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
        window.maximize()
        time.sleep(0.8)

        coordinates = _wokwi_coordinates(window)
        pyautogui.click(*coordinates["file_tab"])
        time.sleep(0.35)
        pyautogui.click(*coordinates["editor"])
        time.sleep(0.2)
        pyperclip.copy(code)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.8)
        pyautogui.click(*coordinates["save"])
        time.sleep(0.8)
        pyautogui.click(*coordinates["run"])
    except (OSError, pyautogui.PyAutoGUIException, pyperclip.PyperclipException) as error:
        raise WokwiBrowserError(f"No se pudo actualizar o reiniciar Wokwi: {error}") from error
