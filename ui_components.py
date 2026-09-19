"""Componentes de interfaz reutilizables de AS Facturation.

Extraídos de ``Main.py`` para separar los widgets/diálogos de la lógica de la
aplicación: tokens de diseño (``UI``), utilidades defensivas de Tkinter y los
diálogos modales (``ModernDialog`` / ``ModernMessageBox``).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any, Dict, Iterable, Optional, Tuple

import tkinter as tk
import customtkinter as ctk
from PIL import Image


def open_path(path: str) -> None:
    """Abre un archivo o carpeta con la aplicación del sistema (multiplataforma).

    Usa os.startfile (Windows), open (macOS) o xdg-open (Linux).
    """
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# =============================================================================
# CACHÉ DE IMÁGENES — Evita recargar logos/iconos desde disco en cada uso
# =============================================================================
_IMAGE_CACHE: Dict[Tuple[str, int, int], Any] = {}
_IMAGE_CACHE_MAX = 64


def load_ctk_image(path: str, size: Tuple[int, int] = (30, 30)) -> Optional[ctk.CTkImage]:
    """Carga una imagen como ``CTkImage`` y la reutiliza si ya se cargó.

    La clave del caché combina la ruta absoluta con el tamaño solicitado, por lo
    que pedir el mismo archivo con el mismo tamaño no vuelve a leer el disco.
    """
    if not path:
        return None
    key = (os.path.normcase(os.path.abspath(path)), int(size[0]), int(size[1]))
    cached = _IMAGE_CACHE.get(key)
    if cached is not None:
        return cached
    if not os.path.exists(path):
        return None
    try:
        image = Image.open(path).convert("RGBA")
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except Exception:
        return None
    if len(_IMAGE_CACHE) >= _IMAGE_CACHE_MAX:
        _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE)), None)
    _IMAGE_CACHE[key] = ctk_image
    return ctk_image


def clear_image_cache() -> None:
    """Libera todas las imágenes en caché (útil al cerrar la aplicación)."""
    _IMAGE_CACHE.clear()


def safe_destroy(widget: Optional[Any]) -> None:
    """Destruye de forma segura un widget Tkinter/CTk si existe.

    Solo captura errores propios de Tkinter (widget ya destruido o sin
    ``winfo_exists``); cualquier otro error se propaga para no ocultar fallos.
    """
    if widget is None:
        return
    try:
        exists = bool(widget.winfo_exists())
    except (AttributeError, tk.TclError):
        exists = True
    if not exists:
        return
    try:
        widget.destroy()
    except tk.TclError:
        pass


def safe_widget_insert(widget: Any, index: Any, text: Any) -> None:
    """Insertar texto de forma segura en widgets Entry/Text/CtkEntry.

    Convierte ``None`` a cadena vacía y solo ignora los ``TclError`` esperados
    de Tkinter al insertar con índices incompatibles.
    """
    value = "" if text is None else str(text)
    try:
        widget.insert(index, value)
        return
    except tk.TclError:
        pass
    try:
        widget.insert(value)
        return
    except tk.TclError:
        pass
    try:
        widget.configure(state="normal")
        widget.delete(0, "end")
        widget.insert(0, value)
    except tk.TclError:
        pass


def toggle_password_visibility(entry: Any, button: Any) -> None:
    """Alternar visibilidad de la contraseña en un CTkEntry."""
    if entry.cget("show") == "*":
        entry.configure(show="")
        button.configure(text="👁️")  # Ojo abierto: Ver
    else:
        entry.configure(show="*")
        button.configure(text="🔒")  # Candado/Ojo tachado: Ocultar


def format_ci_rif(value: Any) -> str:
    """Normaliza cédula/RIF agrupando los dígitos de 3 en 3:
    '30.2689.58' -> '30.268.958', '11609827' -> '11.609.827',
    'J-123456789' -> 'J-123.456.789'."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    prefix_match = re.match(r"^\s*([A-Za-z]{1,3})", s)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return s
    groups = [digits[max(0, i - 3):i] for i in range(len(digits), 0, -3)]
    grouped = ".".join(reversed(groups))
    if prefix_match:
        return f"{prefix_match.group(1)}-{grouped}"
    return grouped


