"""Kit de herramientas UI reutilizables para AS Facturation.

Contiene helpers independientes de la UI principal:
debounce, tooltips, feedback de pulsación (pulse), indicadores de carga
skeleton/shimmer, historial de búsquedas, validación inline, pista de atajos,
persistencia de geometría de ventana y escala de interfaz.

Este módulo NO importa ``Main`` para evitar dependencias circulares.
"""

import json
import os
import tkinter as tk
import customtkinter as ctk
import db

SEARCH_HISTORY_FILE = "search_history.json"
MAX_HISTORY = 10
SEARCH_DEBOUNCE_MS = 300


def _project_path(*parts):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


# =============================================================================
# Debounce
# =============================================================================
class DelayedCall:
    """Programa una llamada después de un retardo, cancelando la anterior."""

    def __init__(self, root=None):
        self.root = root
        self._after_id = None

    def _target(self):
        if self.root is not None:
            try:
                if self.root.winfo_exists():
                    return self.root
            except Exception:
                pass
        r = tk._default_root
        return r if r is not None else self.root

    def schedule(self, ms, fn):
        self.cancel()
        target = self._target()
        if target is None:
            try:
                fn()
            except Exception:
                pass
            return
        try:
            self._after_id = target.after(ms, lambda: self._run(fn))
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _run(self, fn):
        self._after_id = None
        try:
            fn()
        except Exception:
            pass

    def cancel(self):
        if self._after_id is not None:
            try:
                target = self._target()
                if target is not None:
                    target.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None


def debounced(root):
    """Crea una instancia de DelayedCall ligada a la raíz indicada."""
    return DelayedCall(root)


