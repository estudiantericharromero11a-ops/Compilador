"""Interfaz gráfica Tkinter para editar, compilar y ejecutar programas Luma."""

from __future__ import annotations

import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .compiler import compile_source
from .errors import LumaError
from .transport import MicroPythonSerial, SerialTransportError, list_serial_ports

SAMPLE_PROGRAM = """INICIAR

REPETIR 5
    LED 2 ENCENDER
    ESPERAR 500
    LED 2 APAGAR
    ESPERAR 500
FIN_REPETIR

FINALIZAR
"""


class LumaApp:
    """Ventana principal del editor Luma."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Luma — Compilador para ESP32")
        self.root.geometry("1100x760")
        self.transport: MicroPythonSerial | None = None
        self.current_path: Path | None = None
        self.generated_code: str | None = None
        self._build_ui()
        self._refresh_ports()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)
        for label, command in (
            ("Nuevo", self._new_file),
            ("Abrir", self._open_file),
            ("Guardar", self._save_file),
            ("Compilar", self._compile),
        ):
            ttk.Button(toolbar, text=label, command=command).pack(side=tk.LEFT, padx=3)

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(toolbar, textvariable=self.port_var, width=17, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(16, 3))
        ttk.Button(toolbar, text="Actualizar", command=self._refresh_ports).pack(side=tk.LEFT, padx=3)
        self.connect_button = ttk.Button(toolbar, text="Conectar", command=self._connect)
        self.connect_button.pack(side=tk.LEFT, padx=3)
        self.run_button = ttk.Button(toolbar, text="Ejecutar en ESP32", command=self._run, state=tk.DISABLED)
        self.run_button.pack(side=tk.LEFT, padx=3)
        self.status_var = tk.StringVar(value="Desconectado")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.RIGHT, padx=8)

        panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        editor_frame = ttk.Labelframe(panes, text="Programa Luma", padding=5)
        output_frame = ttk.Labelframe(panes, text="Código generado", padding=5)
        panes.add(editor_frame, weight=1)
        panes.add(output_frame, weight=1)

        self.editor = ScrolledText(editor_frame, wrap=tk.NONE, undo=True, font=("Consolas", 11))
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.insert("1.0", SAMPLE_PROGRAM)
        self.editor.edit_modified(False)
        self.editor.bind("<KeyRelease>", self._highlight)
        output_tabs = ttk.Notebook(output_frame)
        output_tabs.pack(fill=tk.BOTH, expand=True)
        micropython_frame = ttk.Frame(output_tabs)
        assembly_frame = ttk.Frame(output_tabs)
        output_tabs.add(micropython_frame, text="MicroPython")
        output_tabs.add(assembly_frame, text="Ensamblador Xtensa")
        self.output = ScrolledText(
            micropython_frame, wrap=tk.NONE, font=("Consolas", 10), state=tk.DISABLED
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self.assembly_output = ScrolledText(
            assembly_frame, wrap=tk.NONE, font=("Consolas", 10), state=tk.DISABLED
        )
        self.assembly_output.pack(fill=tk.BOTH, expand=True)
        self.editor.tag_configure("keyword", foreground="#185abc")
        self.editor.tag_configure("comment", foreground="#718096")

        log_frame = ttk.Labelframe(self.root, text="Mensajes", padding=5)
        log_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.log = ScrolledText(log_frame, height=6, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED)
        self.log.pack(fill=tk.X)
        self._highlight()

    def _highlight(self, _event: tk.Event | None = None) -> None:
        source = self.editor.get("1.0", "end-1c")
        self.editor.tag_remove("keyword", "1.0", tk.END)
        self.editor.tag_remove("comment", "1.0", tk.END)
        keywords = (
            r"\b(?:INICIAR|FINALIZAR|LED|ENCENDER|APAGAR|ESPERAR|REPETIR|FIN_REPETIR|"
            r"BOTONES|COMO|DISPLAY7|ACTIVO_BAJO|LEER_BINARIO|SI|SINO|FIN_SI|MOSTRAR|EN|"
            r"LIMPIAR|REPETIR_SIEMPRE|FIN_REPETIR_SIEMPRE)\b"
        )
        for match in re.finditer(keywords, source, re.IGNORECASE):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.editor.tag_add("keyword", start, end)
        for match in re.finditer(r"#.*", source):
            self.editor.tag_add("comment", f"1.0+{match.start()}c", f"1.0+{match.end()}c")

    def _refresh_ports(self) -> None:
        try:
            ports = list_serial_ports()
        except SerialTransportError as error:
            self._log(str(error))
            return
        self.port_combo["values"] = [f"{port} — {description}" for port, description in ports]
        if ports and not self.port_var.get():
            self.port_var.set(self.port_combo["values"][0])

    def _connect(self) -> None:
        if self.transport is not None:
            self._disconnect()
            return
        selected = self.port_var.get()
        if not selected:
            messagebox.showwarning("Puerto requerido", "Selecciona un puerto COM conectado.")
            return
        port = selected.split(" — ", 1)[0]
        try:
            self.transport = MicroPythonSerial(port)
        except SerialTransportError as error:
            messagebox.showerror("No se pudo conectar", str(error))
            self._log(str(error))
            return
        self.status_var.set(f"Conectado: {port}")
        self.connect_button.configure(text="Desconectar")
        self.run_button.configure(state=tk.NORMAL)
        self._log(f"Puerto {port} abierto a 115200 baudios. Se requiere MicroPython en la placa.")

    def _disconnect(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        self.status_var.set("Desconectado")
        self.connect_button.configure(text="Conectar")
        self.run_button.configure(state=tk.DISABLED)
        self._log("Puerto serial cerrado.")

    def _compile(self) -> bool:
        try:
            result = compile_source(self.editor.get("1.0", "end-1c"))
        except LumaError as error:
            self.generated_code = None
            self._set_output("")
            self._set_assembly_output("")
            self._log(f"Error de compilación: {error}")
            self.editor.mark_set(tk.INSERT, f"{error.location.line}.{error.location.column - 1}")
            self.editor.see(tk.INSERT)
            messagebox.showerror("Error de compilación", str(error))
            return False
        self.generated_code = result.generated_code
        self._set_output(result.generated_code)
        self._set_assembly_output(result.generated_assembly)
        self._log(
            "Compilación correcta: análisis léxico, sintáctico y semántico completados; "
            "salidas MicroPython y ensamblador Xtensa generadas."
        )
        return True

    def _run(self) -> None:
        if self.transport is None:
            messagebox.showwarning("Sin conexión", "Conecta primero una placa con MicroPython.")
            return
        if not self._compile():
            return
        self.run_button.configure(state=tk.DISABLED)
        self.status_var.set("Ejecutando…")
        code = self.generated_code or ""
        thread = threading.Thread(target=self._execute_worker, args=(code,), daemon=True)
        thread.start()

    def _execute_worker(self, code: str) -> None:
        try:
            if self.transport is None:
                raise SerialTransportError("La conexión serial se cerró antes de ejecutar.")
            output = self.transport.execute(code)
            self.root.after(0, self._execution_finished, output, None)
        except SerialTransportError as error:
            self.root.after(0, self._execution_finished, "", str(error))

    def _execution_finished(self, output: str, error: str | None) -> None:
        if error:
            self._log(f"Error de ejecución: {error}")
            self.status_var.set("Error de ejecución")
            messagebox.showerror("Error de ejecución", error)
        else:
            self._log("Programa ejecutado en el ESP32." + (f"\n{output}" if output else ""))
            self.status_var.set("Conectado")
        if self.transport is not None:
            self.run_button.configure(state=tk.NORMAL)

    def _new_file(self) -> None:
        if self._confirm_discard():
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", SAMPLE_PROGRAM)
            self.editor.edit_modified(False)
            self.current_path = None

    def _open_file(self) -> None:
        if not self._confirm_discard():
            return
        name = filedialog.askopenfilename(filetypes=[("Programas Luma", "*.luma"), ("Todos los archivos", "*.*")])
        if not name:
            return
        try:
            source = Path(name).read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("No se pudo abrir el archivo", str(error))
            return
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", source)
        self.editor.edit_modified(False)
        self.current_path = Path(name)
        self._highlight()

    def _save_file(self) -> bool:
        if self.current_path is None:
            name = filedialog.asksaveasfilename(
                defaultextension=".luma", filetypes=[("Programas Luma", "*.luma")]
            )
            if not name:
                return False
            self.current_path = Path(name)
        try:
            self.current_path.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
        except OSError as error:
            messagebox.showerror("No se pudo guardar el archivo", str(error))
            return False
        self.editor.edit_modified(False)
        self._log(f"Archivo guardado: {self.current_path}")
        return True

    def _confirm_discard(self) -> bool:
        if not self.editor.edit_modified():
            return True
        if not messagebox.askyesno("Cambios sin guardar", "¿Descartar los cambios no guardados?"):
            return False
        self.editor.edit_modified(False)
        return True

    def _set_output(self, code: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", code)
        self.output.configure(state=tk.DISABLED)

    def _set_assembly_output(self, code: str) -> None:
        self.assembly_output.configure(state=tk.NORMAL)
        self.assembly_output.delete("1.0", tk.END)
        self.assembly_output.insert("1.0", code)
        self.assembly_output.configure(state=tk.DISABLED)

    def _log(self, message: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        if self.transport is not None:
            self.transport.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    LumaApp(root)
    root.mainloop()