# =============================================================================
# TOKENS DE DISEÑO — Paleta, tipografía y radios coherentes
# =============================================================================
class UI:
    """Tokens de diseño centralizados para mantener coherencia visual."""

    # Superficies
    BG = "#F8FAFC"
    CARD = "#FFFFFF"
    FIELD = "#FFFFFF"
    MUTED = "#E2E8F0"
    BORDER = "#CBD5E1"

    # Texto
    TEXT = "#1E293B"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED = "#64748B"

    # Tokens en tupla (light, dark) para flat surfaces y textos invariantes
    CARD_T = ("#FFFFFF", "#1E293B")
    CARD_DARK_T = ("#FFFFFF", "#2A2A3C")
    BG_T = ("#F8FAFC", "#0F172A")
    BG_DARK_T = ("#F8FAFC", "#1A1A2E")
    MUTED_T = ("#E2E8F0", "#334155")
    BORDER_T = ("#CBD5E1", "#334155")
    BORDER_LIGHT_T = ("#E2E8F0", "#475569")
    FIELD_DARK_T = ("#E2E8F0", "#2A2A3C")
    FIELD_MID_T = ("#E2E8F0", "#3F3F5F")
    SELECT_BG_T = ("#F1F5F9", "#334155")
    SLATE_100_VDARK_T = ("#F1F5F9", "#0F172A")
    TEXT_T = ("#1E293B", "#F8FAFC")
    TEXT_SEC_T = ("#475569", "#CBD5E1")
    NEUTRAL_T = ("#64748B", "#94A3B8")
    NEUTRAL_DARK_T = ("#64748B", "#334155")
    NEUTRAL_MUTED_T = ("#64748B", "#A0A0B8")
    PLACEHOLDER_T = ("#94A3B8", "#475569")
    PRIMARY_T = ("#2563EB", "#3B82F6")
    PRIMARY_HOVER_T = ("#1D4ED8", "#2563EB")
    ACCENT_T = ("#2563EB", "#60A5FA")

    # Acciones
    PRIMARY = "#2563EB"
    PRIMARY_HOVER = "#1D4ED8"
    ACCENT = "#3B82F6"
    SUCCESS = "#059669"
    SUCCESS_HOVER = "#047857"
    WARNING = "#F59E0B"
    WARNING_HOVER = "#D97706"
    DANGER = "#DC2626"
    DANGER_HOVER = "#B91C1C"
    INFO = "#0EA5E9"
    INFO_HOVER = "#0284C7"
    INDIGO = "#6366F1"
    INDIGO_HOVER = "#4F46E5"
    NEUTRAL = "#64748B"
    NEUTRAL_HOVER = "#475569"

    # Tipografía (selección según plataforma)
    if sys.platform == "darwin":
        FONT = "Helvetica Neue"
        FONT_MONO = "Menlo"
    elif os.name == "nt":
        FONT = "Segoe UI"
        FONT_MONO = "Cascadia Code"
    else:
        FONT = "Noto Sans"
        FONT_MONO = "DejaVu Sans Mono"
    FONT_HEADING = FONT

    S_H1 = (FONT_HEADING, 24, "bold")
    S_H2 = (FONT_HEADING, 20, "bold")
    S_H3 = (FONT_HEADING, 14, "bold")
    S_BODY = (FONT, 12)
    S_SMALL = (FONT, 10)

    # Radios / Espaciado
    R_SM = 8
    R_MD = 12
    R_LG = 16
    SPACE = 10

    @staticmethod
    def col(light: str, dark: str) -> tuple[str, str]:
        """Devuelve una tupla (light, dark) para usarla en widgets CTk."""
        return (light, dark)


def fade_in_window(window: Any, step: float = 0.07) -> None:
    """Fade-in sutil no bloqueante para ventanas Toplevel."""
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return
    try:
        window.focus_force()
    except tk.TclError:
        pass

    def _tick(alpha: float = 0.0) -> None:
        try:
            if not window.winfo_exists():
                return
            alpha = min(alpha + step, 1.0)
            window.attributes("-alpha", alpha)
            if alpha < 1.0:
                window.after(14, lambda: _tick(alpha))
        except tk.TclError:
            pass

    window.after(10, lambda: _tick(0.0))