# =============================================================================
# Tooltip
# =============================================================================
class ToolTip:
    """Tooltip moderno (CTk) que aparece tras un pequeño retardo."""

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id = None
        self.tip_window = None
        try:
            self._enter_bind = widget.bind("<Enter>", self._schedule, add="+")
            self._leave_bind = widget.bind("<Leave>", self._hide, add="+")
            self._motion_bind = widget.bind("<Motion>", self._hide, add="+")
        except Exception:
            pass

    def _schedule(self, event=None):
        try:
            self._cancel_after()
            self._after_id = self.widget.after(self.delay, self._show)
        except Exception:
            pass

    def _cancel_after(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        try:
            if not self.widget.winfo_exists():
                return
            self._hide()
            x = self.widget.winfo_rootx() + 24
            y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2 + 12

            tip = tk.Toplevel(self.widget)
            tip.withdraw()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{int(x)}+{int(y)}")

            frame = ctk.CTkFrame(
                tip,
                corner_radius=8,
                border_width=1,
                border_color=("#CBD5E1", "#334155"),
                fg_color=("#1E293B", "#F8FAFC"),
            )
            frame.pack(fill="both", expand=True)

            label = ctk.CTkLabel(
                frame,
                text=self.text,
                font=("Segoe UI", 11),
                text_color=("#F8FAFC", "#1E293B"),
                justify="left",
                wraplength=280,
            )
            label.pack(padx=10, pady=6)
            tip.deiconify()
            self.tip_window = tip
        except Exception:
            pass

    def _hide(self, event=None):
        self._cancel_after()
        if self.tip_window is not None:
            try:
                if self.tip_window.winfo_exists():
                    self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


def bind_tooltip(widget, text, delay=500):
    """Crea y devuelve un ToolTip para un widget dado."""
    try:
        return ToolTip(widget, text, delay=delay)
    except Exception:
        return None


# =============================================================================
# Feedback visual sutil (pulse / ripple simplificado)
# =============================================================================
class _PulseState:
    def __init__(self):
        self.installed = False


_PULSE = _PulseState()


def install_pulse(root):
    """Instala un efecto de feedback sutil sobre todos los CTkButton.

    Al presionar el botón se muestra su color de hover; al soltar se restaura
    el color original. Es idempotente para la raíz indicada.
    """
    if _PULSE.installed:
        return
    try:
        _PULSE.installed = True
    except Exception:
        pass

    def _on_press(event):
        w = event.widget
        if not isinstance(w, ctk.CTkButton):
            return
        try:
            if not hasattr(w, "_pulse_original"):
                w._pulse_original = w.cget("fg_color")
            hover = w.cget("hover_color")
            if hover:
                w.configure(fg_color=hover)
        except Exception:
            pass

    def _on_release(event):
        w = event.widget
        if not isinstance(w, ctk.CTkButton):
            return
        try:
            if hasattr(w, "_pulse_original"):
                w.configure(fg_color=w._pulse_original)
                del w._pulse_original
        except Exception:
            pass

    try:
        root.bind_all("<ButtonPress-1>", _on_press, add="+")
        root.bind_all("<ButtonRelease-1>", _on_release, add="+")
    except Exception:
        pass


# =============================================================================
# Skeleton / shimmer
# =============================================================================
class SkeletonShimmer:
    """Overlay de carga con efecto de brillo animado sobre un widget padre."""

    def __init__(self, parent, bg=("#FFFFFF", "#1E293B")):
        self.parent = parent
        self.bg = bg
        self.canvas = None
        self._after_id = None
        self._offset = 0

    def show(self):
        try:
            if self.canvas is not None:
                return
            parent = self.parent
            if parent is None or not parent.winfo_exists():
                return
            bg = self.bg
            if isinstance(bg, (tuple, list)):
                bg = bg[0] if ctk.get_appearance_mode() == "Light" else bg[1]
            canvas = tk.Canvas(
                parent,
                highlightthickness=0,
                bg=bg,
                borderwidth=0,
            )
            canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.canvas = canvas
            self._draw_bars()
            self._animate()
        except Exception:
            pass

    def _draw_bars(self):
        try:
            c = self.canvas
            if c is None:
                return
            c.delete("skeleton")
            w = c.winfo_width() or self.parent.winfo_width() or 500
            h = c.winfo_height() or self.parent.winfo_height() or 300
            base = "#E2E8F0"
            bw = int(w * 0.6)
            bx = max(10, (w - bw) // 2)
            bars = [
                (bx, int(h * 0.12), int(bw * 0.4), 22),   # título
                (bx, int(h * 0.30), int(bw * 0.9), 14),   # fila 1
                (bx, int(h * 0.34), int(bw * 0.9), 14),   # fila 2
                (bx, int(h * 0.38), int(bw * 0.9), 14),   # fila 3
                (bx, int(h * 0.55), int(bw * 0.7), 120),  # gráfico
                (bx, int(h * 0.90), int(bw * 0.5), 16),   # pie
            ]
            for x, y, rw, rh in bars:
                c.create_rectangle(x, y, x + rw, y + rh, fill=base, outline="", tags="skeleton")
        except Exception:
            pass

    def _animate(self):
        if self.canvas is None:
            return
        try:
            c = self.canvas
            c.delete("shimmer")
            w = c.winfo_width() or 500
            h = c.winfo_height() or 300
            self._offset = (self._offset + 10) % (w + 240)
            x0 = self._offset - 140
            x1 = self._offset + 40
            c.create_rectangle(
                x0, 0, x1, h,
                fill="#F8FAFC",
                outline="",
                stipple="gray50",
                tags="shimmer",
            )
            self._after_id = c.after(30, self._animate)
        except Exception:
            pass

    def hide(self):
        if self._after_id is not None:
            try:
                if self.canvas is not None:
                    self.canvas.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self.canvas is not None:
            try:
                if self.canvas.winfo_exists():
                    self.canvas.destroy()
            except Exception:
                pass
            self.canvas = None


# =============================================================================
# Historial de búsqueda
# =============================================================================
def load_search_history(limit=MAX_HISTORY):
    path = _project_path(SEARCH_HISTORY_FILE)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x).strip() for x in data[:limit] if str(x).strip()]
    except Exception:
        pass
    return []


def save_search_history(terms, limit=MAX_HISTORY):
    path = _project_path(SEARCH_HISTORY_FILE)
    try:
        cleaned = []
        for t in terms:
            t = str(t).strip()
            if t and t not in cleaned:
                cleaned.append(t)
        cleaned = cleaned[:limit]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def add_search_term(term, limit=MAX_HISTORY):
    term = str(term).strip()
    if not term:
        return
    terms = load_search_history(limit=limit)
    if term in terms:
        terms.remove(term)
    terms.insert(0, term)
    save_search_history(terms, limit=limit)


class SearchSuggestionPopup:
    """Popup de sugerencias basado en el historial, al enfocar un Entry."""

    def __init__(self, entry, on_select=None, max_items=6):
        self.entry = entry
        self.on_select = on_select
        self.max_items = max_items
        self._pop = None
        self._listbox = None
        self._focus_out_id = None
        try:
            self._focus_bind = entry.bind("<FocusIn>", self._maybe_show, add="+")
            self._ctrl_bind = entry.bind("<Control-Return>", lambda e: self.toggle(), add="+")
        except Exception:
            pass

    def _maybe_show(self, event=None):
        try:
            if not self.entry.winfo_exists():
                return
            if self.entry.get():
                return
            terms = load_search_history(limit=self.max_items)
            if not terms:
                return
            self._show(terms)
        except Exception:
            pass

    def toggle(self):
        if self._pop is not None:
            self.dismiss()
        else:
            self._maybe_show()

    def _show(self, terms):
        self.dismiss()
        try:
            top = self.entry.winfo_toplevel()
            pop = ctk.CTkToplevel(top)
            pop.overrideredirect(True)
            try:
                pop.attributes("-topmost", True)
            except Exception:
                pass
            try:
                pop.transient(top)
            except Exception:
                pass
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
            pop.geometry(f"+{int(x)}+{int(y)}")

            frame = ctk.CTkFrame(
                pop,
                corner_radius=8,
                border_width=1,
                border_color=("#CBD5E1", "#334155"),
                fg_color=("#FFFFFF", "#1E293B"),
            )
            frame.pack(fill="both", expand=True)

            bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
            fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
            listbox = tk.Listbox(
                frame,
                height=min(len(terms), self.max_items),
                bg=bg,
                fg=fg,
                selectbackground="#2563EB",
                selectforeground="#FFFFFF",
                activestyle="none",
                highlightthickness=0,
                borderwidth=0,
                font=("Segoe UI", 11),
            )
            listbox.pack(fill="both", expand=True, padx=4, pady=4)
            for t in terms:
                listbox.insert(tk.END, t)

            self._pop = pop
            self._listbox = listbox
            listbox.bind("<ButtonRelease-1>", self._on_click)
            listbox.bind("<Escape>", lambda e: self.dismiss())

            def _on_focus_out(event=None):
                if self._pop is not None:
                    self._pop.after(150, self.dismiss)

            try:
                self._focus_out_id = self.entry.bind("<FocusOut>", _on_focus_out, add="+")
            except Exception:
                pass
        except Exception:
            pass

    def _on_click(self, event=None):
        if self._listbox is None:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        self._apply(self._listbox.get(sel[0]))

    def _apply(self, term):
        try:
            self.entry.delete(0, "end")
            self.entry.insert(0, term)
            self.entry.icursor(tk.END)
        except Exception:
            pass
        add_search_term(term)
        self.dismiss()
        try:
            self.entry.focus_force()
        except Exception:
            pass
        if self.on_select is not None:
            try:
                self.on_select(term)
            except Exception:
                pass

    def dismiss(self):
        if self._pop is not None:
            try:
                if self._pop.winfo_exists():
                    self._pop.destroy()
            except Exception:
                pass
            self._pop = None
        self._listbox = None
        try:
            if self._focus_out_id:
                self.entry.unbind("<FocusOut>", self._focus_out_id)
                self._focus_out_id = None
        except Exception:
            pass