def shake_window(window: Any, count: int = 0) -> None:
    """Animación de shake sutil (feedback en errores de validación)."""
    if count >= 6:
        return
    try:
        x = window.winfo_x()
        offset = 8 if count % 2 == 0 else -8
        window.geometry(f"+{x + offset}+{window.winfo_y()}")
        window.after(50, lambda: shake_window(window, count + 1))
    except tk.TclError:
        pass


class ModernDialog(ctk.CTkToplevel):
    """Diálogo modal con estética coherente; reemplaza al messagebox nativo."""

    def __init__(
        self,
        parent: Any,
        title: str,
        message: str,
        icon: str = "ℹ️",
        buttons: Iterable[str] = ("OK",),
        width: int = 420,
    ) -> None:
        if parent is not None:
            try:
                if not parent.winfo_exists():
                    parent = None
            except tk.TclError:
                parent = None
        try:
            super().__init__(parent)
        except tk.TclError:
            if parent is not None:
                try:
                    safe_destroy(self)
                except (AttributeError, tk.TclError):
                    pass
                parent = None
                super().__init__(None)
            else:
                raise
        self.result: Optional[str] = None
        self.title(title)
        self.width = width
        self.resizable(False, False)
        try:
            self.configure(fg_color=UI.CARD)
        except tk.TclError:
            pass
        self._build(title, message, icon, buttons)
        if parent is not None:
            self.transient(parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self._center(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))
        fade_in_window(self)
        self.bind("<Escape>", lambda e: self._finish(None))
        self.bind("<Return>", lambda e: self._finish(buttons[0] if buttons else None))

    def _build(self, title: str, message: str, icon: str, buttons: Iterable[str]) -> None:
        icon_color = UI.TEXT_MUTED
        if icon == "❌":
            icon_color = UI.DANGER
        elif icon == "⚠️":
            icon_color = UI.WARNING
        elif icon == "ℹ️":
            icon_color = UI.PRIMARY
        elif icon == "ⓘ":
            icon_color = UI.PRIMARY
        elif icon == "❓":
            icon_color = UI.INDIGO
        elif icon == "✅":
            icon_color = UI.SUCCESS

        ctk.CTkLabel(
            self, text=icon, font=(UI.FONT, 28), text_color=icon_color,
            anchor="center", justify="center"
        ).pack(fill="x", pady=(20, 4))
        ctk.CTkLabel(
            self, text=title, font=UI.S_H3, text_color=UI.TEXT,
            anchor="center", justify="center"
        ).pack(fill="x", padx=24)
        ctk.CTkLabel(
            self, text=message, wraplength=self.width - 60,
            font=UI.S_BODY, text_color=UI.TEXT_SECONDARY,
            justify="center", anchor="center"
        ).pack(padx=28, pady=(8, 4))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(14, 18))

        default_style = {"corner_radius": UI.R_SM, "height": 36, "font": (UI.FONT, 12, "bold")}
        for b in buttons:
            if b.lower() in ("ok", "sí", "aceptar", "guardar"):
                fg, hover = UI.PRIMARY, UI.PRIMARY_HOVER
            elif b.lower() in ("no", "cancelar"):
                fg, hover = UI.NEUTRAL, UI.NEUTRAL_HOVER
            else:
                fg, hover = UI.NEUTRAL, UI.NEUTRAL_HOVER
            ctk.CTkButton(
                btn_frame, text=b, width=110,
                fg_color=fg, hover_color=hover, **default_style,
                command=lambda rb=b: self._finish(rb)
            ).pack(side="left", padx=6)

    def _center(self, parent: Any) -> None:
        try:
            self.update_idletasks()
            w = self.width
            h = self.winfo_reqheight()
            if parent is not None and parent.winfo_exists():
                x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
                y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            else:
                x = (self.winfo_screenwidth() - w) // 2
                y = (self.winfo_screenheight() - h) // 2
            self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def _finish(self, result: Optional[str]) -> None:
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:
            pass
        safe_destroy(self)