# =============================================================================
# Validación inline
# =============================================================================
def mark_invalid(entry, error_label, message, danger=("#DC2626", "#F87171")):
    """Marca un campo como inválido (borde rojo) y muestra un mensaje bajo él."""
    try:
        border = danger[0] if isinstance(danger, (tuple, list)) and ctk.get_appearance_mode() == "Light" else (danger[1] if isinstance(danger, (tuple, list)) else danger)
        if isinstance(entry, ctk.CTkEntry):
            entry.configure(border_color=border, border_width=2)
        elif isinstance(entry, ctk.CTkComboBox):
            try:
                entry.configure(border_color=border, border_width=2)
            except Exception:
                pass
    except Exception:
        pass
    if error_label is not None:
        try:
            if isinstance(danger, (tuple, list)):
                err_color = danger[0] if ctk.get_appearance_mode() == "Light" else danger[1]
            else:
                err_color = danger
            error_label.configure(text=message, text_color=err_color, font=("Segoe UI", 10))
            manager = "none"
            try:
                manager = error_label.winfo_manager()
            except Exception:
                manager = ""
            if manager in ("", "none"):
                try:
                    error_label.pack(fill="x", padx=20, pady=(2, 0), anchor="w")
                except Exception:
                    pass
        except Exception:
            pass
    try:
        entry.focus_force()
    except Exception:
        pass


def clear_invalid(entry, error_label, border=("#E2E8F0", "#334155")):
    try:
        b = border[0] if isinstance(border, (tuple, list)) and ctk.get_appearance_mode() == "Light" else (border[1] if isinstance(border, (tuple, list)) else border)
        if isinstance(entry, ctk.CTkEntry):
            entry.configure(border_color=b, border_width=1)
        elif isinstance(entry, ctk.CTkComboBox):
            try:
                entry.configure(border_color=b, border_width=1)
            except Exception:
                pass
    except Exception:
        pass
    if error_label is not None:
        try:
            error_label.configure(text="")
            manager = "none"
            try:
                manager = error_label.winfo_manager()
            except Exception:
                manager = ""
            if manager in ("", "none"):
                try:
                    error_label.pack_forget()
                except Exception:
                    pass
        except Exception:
            pass


def attach_inline_validation(entry, error_label):
    """Limpia el estado de error automáticamente al escribir en el campo."""
    def _clear(event=None):
        clear_invalid(entry, error_label)
    try:
        entry.bind("<KeyRelease>", _clear, add="+")
    except Exception:
        pass
    return _clear


# =============================================================================
# Pista de atajos de teclado (primer inicio)
# =============================================================================
SHORTCUT_HINTS = [
    ("Ctrl + Tab", "Cambiar a la siguiente pestaña"),
    ("Ctrl + Shift + Tab", "Cambiar a la pestaña anterior"),
    ("Ctrl + 1 … 6", "Ir directo a una pestaña"),
    ("Ctrl + F", "Buscar en la pestaña activa"),
    ("Ctrl + N", "Nuevo registro (según la pestaña)"),
    ("Ctrl + P", "Procesar pago o imprimir factura"),
    ("F5", "Refrescar todas las vistas"),
    ("Escape", "Cerrar diálogo o limpiar selección"),
]


class ShortcutHintDialog(ctk.CTkToplevel):
    """Diálogo modal que muestra los atajos de teclado del sistema."""

    def __init__(self, parent, mark_shown=True):
        super().__init__(parent)
        self.title("Atajos de teclado")
        self.resizable(False, False)
        try:
            self.configure(fg_color=("#FFFFFF", "#1E293B"))
        except Exception:
            pass
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass

        w, h = 460, 470
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(
            self,
            text="⌨️ Atajos de teclado",
            font=("Segoe UI", 18, "bold"),
            text_color=("#1E293B", "#F8FAFC"),
        ).pack(pady=(22, 6))
        ctk.CTkLabel(
            self,
            text="Agiliza tu trabajo con estos atajos:",
            font=("Segoe UI", 11),
            text_color=("#64748B", "#94A3B8"),
        ).pack(pady=(0, 14))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=30, fill="both", expand=True)

        for key, desc in SHORTCUT_HINTS:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            key_lbl = ctk.CTkLabel(
                row,
                text=key,
                font=("Segoe UI", 11, "bold"),
                width=150,
                anchor="w",
                fg_color=("#F1F5F9", "#334155"),
                corner_radius=6,
                text_color=("#475569", "#CBD5E1"),
            )
            key_lbl.pack(side="left", fill="y")
            ctk.CTkLabel(
                row,
                text=desc,
                font=("Segoe UI", 11),
                anchor="w",
                text_color=("#1E293B", "#F8FAFC"),
            ).pack(side="left", padx=(12, 0))

        def close():
            if mark_shown:
                try:
                    db.set_config("shortcut_hints_shown", "1")
                except Exception:
                    pass
            try:
                self.destroy()
            except Exception:
                pass

        ctk.CTkButton(
            self,
            text="Entendido",
            command=close,
            width=140,
            height=38,
            corner_radius=8,
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB"),
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(8, 20))

        self.bind("<Return>", lambda e: close())
        self.bind("<Escape>", lambda e: close())
        self.protocol("WM_DELETE_WINDOW", close)


def show_shortcut_hints_if_needed(parent):
    """Muestra la pista de atajos solo la primera vez que inicia sesión."""
    try:
        if db.get_config("shortcut_hints_shown", "0") == "1":
            return None
    except Exception:
        return None
    try:
        dlg = ShortcutHintDialog(parent)
        return dlg
    except Exception:
        return None


# =============================================================================
# Geometría y estado de ventana
# =============================================================================
def save_window_state(geom, state="normal"):
    try:
        db.set_config("window_geometry", geom or "")
        db.set_config("window_state", state or "normal")
    except Exception:
        pass


def load_window_state():
    try:
        geom = db.get_config("window_geometry", "")
        state = db.get_config("window_state", "normal")
        return geom, state
    except Exception:
        return "", "normal"


# =============================================================================
# Escala de interfaz
# =============================================================================
SCALE_OPTIONS = ["100%", "125%", "150%"]


def normalize_ui_scaling(value):
    """Normaliza la escala a un valor válido y seguro, por defecto 100%."""
    if value is None:
        return "100%"

    text = str(value).strip()
    if not text:
        return "100%"

    # Acepta "100%", "125%", "150%" y factores numéricos (1.0, 1.25, etc.)
    text = text.replace("%", "").strip()
    try:
        numeric = float(text)
    except ValueError:
        return "100%"

    if numeric <= 0:
        return "100%"

    if 0.8 <= numeric <= 2.0:
        percent = round(numeric * 100)
        if 80 <= percent <= 200:
            return f"{int(percent)}%"

    normalized = round(numeric)
    if normalized in (100, 125, 150):
        return f"{int(normalized)}%"

    return "100%"


def scale_value_to_factor(value):
    try:
        parsed = normalize_ui_scaling(value)
        return float(parsed.replace("%", "").strip()) / 100.0
    except Exception:
        return 1.0


def save_ui_scaling(value):
    try:
        db.set_config("ui_scale", normalize_ui_scaling(value))
    except Exception:
        pass


def current_ui_scaling():
    try:
        value = db.get_config("ui_scale", "100%")
        return normalize_ui_scaling(value)
    except Exception:
        return "100%"


def apply_ui_scaling():
    """Aplica la escala de interfaz guardada. Debe llamarse antes de crear la UI."""
    try:
        value = current_ui_scaling()
        save_ui_scaling(value)
        factor = scale_value_to_factor(value)
        factor = max(0.8, min(2.0, factor))
        ctk.set_widget_scaling(factor)
        ctk.set_window_scaling(factor)
        return factor
    except Exception:
        return 1.0