class ModernMessageBox:
    """Reemplazo de messagebox con estética CTk (mismas firmas)."""

    @classmethod
    def _show(cls, kind: str, title: str, message: str, **kwargs: Any) -> Any:
        icons = {"info": "ⓘ", "warning": "⚠️", "error": "❌", "question": "❓", "success": "✅"}
        parent = kwargs.pop("parent", None)
        kwargs.pop("icon", None)
        buttons = ("Sí", "No") if kind == "question" else ("OK",)
        try:
            dlg = ModernDialog(
                parent, title, message,
                icon=icons.get(kind, "ℹ️"),
                buttons=buttons,
            )
        except tk.TclError:
            safe_destroy(parent)
            dlg = ModernDialog(
                None, title, message,
                icon=icons.get(kind, "ℹ️"),
                buttons=buttons,
            )
        try:
            if parent is not None and parent.winfo_exists():
                parent.wait_window(dlg)
            else:
                dlg.wait_window()
        except tk.TclError:
            pass
        if kind == "question":
            return dlg.result == "Sí"
        return dlg.result

    @classmethod
    def showinfo(cls, title: str, message: str, **kwargs: Any) -> Any:
        return cls._show("info", title, message, **kwargs)

    @classmethod
    def showwarning(cls, title: str, message: str, **kwargs: Any) -> Any:
        return cls._show("warning", title, message, **kwargs)

    @classmethod
    def showerror(cls, title: str, message: str, **kwargs: Any) -> Any:
        return cls._show("error", title, message, **kwargs)

    @classmethod
    def askyesno(cls, title: str, message: str, **kwargs: Any) -> Any:
        return cls._show("question", title, message, **kwargs)


class Toast:
    """Notificación no bloqueante tipo toast en la esquina superior derecha.

    Solo existe una a la vez: mostrar una nueva reemplaza a la anterior para no
    saturar la pantalla con avisos apilados.
    """

    _current: Optional["Toast"] = None

    def __init__(
        self,
        message: str,
        title: str = "Aviso",
        icon: str = "⚠️",
        duration: int = 6000,
        color: Tuple[str, str] = (UI.WARNING, "#B45309"),
        on_click: Optional[Any] = None,
    ) -> None:
        self.on_click = on_click
        self.window: Optional[ctk.CTkToplevel] = None

        Toast._dismiss_current()

        try:
            self.window = tk.Toplevel()
        except tk.TclError:
            return
        window = self.window
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)

        frame = ctk.CTkFrame(window, corner_radius=12, fg_color=UI.BG)
        frame.pack(padx=2, pady=2)
        frame.configure(border_width=1, border_color=color)
        frame.pack_propagate(False)

        icon_label = ctk.CTkLabel(frame, text=icon, font=(UI.FONT, 22), text_color=color[0])
        icon_label.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=10)

        ctk.CTkLabel(
            frame, text=title, font=(UI.FONT, 12, "bold"), text_color=color[0],
            anchor="w"
        ).grid(row=0, column=1, sticky="w", pady=(10, 0), padx=(0, 14))
        ctk.CTkLabel(
            frame, text=message, font=(UI.FONT, 11), text_color=UI.TEXT_SECONDARY,
            anchor="w", wraplength=360, justify="left"
        ).grid(row=1, column=1, sticky="w", padx=(0, 14), pady=(2, 10))

        close_btn = ctk.CTkButton(
            frame, text="✕", width=24, height=24, corner_radius=12,
            fg_color="transparent", hover_color=UI.SELECT_BG_T, text_color=UI.NEUTRAL,
            font=(UI.FONT, 11, "bold"), command=self.dismiss
        )
        close_btn.grid(row=0, column=2, rowspan=2, padx=(4, 8))

        frame.bind("<Button-1>", self._on_click)
        for child in [icon_label]:
            child.bind("<Button-1>", self._on_click)

        window.update_idletasks()
        width = frame.winfo_reqwidth()
        height = frame.winfo_reqheight()
        screen_w = window.winfo_screenwidth()
        x = screen_w - width - 20
        y = 40
        window.geometry(f"{width}x{height}+{x}+{y}")

        try:
            window.attributes("-alpha", 0.0)
        except tk.TclError:
            window.deiconify()
        else:
            window.deiconify()
            self._fade(0.0, 1.0)

        Toast._current = self
        try:
            window.after(duration, self.dismiss)
        except tk.TclError:
            pass

    def _fade(self, alpha: float, target: float, step: float = 0.12) -> None:
        window = self.window
        if window is None:
            return
        try:
            if not window.winfo_exists():
                return
            alpha = min(alpha + step, target)
            window.attributes("-alpha", alpha)
            if alpha < target:
                window.after(16, lambda: self._fade(alpha, target))
        except tk.TclError:
            pass

    def _on_click(self, event: Any = None) -> None:
        self.dismiss()
        if self.on_click is not None:
            try:
                self.on_click()
            except Exception:
                pass

    def dismiss(self) -> None:
        if Toast._current is self:
            Toast._current = None
        window = self.window
        self.window = None
        if window is None:
            return
        def _close() -> None:
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass
        try:
            window.after(140, _close)
        except tk.TclError:
            _close()

    @staticmethod
    def _dismiss_current() -> None:
        current = Toast._current
        Toast._current = None
        if current is None:
            return
        window = current.window
        current.window = None
        current.on_click = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass


class PDFPreviewDialog(ctk.CTkToplevel):
    """Vista previa antes de guardar: permite revisar el PDF o guardarlo."""

    def __init__(
        self,
        parent: Any,
        temp_path: str,
        final_path: str,
        label: str = "PDF",
    ) -> None:
        super().__init__(parent)
        self.result: Optional[str] = None
        self.title(f"Vista previa — {label}")
        self.resizable(False, False)
        try:
            self.configure(fg_color=UI.CARD)
        except tk.TclError:
            pass
        try:
            self.transient(parent)
        except tk.TclError:
            pass
        try:
            self.grab_set()
        except tk.TclError:
            pass

        size_kb = 0
        if os.path.exists(temp_path):
            size_kb = int(os.path.getsize(temp_path) // 1024)

        ctk.CTkLabel(
            self, text="👁", font=(UI.FONT, 30), text_color=UI.INFO
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            self, text="Vista previa generada", font=UI.S_H3, text_color=UI.TEXT
        ).pack(fill="x", padx=24)
        ctk.CTkLabel(
            self,
            text=(f"El documento «{label}» se generó correctamente "
                  f"({size_kb} KB). Revise la maquetación antes de guardar."),
            wraplength=380, font=UI.S_BODY, text_color=UI.TEXT_SECONDARY,
            justify="center"
        ).pack(padx=28, pady=(8, 4), fill="x")

        info_frame = ctk.CTkFrame(self, fg_color=UI.SELECT_BG_T, corner_radius=10)
        info_frame.pack(fill="x", padx=30, pady=(6, 4))
        ctk.CTkLabel(
            info_frame, text=f"Destino:\n{os.path.basename(final_path)}",
            font=(UI.FONT, 10), text_color=UI.TEXT_SECONDARY, justify="center", wraplength=380
        ).pack(pady=8, padx=10)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(14, 18))

        choices = [
            ("👁 Abrir y revisar", UI.INFO, UI.INFO_HOVER, "review"),
            ("💾 Guardar PDF", UI.PRIMARY, UI.PRIMARY_HOVER, "save"),
            ("Cancelar", UI.NEUTRAL, UI.NEUTRAL_HOVER, None),
        ]
        for text, fg, hover, result in choices:
            ctk.CTkButton(
                btn_frame, text=text, width=140, height=36,
                corner_radius=UI.R_SM, font=(UI.FONT, 12, "bold"),
                fg_color=fg, hover_color=hover,
                command=lambda r=result: self._finish(r, temp_path)
            ).pack(side="left", padx=5)

        self._center(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None, temp_path))
        self.bind("<Escape>", lambda e: self._finish(None, temp_path))
        fade_in_window(self)

    def _center(self, parent: Any) -> None:
        try:
            self.update_idletasks()
            w = 460
            h = self.winfo_reqheight()
            if parent is not None and parent.winfo_exists():
                x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
                y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            else:
                x = (self.winfo_screenwidth() - w) // 2
                y = (self.winfo_screenheight() - h) // 2
            self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def _finish(self, result: Optional[str], temp_path: str) -> None:
        if result == "review" and temp_path:
            try:
                open_path(temp_path)
                return
            except Exception:
                pass
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:
            pass
        safe_destroy(self)
