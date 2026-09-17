import re
import tkinter as tk
from tkinter import messagebox, ttk
import tkinter.simpledialog as simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk
from datetime import datetime, timedelta
import json
import os
import db
import signal
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from xml.sax.saxutils import escape


try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


def safe_destroy(widget):
    """Destruye de forma segura un widget Tkinter/CTk si existe, ignorando TclError."""
    try:
        if widget is None:
            return
        exists = False
        try:
            exists = bool(widget.winfo_exists())
        except Exception:
            # algunos objetos pueden no exponer winfo_exists
            exists = True
        if exists:
            try:
                widget.destroy()
            except tk.TclError:
                pass
            except Exception:
                try:
                    widget.destroy()
                except Exception:
                    pass
    except Exception:
        pass


def safe_widget_insert(widget, index, text):
    """Insertar texto de forma segura en widgets Entry/Text/CtkEntry.
    Convierte None a cadena vacía y captura errores de Tcl.
    """
    try:
        s = "" if text is None else str(text)
        try:
            widget.insert(index, s)
        except Exception:
            # Algunos widgets esperan índices diferentes; intentar sin índice
            try:
                widget.insert(s)
            except Exception:
                try:
                    # como último recurso, escribir mediante configure/state si aplica
                    widget.configure(state="normal")
                    widget.delete(0, "end")
                    widget.insert(0, s)
                except Exception:
                    pass
    except Exception:
        pass

def toggle_password_visibility(entry, button):
    """Alternar visibilidad de la contraseña en un CTkEntry"""
    if entry.cget("show") == "*":
        entry.configure(show="")
        button.configure(text="👁️") # Ojo abierto: Ver
    else:
        entry.configure(show="*")
        button.configure(text="🔒") # Candado/Ojo tachado: Ocultar

def format_ci_rif(value):
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

# Configuración Inicial de CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("dark-blue")

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

    # Tipografía
    FONT = "Segoe UI"
    FONT_HEADING = "Segoe UI"
    FONT_MONO = "Cascadia Code"

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


def fade_in_window(window, step=0.07):
    """Fade-in sutil no bloqueante para ventanas Toplevel."""
    try:
        window.attributes("-alpha", 0.0)
    except Exception:
        return
    try:
        window.focus_force()
    except Exception:
        pass

    def _tick(alpha=0.0):
        try:
            if not window.winfo_exists():
                return
            alpha = min(alpha + step, 1.0)
            window.attributes("-alpha", alpha)
            if alpha < 1.0:
                window.after(14, lambda: _tick(alpha))
        except Exception:
            pass

    window.after(10, lambda: _tick(0.0))


def shake_window(window, count=0):
    """Animación de shake sutil (feedback en errores de validación)."""
    if count >= 6:
        return
    try:
        x = window.winfo_x()
        offset = 8 if count % 2 == 0 else -8
        window.geometry(f"+{x + offset}+{window.winfo_y()}")
        window.after(50, lambda: shake_window(window, count + 1))
    except Exception:
        pass


class ModernDialog(ctk.CTkToplevel):
    """Diálogo modal con estética coherente; reemplaza al messagebox nativo."""

    def __init__(self, parent, title, message, icon="ℹ️", buttons=("OK",), width=420):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.width = width
        self.resizable(False, False)
        try:
            self.configure(fg_color=UI.CARD)
        except Exception:
            pass
        self._build(title, message, icon, buttons)
        if parent is not None:
            self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass
        self._center(parent)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))
        fade_in_window(self)
        self.bind("<Escape>", lambda e: self._finish(None))
        self.bind("<Return>", lambda e: self._finish(buttons[0] if buttons else None))

    def _build(self, title, message, icon, buttons):
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

    def _center(self, parent):
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
        except Exception:
            pass

    def _finish(self, result):
        self.result = result
        try:
            self.grab_release()
        except Exception:
            pass
        safe_destroy(self)


class ModernMessageBox:
    """Reemplazo de messagebox con estética CTk (mismas firmas)."""

    @classmethod
    def _show(cls, kind, title, message, **kwargs):
        icons = {"info": "ⓘ", "warning": "⚠️", "error": "❌", "question": "❓", "success": "✅"}
        parent = kwargs.pop("parent", None)
        kwargs.pop("icon", None)
        dlg = ModernDialog(
            parent, title, message,
            icon=icons.get(kind, "ℹ️"),
            buttons=("Sí", "No") if kind == "question" else ("OK",)
        )
        try:
            if parent is not None and parent.winfo_exists():
                parent.wait_window(dlg)
            else:
                dlg.wait_window()
        except Exception:
            pass
        if kind == "question":
            return dlg.result == "Sí"
        return dlg.result

    @classmethod
    def showinfo(cls, title, message, **kwargs):
        return cls._show("info", title, message, **kwargs)

    @classmethod
    def showwarning(cls, title, message, **kwargs):
        return cls._show("warning", title, message, **kwargs)

    @classmethod
    def showerror(cls, title, message, **kwargs):
        return cls._show("error", title, message, **kwargs)

    @classmethod
    def askyesno(cls, title, message, **kwargs):
        return cls._show("question", title, message, **kwargs)


class BillingSystem(ctk.CTkToplevel):
    def __init__(self, master=None, user_role="admin"):
        super().__init__(master=master)
        self.user_role = user_role
        self.title(f"Sistema de Facturación AS — v3.3 ({'Administrador' if user_role == 'admin' else 'Empleado'})")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # Iniciar maximizado
        self.after(0, lambda: self.state('zoomed'))

        # Variables de estado
        self.include_pending_in_dashboard = True
        self.ttk_style = ttk.Style()
        self.configure_ttk_styles()
        self.products = []
        self.clients = []
        self.invoices = []
        self.current_invoice_items = []
        self.invoice_counter = 1000
        self.iva_rate = 0.16  # IVA configurable
        self.exchange_rate = 350.0  # Tasa de cambio USD a BS configurable
        self.auto_update_rate = False
        self.rate_source = "oficial"
        self.company_name = "SISTEMA DE FACTURACIÓN AS"
        self.company_rif = "RIF: N/A"
        self.company_address = "Domicilio fiscal: N/A"
        self.company_phone = "Teléfono: N/A"
        
        # Inicializar base de datos
        db.init_db()
        
        # Cargar datos guardados
        self.load_data()

        # Iniciar ciclo de auto-actualización
        self.start_auto_update_loop()

        # Vincular F5 para refrescar
        self.bind("<F5>", lambda e: self.refresh_all_views())

        # Configurar signal handler para guardar datos al cerrar abruptamente
        def signal_handler(sig, frame):
            self.save_data()
            self.quit()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Configurar iconos
        self.setup_icons()
        
        # Cargar logo
        self.load_main_logo()

        # --- Frame Superior (Barra de Herramientas) ---
        self.create_top_bar()

        # --- Pestañas Principales ---
        self.tab_control = ttk.Notebook(self)
        
        # Crear pestañas
        self.tab_point_of_sale = ctk.CTkFrame(self.tab_control)
        self.tab_inventory = ctk.CTkFrame(self.tab_control)
        self.tab_clients = ctk.CTkFrame(self.tab_control)
        self.tab_invoices = ctk.CTkFrame(self.tab_control)
        self.tab_reports = ctk.CTkFrame(self.tab_control)

        self.tab_control.add(self.tab_point_of_sale, text="🏪 Punto de Venta")
        self.tab_control.add(self.tab_inventory, text="📦 Inventario")
        self.tab_control.add(self.tab_clients, text="👥 Clientes")
        self.tab_control.add(self.tab_invoices, text="📄 Facturas")
        self.tab_control.add(self.tab_reports, text="📊 Reportes")
        
        if self.user_role == "admin":
            self.tab_users = ctk.CTkFrame(self.tab_control)
            self.tab_control.add(self.tab_users, text="👥 Usuarios")

        self.tab_control.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self.bind("<Configure>", self.on_window_resize)
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Inicializar contenido de pestañas
        self.create_point_of_sale_tab()
        self.create_inventory_tab()
        self.create_clients_tab()
        self.create_invoices_tab()
        self.create_reports_tab()
        if self.user_role == "admin":
            self.create_users_tab()

        # Actualizar contadores
        self.update_counters()

        # Aplicar permisos según el rol
        self.apply_permissions()

        # Configurar atajos de teclado globales
        self.setup_keyboard_shortcuts()

        # Configurar cierre de ventana
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Animación sutil de fade-in al abrir
        self.attributes("-alpha", 0.0)
        self._fade_in()

    def apply_permissions(self):
        """Aplicar restricciones basadas en el rol del usuario"""
        if self.user_role == "empleado":
            def disable_restricted_buttons(parent):
                for widget in parent.winfo_children():
                    if isinstance(widget, ctk.CTkButton):
                        text = widget.cget("text")
                        if any(x in text for x in ["Nuevo Producto", "Editar", "Eliminar Factura", "Cancelar Factura"]):
                            widget.configure(state="disabled", fg_color="#94A3B8")
                        # Caso especial para "Eliminar" genérico en inventario
                        elif text == f"{self.icons['delete']} Eliminar":
                            widget.configure(state="disabled", fg_color="#94A3B8")
                    elif isinstance(widget, (ctk.CTkFrame, tk.Frame)):
                        disable_restricted_buttons(widget)

            # Escanear pestañas restringidas
            disable_restricted_buttons(self.tab_inventory)
            disable_restricted_buttons(self.tab_clients)
            disable_restricted_buttons(self.tab_invoices)
            
            # Quitar opciones del menú contextual de inventario
            try:
                self.inventory_menu.entryconfigure(" Editar", state="disabled")
                self.inventory_menu.entryconfigure(" Eliminar", state="disabled")
            except Exception as e: print(f"DEBUG: Error menu inventario: {e}")

            # Quitar opción "Eliminar" del menú contextual de facturas
            try:
                self.invoices_menu.entryconfigure(" Eliminar", state="disabled")
            except Exception as e: print(f"DEBUG: Error menu facturas: {e}")

            # El rol de empleado SI puede facturar, ver detalles, e interactuar con clientes (permisos totales en clientes)
            print("INFO: Aplicados permisos restrictivos para rol EMPLEADO")
        else:
            print("INFO: Sesión iniciada como ADMINISTRADOR")

    def _require_admin(self, action):
        """Evitar que un empleado ejecute una operación restringida por otro medio."""
        if self.user_role == "admin":
            return True
        ModernMessageBox.showwarning(
            "Permiso insuficiente",
            f"Solo el administrador puede {action}."
        )
        return False

    def _fade_in(self, alpha=0.0):
        """Animación de fade-in sutil"""
        if alpha < 1.0:
            alpha = min(alpha + 0.06, 1.0)
            try:
                self.attributes("-alpha", alpha)
            except Exception:
                return
            self.after(16, lambda: self._fade_in(alpha))

    def _on_tab_changed(self, event=None):
        """Microinteracción: pulso sutil de opacidad al navegar entre pestañas."""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            self.attributes("-alpha", 0.94)

            def _restore(step=0):
                if step >= 6:
                    self.attributes("-alpha", 1.0)
                    return
                try:
                    self.attributes("-alpha", 0.94 + step * 0.01)
                except Exception:
                    return
                self.after(12, lambda: _restore(step + 1))

            _restore()
        except Exception:
            pass

    def setup_keyboard_shortcuts(self):
        """Configurar atajos de teclado globales del sistema"""
        # Navegación entre pestañas (Ctrl + Tab, Ctrl + Shift + Tab, Ctrl + RePág / AvPág)
        self.bind_all("<Control-Tab>", self.switch_tab_next)
        self.bind_all("<Control-Shift-Tab>", self.switch_tab_prev)
        self.bind_all("<Control-ISO_Left_Tab>", self.switch_tab_prev)
        self.bind_all("<Control-Prior>", self.switch_tab_prev)
        self.bind_all("<Control-Next>", self.switch_tab_next)

        # Acceso directo por número de pestaña (Ctrl + 1..6)
        for i in range(1, 7):
            self.bind_all(f"<Control-Key-{i}>", lambda e, idx=i-1: self.switch_tab_index(idx))

        # Atajos de búsqueda, nuevo registro, pago/impresión y escape
        self.bind_all("<Control-f>", self.focus_search_shortcut)
        self.bind_all("<Control-F>", self.focus_search_shortcut)
        self.bind_all("<Control-n>", self.new_record_shortcut)
        self.bind_all("<Control-N>", self.new_record_shortcut)
        self.bind_all("<Control-p>", self.print_or_pay_shortcut)
        self.bind_all("<Control-P>", self.print_or_pay_shortcut)
        self.bind_all("<Escape>", self.on_escape_shortcut)

    def _is_child_dialog_focused(self):
        """Verifica si el foco actual está en una ventana modal o diálogo secundario"""
        try:
            focused = self.focus_get()
            if focused is not None:
                top = focused.winfo_toplevel()
                if top != self:
                    return True, top
        except Exception:
            pass
        return False, None

    def switch_tab_next(self, event=None):
        """Cambiar a la siguiente pestaña con Ctrl+Tab"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            tabs = self.tab_control.tabs()
            if not tabs:
                return "break"
            curr = self.tab_control.index(self.tab_control.select())
            nxt = (curr + 1) % len(tabs)
            self.tab_control.select(nxt)
        except Exception as e:
            print(f"DEBUG: Error cambiando a pestaña siguiente: {e}")
        return "break"

    def switch_tab_prev(self, event=None):
        """Cambiar a la pestaña anterior con Ctrl+Shift+Tab"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            tabs = self.tab_control.tabs()
            if not tabs:
                return "break"
            curr = self.tab_control.index(self.tab_control.select())
            prv = (curr - 1) % len(tabs)
            self.tab_control.select(prv)
        except Exception as e:
            print(f"DEBUG: Error cambiando a pestaña previa: {e}")
        return "break"

    def switch_tab_index(self, index, event=None):
        """Saltar directamente a una pestaña por su índice numérico (Ctrl+1, Ctrl+2, etc.)"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            tabs = self.tab_control.tabs()
            if 0 <= index < len(tabs):
                self.tab_control.select(index)
        except Exception as e:
            print(f"DEBUG: Error saltando a pestaña {index}: {e}")
        return "break"

    def focus_search_shortcut(self, event=None):
        """Atajo Ctrl+F: Enfocar el buscador de la pestaña activa o buscador global"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            curr = self.tab_control.index(self.tab_control.select())
            if curr == 0 and hasattr(self, 'pos_search_entry'):
                self.pos_search_entry.focus()
                self.pos_search_entry.select_range(0, 'end')
            elif curr == 1 and hasattr(self, 'inventory_search_entry'):
                self.inventory_search_entry.focus()
                self.inventory_search_entry.select_range(0, 'end')
            elif curr == 2 and hasattr(self, 'client_search_entry'):
                self.client_search_entry.focus()
                self.client_search_entry.select_range(0, 'end')
            elif curr == 3 and hasattr(self, 'date_from_entry'):
                self.date_from_entry.focus()
                self.date_from_entry.select_range(0, 'end')
            elif hasattr(self, 'global_search_entry'):
                self.global_search_entry.focus()
                self.global_search_entry.select_range(0, 'end')
        except Exception as e:
            print(f"DEBUG: Error en Ctrl+F: {e}")
        return "break"

    def new_record_shortcut(self, event=None):
        """Atajo Ctrl+N: Crear nuevo registro según la pestaña activa"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            curr = self.tab_control.index(self.tab_control.select())
            if curr == 0:
                self.create_new_invoice()
            elif curr == 1 and self.user_role != "empleado":
                self.open_new_product_dialog()
            elif curr == 2:
                self.open_new_client_dialog()
            elif curr == 5 and self.user_role == "admin":
                self.open_new_user_from_tab()
        except Exception as e:
            print(f"DEBUG: Error en Ctrl+N: {e}")
        return "break"

    def print_or_pay_shortcut(self, event=None):
        """Atajo Ctrl+P: Procesar pago en POS o Imprimir en Facturas"""
        is_child, _ = self._is_child_dialog_focused()
        if is_child:
            return
        try:
            curr = self.tab_control.index(self.tab_control.select())
            if curr == 0:
                self.process_payment()
            elif curr == 3:
                self.generate_pdf_invoice()
        except Exception as e:
            print(f"DEBUG: Error en Ctrl+P: {e}")
        return "break"

    def on_escape_shortcut(self, event=None):
        """Atajo Escape: Cerrar diálogo hijo activo o limpiar selecciones en tablas"""
        is_child, top = self._is_child_dialog_focused()
        if is_child and top is not None:
            safe_destroy(top)
            return "break"
        try:
            curr = self.tab_control.index(self.tab_control.select())
            if curr == 0:
                if hasattr(self, 'pos_tree'):
                    self.pos_tree.selection_remove(self.pos_tree.selection())
                if hasattr(self, 'invoice_tree'):
                    self.invoice_tree.selection_remove(self.invoice_tree.selection())
            elif curr == 1 and hasattr(self, 'inventory_tree'):
                self.inventory_tree.selection_remove(self.inventory_tree.selection())
            elif curr == 2 and hasattr(self, 'clients_tree'):
                self.clients_tree.selection_remove(self.clients_tree.selection())
            elif curr == 3 and hasattr(self, 'invoices_tree'):
                self.invoices_tree.selection_remove(self.invoices_tree.selection())
            elif curr == 5 and hasattr(self, 'users_tree'):
                self.users_tree.selection_remove(self.users_tree.selection())
        except Exception:
            pass
        return "break"

    def on_window_resize(self, event):
        if event.widget is self:
            self.adjust_responsive_layout(event.width, event.height)

    def adjust_responsive_layout(self, width, height):
        """Ajustar dinámicamente algunos contenedores para resoluciones más pequeñas."""
        if hasattr(self, 'top_frame') and hasattr(self, 'search_frame'):
            if width < 1100:
                try:
                    self.quick_stats_frame.grid_remove()
                    self.search_frame.grid_configure(column=3, columnspan=2, sticky="ew")
                except Exception:
                    pass
            else:
                try:
                    self.quick_stats_frame.grid()
                    self.search_frame.grid_configure(column=4, columnspan=1, sticky="ew")
                except Exception:
                    pass

        if hasattr(self, 'reports_sidebar') and hasattr(self, 'report_content_area'):
            if width < 1100:
                try:
                    self.reports_sidebar.pack_forget()
                    self.report_content_area.pack_forget()
                    self.reports_sidebar.pack(side="top", fill="x")
                    self.report_content_area.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 10))
                    self.reports_sidebar.configure(width=200)
                except Exception:
                    pass
            else:
                try:
                    self.reports_sidebar.pack_forget()
                    self.report_content_area.pack_forget()
                    self.reports_sidebar.pack(side="left", fill="y")
                    self.report_content_area.pack(side="left", fill="both", expand=True, padx=20, pady=20)
                    self.reports_sidebar.configure(width=280)
                except Exception:
                    pass

        self.adjust_invoice_action_buttons(width)

    def adjust_invoice_action_buttons(self, width=None):
        """Ajustar el layout de los botones de acción de facturas según el ancho disponible."""
        if not hasattr(self, 'invoices_action_frame') or not hasattr(self, 'invoices_action_buttons'):
            return

        try:
            if width is None or width <= 0:
                width = self.invoices_action_frame.winfo_width() or self.winfo_width()

            if width <= 0:
                width = self.winfo_width()

            max_button_width = 180
            columns = max(1, min(len(self.invoices_action_buttons), width // max_button_width))
            for btn in self.invoices_action_buttons:
                btn.grid_forget()

            for col in range(columns):
                self.invoices_action_frame.grid_columnconfigure(col, weight=1)

            for index, btn in enumerate(self.invoices_action_buttons):
                row = index // columns
                col = index % columns
                btn.grid(row=row, column=col, sticky="ew", padx=5, pady=5)
        except Exception:
            pass

    def load_main_logo(self):
        """Cargar logo para la aplicación principal"""
        self.main_logo = None
        try:
            if os.path.exists("img/logo.png"):
                logo_img = Image.open("img/logo.png")
                self.main_logo = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(30, 30))
        except Exception as e:
            print(f"Error loading main logo: {e}")

    def setup_icons(self):
        """Configurar iconos para botones"""
        self.icons = {
            "add": "➕",
            "delete": "🗑️",
            "edit": "✏️",
            "print": "🖨️",
            "save": "💾",
            "search": "🔍",
            "theme": "🌙",
            "new_invoice": "🧾",
            "add_item": "📥",
            "payment": "💰",
            "clear": "🗑️",
            "client": "👤",
            "products": "📦",
            "reports": "📊"
        }

    def create_top_bar(self):
        """Crear barra superior con herramientas"""
        self.top_frame = ctk.CTkFrame(self, height=60)
        self.top_frame.pack(side="top", fill="x", padx=10, pady=5)
        self.top_frame.grid_columnconfigure(0, weight=0)
        self.top_frame.grid_columnconfigure(1, weight=0)
        self.top_frame.grid_columnconfigure(2, weight=0)
        self.top_frame.grid_columnconfigure(3, weight=0)
        self.top_frame.grid_columnconfigure(4, weight=1)
        self.top_frame.grid_columnconfigure(5, weight=0)
        self.top_frame.grid_columnconfigure(6, weight=0)

        # Logo y Título
        logo_label = ctk.CTkLabel(self.top_frame, text="", image=self.main_logo) if self.main_logo else None
        if logo_label:
            logo_label.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)

        # Botón nueva factura
        self.new_invoice_btn = ctk.CTkButton(
            self.top_frame,
            text=f"{self.icons['new_invoice']} Nueva Factura",
            command=self.create_new_invoice,
            height=35,
            corner_radius=8,
            font=("Segoe UI", 12, "bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        )
        self.new_invoice_btn.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Separador
        ctk.CTkLabel(self.top_frame, text="|").grid(row=0, column=2, padx=10, pady=5)

        # Contadores rápidos
        self.quick_stats_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.quick_stats_frame.grid(row=0, column=3, sticky="w", padx=10, pady=5)

        self.product_count_label = ctk.CTkLabel(
            self.quick_stats_frame,
            text="Productos: 0",
            font=("Segoe UI", 11)
        )
        self.product_count_label.pack(side="left", padx=10)

        self.client_count_label = ctk.CTkLabel(
            self.quick_stats_frame,
            text="Clientes: 0",
            font=("Segoe UI", 11)
        )
        self.client_count_label.pack(side="left", padx=10)

        self.invoice_count_label = ctk.CTkLabel(
            self.quick_stats_frame,
            text="Facturas: 0",
            font=("Segoe UI", 11)
        )
        self.invoice_count_label.pack(side="left", padx=10)

        # Buscador global (Responsivo)
        self.search_frame = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        self.search_frame.grid(row=0, column=4, sticky="ew", padx=10, pady=5)

        self.global_search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="Buscar productos..."
        )
        self.global_search_entry.pack(side="left", fill="x", expand=True)
        self.global_search_entry.bind("<Return>", self.on_global_search)
        self.global_search_entry.bind("<KP_Enter>", self.on_global_search)

        search_btn = ctk.CTkButton(
            self.search_frame,
            text=self.icons["search"],
            width=40,
            corner_radius=8,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            command=self.perform_global_search
        )
        search_btn.pack(side="left", padx=5)

        # Botón configuración
        self.settings_btn = ctk.CTkButton(
            self.top_frame,
            text="⚙️ Configuración",
            command=self.open_settings_dialog,
            height=35,
            corner_radius=8,
            font=("Segoe UI", 11),
            fg_color="#475569",
            hover_color="#334155"
        )
        self.settings_btn.grid(row=0, column=5, sticky="e", padx=5, pady=5)

        # Botón cerrar sesión
        self.logout_btn = ctk.CTkButton(
            self.top_frame,
            text="🔒 Cerrar Sesión",
            command=self.logout,
            height=35,
            corner_radius=8,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        )
        self.logout_btn.grid(row=0, column=6, sticky="e", padx=5, pady=5)

    def create_point_of_sale_tab(self):
        """Crear interfaz de punto de venta"""
        # Frame principal con grid para layout responsivo
        main_frame = ctk.CTkFrame(self.tab_point_of_sale)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(0, weight=1)

        # Columna izquierda: Selección de productos
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Cabecera de productos
        header_frame = ctk.CTkFrame(left_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header_frame,
            text="PRODUCTOS DISPONIBLES",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=10)

        # Buscador de productos
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 10))

        self.pos_search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Buscar producto por nombre o código..."
        )
        self.pos_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.pos_search_entry.bind("<KeyRelease>", self.on_pos_search)
        self.pos_search_entry.bind("<Return>", self.add_first_pos_search_result)

        # Tabla de productos
        self.pos_tree_frame = ctk.CTkFrame(left_frame)
        self.pos_tree_frame.pack(fill="both", expand=True)

        # Crear Treeview para productos
        columns = ("ID", "Nombre", "Precio", "Stock")
        self.pos_tree = ttk.Treeview(
            self.pos_tree_frame,
            columns=columns,
            show="headings",
            height=15
        )

        for col in columns:
            self.pos_tree.heading(col, text=col)
            self.pos_tree.column(col, width=100)

        self.pos_tree.column("Nombre", width=300)
        self.pos_tree.column("Precio", width=100, anchor="e")
        self.pos_tree.column("Stock", width=80, anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.pos_tree_frame, orient="vertical", command=self.pos_tree.yview)
        self.pos_tree.configure(yscrollcommand=scrollbar.set)
        
        self.pos_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Doble clic para agregar producto
        self.pos_tree.bind("<Double-1>", self.add_product_to_invoice)
        self.pos_tree.bind("<Return>", self.add_product_to_invoice)

        # Columna derecha: Factura actual
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # Información de factura
        invoice_header = ctk.CTkFrame(right_frame)
        invoice_header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            invoice_header,
            text=f"FACTURA #{self.invoice_counter}",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=5)

        self.invoice_date_label = ctk.CTkLabel(
            invoice_header,
            text=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            font=("Segoe UI", 11)
        )
        self.invoice_date_label.pack()

        # Selección de cliente
        client_frame = ctk.CTkFrame(right_frame)
        client_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(client_frame, text="Cliente:").pack(side="left", padx=(0, 10))
        
        self.client_var = tk.StringVar()
        self.client_combobox = ttk.Combobox(
            client_frame,
            textvariable=self.client_var,
            values=[c["name"] for c in self.clients],
            state="readonly",
            width=30
        )
        self.client_combobox.pack(side="left", padx=(0, 10))
        self.client_combobox.set("")

        # Botón nuevo cliente
        new_client_btn = ctk.CTkButton(
            client_frame,
            text=self.icons["client"],
            width=30,
            command=self.add_client_from_pos
        )
        new_client_btn.pack(side="left")

        # Botón búsqueda rápida de cliente
        search_client_btn = ctk.CTkButton(
            client_frame,
            text=self.icons["search"],
            width=30,
            command=self.quick_search_client_from_pos
        )
        search_client_btn.pack(side="left", padx=(5,0))

        # Tabla de items de la factura
        items_frame = ctk.CTkFrame(right_frame)
        items_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Treeview para items
        columns = ("Producto", "Cant", "Precio", "Total")
        self.invoice_tree = ttk.Treeview(
            items_frame,
            columns=columns,
            show="headings",
            height=10
        )

        for col in columns:
            self.invoice_tree.heading(col, text=col)
            self.invoice_tree.column(col, width=80)

        self.invoice_tree.column("Producto", width=200)
        self.invoice_tree.column("Precio", width=80, anchor="e")
        self.invoice_tree.column("Total", width=80, anchor="e")

        scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=self.invoice_tree.yview)
        self.invoice_tree.configure(yscrollcommand=scrollbar.set)
        
        self.invoice_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Vincular tecla Suprimir y Retroceso
        self.invoice_tree.bind("<Delete>", self.remove_selected_invoice_item)
        self.invoice_tree.bind("<BackSpace>", self.remove_selected_invoice_item)

        # Menú contextual para el carrito de facturación
        self.invoice_items_menu = tk.Menu(self, tearoff=0)
        self.invoice_items_menu.add_command(label=" Quitar seleccionado(s)", command=self.remove_selected_invoice_item)
        self.invoice_items_menu.add_separator()
        self.invoice_items_menu.add_command(label=" Limpiar todo el carrito", command=self.clear_current_invoice)

        def show_invoice_items_menu(event):
            item = self.invoice_tree.identify_row(event.y)
            if item:
                if item not in self.invoice_tree.selection():
                    self.invoice_tree.selection_set(item)
                self.invoice_items_menu.post(event.x_root, event.y_root)

        self.invoice_tree.bind("<Button-3>", show_invoice_items_menu)

        # Totales
        totals_frame = ctk.CTkFrame(right_frame)
        totals_frame.pack(fill="x", pady=(0, 10))

        self.subtotal_label = ctk.CTkLabel(
            totals_frame,
            text="Subtotal: $0.00",
            font=("Segoe UI", 12)
        )
        self.subtotal_label.pack(anchor="e", padx=20)

        self.tax_label = ctk.CTkLabel(
            totals_frame,
            text="IVA: $0.00",
            font=("Segoe UI", 12)
        )
        self.tax_label.pack(anchor="e", padx=20)

        self.total_label = ctk.CTkLabel(
            totals_frame,
            text="TOTAL: $0.00",
            font=("Segoe UI", 16, "bold")
        )
        self.total_label.pack(anchor="e", padx=20)

        # Botones de acción
        buttons_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        buttons_frame.pack(fill="x")

        ctk.CTkButton(
            buttons_frame,
            text=f"{self.icons['add_item']} Agregar Item",
            command=self.add_item_manual,
            width=120,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text=f"{self.icons['delete']} Quitar",
            command=self.remove_selected_invoice_item,
            width=90,
            corner_radius=8,
            fg_color="#EF4444",
            hover_color="#DC2626"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text=f"{self.icons['clear']} Limpiar",
            command=self.clear_current_invoice,
            width=90,
            corner_radius=8,
            fg_color="#64748B",
            hover_color="#475569"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text=f"{self.icons['payment']} Procesar Pago",
            command=self.process_payment,
            width=140,
            corner_radius=8,
            fg_color="#059669",
            hover_color="#047857"
        ).pack(side="right", padx=5)

        # Cargar productos en el POS
        self.refresh_pos_products()

    def create_inventory_tab(self):
        """Crear interfaz de inventario"""
        main_frame = ctk.CTkFrame(self.tab_inventory)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Frame de controles superiores
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.pack(fill="x", pady=(0, 10))

        # Botones de acción
        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['add']} Nuevo Producto",
            command=self.open_new_product_dialog,
            width=150,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['edit']} Editar",
            command=self.open_edit_product_dialog,
            width=100,
            corner_radius=8,
            fg_color="#F59E0B",
            hover_color="#D97706"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['delete']} Eliminar",
            command=self.delete_product,
            width=100,
            corner_radius=8,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        ).pack(side="left", padx=5)

        # Buscador y Filtros
        search_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        search_frame.pack(side="left", fill="x", expand=True, padx=10)

        ctk.CTkLabel(search_frame, text="Buscar:").pack(side="left", padx=(0, 5))
        self.inventory_search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Nombre o código...",
            width=200
        )
        self.inventory_search_entry.pack(side="left", padx=(0, 15))
        self.inventory_search_entry.bind("<KeyRelease>", self.on_inventory_search)

        ctk.CTkLabel(search_frame, text="Categoría:").pack(side="left", padx=(0, 5))
        self.category_filter = ctk.CTkComboBox(
            search_frame,
            values=["Todas"],
            command=lambda v: self.refresh_inventory(self.inventory_search_entry.get().lower()),
            width=150
        )
        self.category_filter.set("Todas")
        self.category_filter.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(search_frame, text="Proveedor:").pack(side="left", padx=(10, 5))
        self.supplier_filter = ctk.CTkComboBox(
            search_frame,
            values=["Todos"],
            command=lambda v: self.refresh_inventory(self.inventory_search_entry.get().lower()),
            width=140
        )
        self.supplier_filter.set("Todos")
        self.supplier_filter.pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['info'] if 'info' in self.icons else ''} Ver Detalle",
            command=self.view_inventory_detail,
            width=120,
            corner_radius=8,
            fg_color="#6366F1",
            hover_color="#4F46E5"
        ).pack(side="left", padx=5)

        # Tabla de inventario
        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "Código", "Nombre", "Categoría", "Precio", "Stock", "Mínimo", "Ubicación")
        self.inventory_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=20
        )

        column_widths = {
            "ID": 50, "Código": 100, "Nombre": 250, "Categoría": 120,
            "Precio": 80, "Stock": 60, "Mínimo": 60, "Ubicación": 100
        }

        for col in columns:
            self.inventory_tree.heading(col, text=col)
            self.inventory_tree.column(col, width=column_widths[col], anchor="center")
        
        self.inventory_tree.column("Nombre", anchor="w")
        self.inventory_tree.column("Precio", anchor="e")

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.inventory_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.inventory_tree.xview)
        self.inventory_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.inventory_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Cargar datos
        self.refresh_inventory()

        # Vincular teclas
        self.inventory_tree.bind("<Return>", lambda e: self.open_edit_product_dialog())
        self.inventory_tree.bind("<Double-1>", lambda e: self.open_edit_product_dialog())
        self.inventory_tree.bind("<Delete>", lambda e: self.delete_product())

        # Menú contextual
        self.inventory_menu = tk.Menu(self, tearoff=0)
        self.inventory_menu.add_command(label=" Nuevo Producto", command=self.open_new_product_dialog)
        self.inventory_menu.add_separator()
        self.inventory_menu.add_command(label=" Editar", command=self.open_edit_product_dialog)
        self.inventory_menu.add_command(label=" Eliminar", command=self.delete_product)
        self.inventory_menu.add_command(label=" Ver Detalle", command=self.view_inventory_detail)

        def show_inventory_menu(event):
            item = self.inventory_tree.identify_row(event.y)
            if item:
                if item not in self.inventory_tree.selection():
                    self.inventory_tree.selection_set(item)
                self.inventory_menu.post(event.x_root, event.y_root)

        self.inventory_tree.bind("<Button-3>", show_inventory_menu)

    def create_clients_tab(self):
        """Crear interfaz de gestión de clientes"""
        main_frame = ctk.CTkFrame(self.tab_clients)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Frame de controles
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['add']} Nuevo Cliente",
            command=self.open_new_client_dialog,
            width=150,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['edit']} Editar",
            command=self.open_edit_client_dialog,
            width=100,
            corner_radius=8,
            fg_color="#F59E0B",
            hover_color="#D97706"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['delete']} Eliminar",
            command=self.delete_client,
            width=100,
            corner_radius=8,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text="Ver Detalle",
            command=self.view_client_detail,
            width=120,
            corner_radius=8,
            fg_color="#6366F1",
            hover_color="#4F46E5"
        ).pack(side="left", padx=5)

        # Buscador (Responsivo)
        search_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        search_frame.pack(side="left", fill="x", expand=True, padx=10)

        ctk.CTkLabel(search_frame, text="Buscar:").pack(side="left", padx=(0, 5))
        
        self.client_search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Nombre o documento..."
        )
        self.client_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.client_search_entry.bind("<KeyRelease>", self.on_client_search)

        ctk.CTkLabel(search_frame, text="Tipo:").pack(side="left", padx=(10, 5))
        self.client_type_filter = ctk.CTkComboBox(
            search_frame,
            values=["Todos", "General", "Público", "Empresa", "Distribuidor"],
            command=lambda v: self.refresh_clients(self.client_search_entry.get().lower()),
            width=150
        )
        self.client_type_filter.set("Todos")
        self.client_type_filter.pack(side="left", padx=(0, 5))

        # Tabla de clientes
        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "Nombre", "RIF/Cédula de Identidad (CI)", "Teléfono", "Email", "Dirección", "Tipo")
        self.clients_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=20
        )

        for col in columns:
            self.clients_tree.heading(col, text=col)
            self.clients_tree.column(col, width=120, anchor="center")
        
        self.clients_tree.column("ID", width=50)
        self.clients_tree.column("Nombre", width=200, anchor="w")
        self.clients_tree.column("Dirección", width=250)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.clients_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.clients_tree.xview)
        self.clients_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.clients_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Cargar clientes
        self.refresh_clients()

        # Vincular teclas
        self.clients_tree.bind("<Return>", lambda e: self.open_edit_client_dialog())
        self.clients_tree.bind("<Double-1>", lambda e: self.open_edit_client_dialog())
        self.clients_tree.bind("<Delete>", lambda e: self.delete_client())

        # Menú contextual
        self.clients_menu = tk.Menu(self, tearoff=0)
        self.clients_menu.add_command(label=" Nuevo Cliente", command=self.open_new_client_dialog)
        self.clients_menu.add_separator()
        self.clients_menu.add_command(label=" Editar", command=self.open_edit_client_dialog)
        self.clients_menu.add_command(label=" Eliminar", command=self.delete_client)
        self.clients_menu.add_command(label=" Ver Detalle", command=self.view_client_detail)

        def show_clients_menu(event):
            item = self.clients_tree.identify_row(event.y)
            if item:
                if item not in self.clients_tree.selection():
                    self.clients_tree.selection_set(item)
                self.clients_menu.post(event.x_root, event.y_root)

        self.clients_tree.bind("<Button-3>", show_clients_menu)

    def create_invoices_tab(self):
        """Crear interfaz de gestión de facturas"""
        main_frame = ctk.CTkFrame(self.tab_invoices)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Frame de filtros
        filters_frame = ctk.CTkFrame(main_frame)
        filters_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(filters_frame, text="Filtrar por:").pack(side="left", padx=(10, 5))

        # Fecha desde
        ctk.CTkLabel(filters_frame, text="Desde:").pack(side="left", padx=(10, 5))
        self.date_from_entry = ctk.CTkEntry(filters_frame, placeholder_text="DD/MM/AAAA")
        self.date_from_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Fecha hasta
        ctk.CTkLabel(filters_frame, text="Hasta:").pack(side="left", padx=(0, 5))
        self.date_to_entry = ctk.CTkEntry(filters_frame, placeholder_text="DD/MM/AAAA")
        self.date_to_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Filtro por estado
        ctk.CTkLabel(filters_frame, text="Estado:").pack(side="left", padx=(0, 5))
        self.status_filter_var = tk.StringVar(value="Todos")
        self.status_filter_combobox = ttk.Combobox(
            filters_frame,
            textvariable=self.status_filter_var,
            values=["Todos", "Pagada", "Pendiente", "Cancelada"],
            state="readonly",
            width=15
        )
        self.status_filter_combobox.pack(side="left", padx=(0, 10))

        # Botón aplicar filtros
        ctk.CTkButton(
            filters_frame,
            text="Aplicar Filtros",
            command=self.apply_invoice_filters,
            width=120,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=10)

        # Botón limpiar filtros
        ctk.CTkButton(
            filters_frame,
            text="Limpiar",
            command=self.clear_invoice_filters,
            width=100,
            corner_radius=8,
            fg_color="#64748B",
            hover_color="#475569"
        ).pack(side="left", padx=5)

        # Tabla de facturas
        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("N° Factura", "Fecha", "Cliente", "Subtotal", "IVA", "Total", "Estado", "Método Pago")
        self.invoices_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=20
        )

        column_widths = {
            "N° Factura": 100, "Fecha": 120, "Cliente": 200, "Subtotal": 100,
            "IVA": 80, "Total": 100, "Estado": 100, "Método Pago": 120
        }

        for col in columns:
            self.invoices_tree.heading(col, text=col)
            self.invoices_tree.column(col, width=column_widths[col], anchor="center")
        
        self.invoices_tree.column("Cliente", anchor="w")
        self.invoices_tree.column("Subtotal", anchor="e")
        self.invoices_tree.column("IVA", anchor="e")
        self.invoices_tree.column("Total", anchor="e")

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.invoices_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.invoices_tree.xview)
        self.invoices_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.invoices_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Frame de botones de acción
        self.invoices_action_frame = ctk.CTkFrame(main_frame)
        self.invoices_action_frame.pack(fill="x", pady=(10, 0))
        for col in range(7):
            self.invoices_action_frame.grid_columnconfigure(col, weight=1)

        self.invoices_action_buttons = []

        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text=f"{self.icons['print']} Imprimir Factura",
            command=self.generate_pdf_invoice,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="📦 Nota de Entrega",
            command=self.generate_pdf_delivery_note,
            corner_radius=8,
            fg_color="#0EA5E9",
            hover_color="#0284C7"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="Realizar pago pendiente",
            command=self.mark_invoice_as_paid,
            corner_radius=8,
            fg_color="#059669",
            hover_color="#047857"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="Ver Detalle",
            command=self.view_invoice_detail,
            corner_radius=8,
            fg_color="#6366F1",
            hover_color="#4F46E5"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="Cancelar Factura",
            command=self.cancel_invoice,
            corner_radius=8,
            fg_color="#F59E0B",
            hover_color="#D97706"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="Eliminar Factura",
            command=self.delete_invoice,
            corner_radius=8,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        ))
        self.invoices_action_buttons.append(ctk.CTkButton(
            self.invoices_action_frame,
            text="Exportar a Excel",
            command=self.export_invoices_excel,
            corner_radius=8,
            fg_color="#059669",
            hover_color="#047857"
        ))

        self.adjust_invoice_action_buttons()
        self.after(100, self.adjust_invoice_action_buttons)

        # Cargar facturas
        self.refresh_invoices()

        # Vincular teclas
        self.invoices_tree.bind("<Return>", lambda e: self.view_invoice_detail())
        self.invoices_tree.bind("<Double-1>", lambda e: self.view_invoice_detail())
        self.invoices_tree.bind("<Delete>", lambda e: self.delete_invoice())

        # Menú contextual
        self.invoices_menu = tk.Menu(self, tearoff=0)
        self.invoices_menu.add_command(label=" Ver Detalle", command=self.view_invoice_detail)
        self.invoices_menu.add_command(label=" Imprimir", command=self.generate_pdf_invoice)
        self.invoices_menu.add_command(label=" Nota de Entrega", command=self.generate_pdf_delivery_note)
        self.invoices_menu.add_command(label=" Exportar a Excel", command=self.export_invoices_excel)
        self.invoices_menu.add_separator()
        self.invoices_menu.add_command(label=" Marcar como Pagada", command=self.mark_invoice_as_paid)
        self.invoices_menu.add_command(label=" Anular", command=self.cancel_invoice)
        self.invoices_menu.add_command(label=" Eliminar", command=self.delete_invoice)

        def show_invoices_menu(event):
            item = self.invoices_tree.identify_row(event.y)
            if item:
                if item not in self.invoices_tree.selection():
                    self.invoices_tree.selection_set(item)
                self.invoices_menu.post(event.x_root, event.y_root)

        self.invoices_tree.bind("<Button-3>", show_invoices_menu)

    def create_reports_tab(self):
        """Crear interfaz de reportes con estética premium"""
        # Limpiar tab
        for widget in self.tab_reports.winfo_children():
            safe_destroy(widget)

        # Contenedor principal con efecto de "capas"
        bg_frame = ctk.CTkFrame(self.tab_reports, fg_color=("#F8FAFC", "#0F172A"))
        bg_frame.pack(fill="both", expand=True)

        # Barra lateral de navegación de reportes (Sidebar)
        self.reports_sidebar = ctk.CTkFrame(bg_frame, width=280, corner_radius=0, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#E2E8F0", "#334155"))
        self.reports_sidebar.pack(side="left", fill="y")
        self.reports_sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.reports_sidebar,
            text="CENTRO DE REPORTES",
            font=("Inter", 16, "bold"),
            text_color=("#64748B", "#94A3B8")
        ).pack(pady=(30, 20), padx=20, anchor="w")

        # Lista de reportes con iconos modernos
        reports = [
            ("📊", "Ventas por Día"),
            ("📈", "Ventas por Mes"),
            ("👥", "Ventas por Cliente"),
            ("📦", "Productos Top"),
            ("⚠️", "Stock Crítico"),
            ("💰", "Flujo de Caja"),
            ("🏪", "Desempeño"),
            ("📋", "Pendientes"),
            ("🏦", "Banco")
        ]

        self.report_var = tk.StringVar(value=f"{reports[0][0]} {reports[0][1]}")
        self.report_buttons = {}

        def select_report(name):
            self.report_var.set(name)
            for btn_name, btn in self.reports_buttons.items():
                if btn_name == name:
                    btn.configure(fg_color=("#F1F5F9", "#334155"), text_color=("#2563EB", "#60A5FA"))
                else:
                    btn.configure(fg_color="transparent", text_color=("#475569", "#CBD5E1"))
            self.generate_report()

        self.reports_buttons = {}
        for icon, name in reports:
            full_name = f"{icon} {name}"
            btn = ctk.CTkButton(
                self.reports_sidebar,
                text=full_name,
                anchor="w",
                height=45,
                corner_radius=8,
                fg_color="transparent",
                text_color=("#475569", "#CBD5E1"),
                hover_color=("#F1F5F9", "#334155"),
                font=("Inter", 12),
                command=lambda n=full_name: select_report(n)
            )
            btn.pack(fill="x", padx=15, pady=2)
            self.reports_buttons[full_name] = btn

        # Botones inferiores
        footer_frame = ctk.CTkFrame(self.reports_sidebar, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", pady=20, padx=15)

        ctk.CTkButton(
            footer_frame,
            text="🏠 Panel Principal",
            command=self.update_dashboard,
            height=40,
            corner_radius=10,
            font=("Inter", 12, "bold"),
            fg_color=("#2563EB", "#3B82F6"),
            hover_color=("#1D4ED8", "#2563EB")
        ).pack(fill="x", pady=5)

        # Área de contenido
        self.report_content_area = ctk.CTkFrame(bg_frame, fg_color="transparent")
        self.report_content_area.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        # Cabecera dinámica del reporte
        self.report_header = ctk.CTkFrame(self.report_content_area, fg_color="transparent")
        self.report_header.pack(fill="x", pady=(0, 20))
        
        self.report_title_label = ctk.CTkLabel(
            self.report_header, 
            text="Dashboard de Inteligencia", 
            font=("Inter", 24, "bold"),
            text_color=("#1E293B", "#F8FAFC")
        )
        self.report_title_label.pack(side="left")

        # Vista de reporte (Textbox inicialmente oculto) - Mantener por compatibilidad interna o logs
        self.report_text = ctk.CTkTextbox(
            self.report_content_area,
            font=("Cascadia Code", 12),
            corner_radius=12,
            border_width=1,
            border_color=("#E2E8F0", "#334155"),
            fg_color=("#FFFFFF", "#1E293B")
        )

        # Botón de refrescar (Único, movido desde update_dashboard)
        self.refresh_report_btn = ctk.CTkButton(
            self.report_header, 
            text="🔄 Actualizar Datos", 
            width=140, 
            height=32,
            corner_radius=8,
            command=self.update_dashboard,
            fg_color=("#F1F5F9", "#334155"),
            text_color=("#475569", "#CBD5E1"),
            hover_color=("#E2E8F0", "#475569"),
            font=("Inter", 11, "bold")
        )
        self.refresh_report_btn.pack(side="right")

        # Inicialmente mostrar dashboard
        self.update_dashboard()

    def update_dashboard(self):
        """Actualizar el dashboard con una estética minimalista y moderna"""
        # Validar si report_content_area existe antes de intentar acceder o limpiar sus elementos
        if not hasattr(self, 'report_content_area') or not self.report_content_area:
            return

        # Limpiar área de contenido de forma segura
        header = getattr(self, 'report_header', None)
        text = getattr(self, 'report_text', None)

        for widget in self.report_content_area.winfo_children():
            if widget not in (header, text):
                safe_destroy(widget)
        
        if text and hasattr(text, 'winfo_exists') and text.winfo_exists():
            text.pack_forget()

        if hasattr(self, 'report_title_label') and self.report_title_label:
            self.report_title_label.configure(text="Resumen Analítico")
        
        # Asegurar que el botón de refrescar sea visible en el dashboard
        if hasattr(self, 'refresh_report_btn') and self.refresh_report_btn and self.refresh_report_btn.winfo_exists():
            self.refresh_report_btn.pack(side="right")

        # Contenedor con scroll elegante
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # --- SECCIÓN KPI: TARJETAS FLOTANTES ---
        kpi_container = ctk.CTkFrame(container, fg_color="transparent")
        kpi_container.pack(fill="x", pady=(10, 20))

        # Cálculos
        total_sales = sum(inv["total"] for inv in self.invoices if inv["status"] in (["Pagada", "Pendiente"] if getattr(self, 'include_pending_in_dashboard', False) else ["Pagada"]))
        low_stock = len([p for p in self.products if p["stock"] <= p.get("min_stock", 5)])
        
        cards_data = [
            ("Ingresos Totales", f"${total_sales:,.2f}", "💰", "#3B82F6"),
            ("Stock Crítico", str(low_stock), "⚠️", "#EF4444"),
            ("Clientes Activos", str(len(self.clients)), "👥", "#8B5CF6"),
            ("Facturas Emitidas", str(len(self.invoices)), "📄", "#10B981")
        ]

        for title, val, icon, color in cards_data:
            card = ctk.CTkFrame(kpi_container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
            card.pack(side="left", fill="both", expand=True, padx=8)
            
            ctk.CTkLabel(card, text=icon, font=("Inter", 24), text_color=color).pack(pady=(20, 5))
            ctk.CTkLabel(card, text=title, font=("Inter", 12), text_color=("#64748B", "#94A3B8")).pack()
            ctk.CTkLabel(card, text=val, font=("Inter", 20, "bold"), text_color=("#1E293B", "#F8FAFC")).pack(pady=(0, 20))

        # --- SECCIÓN GRÁFICOS: GRID MODERNO ---
        charts_grid = ctk.CTkFrame(container, fg_color="transparent")
        charts_grid.pack(fill="both", expand=True)
        charts_grid.grid_columnconfigure((0, 1), weight=1)

        def create_chart_container(parent, title, row, col):
            f = ctk.CTkFrame(parent, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
            f.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            ctk.CTkLabel(f, text=title, font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")
            return f

        # Configuración Matplotlib Premium
        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        plt.rcParams.update({
            'text.color': plt_fg, 'axes.labelcolor': plt_fg, 'xtick.color': plt_fg, 
            'ytick.color': plt_fg, 'axes.facecolor': plt_bg, 'figure.facecolor': plt_bg,
            'font.family': 'sans-serif', 'font.sans-serif': ['Inter', 'Segoe UI']
        })

        # 1. Tendencia de Ventas
        f1 = create_chart_container(charts_grid, "Tendencia de Ventas", 0, 0)
        canvas1 = FigureCanvasTkAgg(self.create_sales_trend_chart(plt_bg, plt_fg), master=f1)
        canvas1.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 2. Productos Más Vendidos
        f2 = create_chart_container(charts_grid, "Distribución de Productos", 0, 1)
        canvas2 = FigureCanvasTkAgg(self.create_top_products_chart(plt_bg, plt_fg), master=f2)
        canvas2.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 3. Categorías
        f3 = create_chart_container(charts_grid, "Ventas por Categoría", 1, 0)
        canvas3 = FigureCanvasTkAgg(self.create_category_sales_chart(plt_bg, plt_fg), master=f3)
        canvas3.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 4. Clientes Top
        f4 = create_chart_container(charts_grid, "Top Clientes", 1, 1)
        canvas4 = FigureCanvasTkAgg(self.create_top_clients_chart(plt_bg, plt_fg), master=f4)
        canvas4.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def create_top_clients_chart(self, bg_color, fg_color):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        client_sales = {}
        for inv in self.invoices:
            if inv["status"] != "Cancelada":
                c_name = inv["client"]
                client_sales[c_name] = client_sales.get(c_name, 0) + inv["total"]
        
        sorted_clients = sorted(client_sales.items(), key=lambda x: x[1], reverse=True)[:5]
        names = [c[0].split()[0] for c in sorted_clients] # Primer nombre
        amounts = [c[1] for c in sorted_clients]
        
        if not names:
            names, amounts = ["Sin Datos"], [0]
            
        ax.barh(names, amounts, color="#8B5CF6")
        ax.set_title("Top Clientes (Ventas $)", fontsize=10, fontweight='bold', pad=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.invert_yaxis()
        fig.tight_layout()
        return fig

    def create_sales_trend_chart(self, bg_color, fg_color):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        # Agrupar ventas por fecha (últimos 7 días con datos)
        sales_by_day = {}
        for inv in self.invoices:
            if inv["status"] != "Cancelada":
                date = inv["date"].split()[0]
                sales_by_day[date] = sales_by_day.get(date, 0) + inv["total"]
        
        dates = sorted(sales_by_day.keys())[-7:]
        values = [sales_by_day[d] for d in dates]
        
        if not dates:
            dates, values = ["No Data"], [0]

        ax.plot(dates, values, marker='o', color='#3B82F6', linewidth=2)
        ax.fill_between(dates, values, color='#3B82F6', alpha=0.1)
        ax.set_title("Tendencia de Ventas (Días)", fontsize=10, fontweight='bold', pad=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        fig.tight_layout()
        return fig

    def create_top_products_chart(self, bg_color, fg_color):
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        product_sales = {}
        for inv in self.invoices:
            if inv["status"] != "Cancelada":
                for item in inv["items"]:
                    p_name = item["product"]
                    product_sales[p_name] = product_sales.get(p_name, 0) + item["quantity"]
        
        sorted_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
        names = []
        for p in sorted_products:
            name = str(p[0]) if p[0] is not None else "Sin Nombre"
            if len(name) > 15:
                names.append(name[:15] + "..")
            else:
                names.append(name)
        counts = [p[1] for p in sorted_products]
        
        if not names:
            names, counts = ["Sin Datos"], [0]
            
        colors = ["#2563EB", "#059669", "#6366F1", "#F59E0B", "#DC2626"]
        ax.bar(names, counts, color=colors[:len(names)])
        ax.set_title("Productos Más Vendidos (Cant.)", fontsize=10, fontweight='bold', pad=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout()
        return fig

    def create_category_sales_chart(self, bg_color, fg_color):
        """Crear gráfico de ventas por categoría usando la categoría de cada producto."""
        fig = Figure(figsize=(5, 3), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        category_sales = {}
        for inv in self.invoices:
            if inv.get("status") == "Cancelada":
                continue
            for item in inv.get("items", []):
                product_name = item.get("product")
                category = "Sin Categoría"
                product = next((p for p in self.products if p.get("name") == product_name), None)
                if product is not None:
                    category = product.get("category") or "Sin Categoría"
                category_sales[category] = category_sales.get(category, 0.0) + float(item.get("total", 0.0) or 0)

        if not category_sales:
            ax.bar(["Sin Datos"], [0], color="#94A3B8")
            ax.set_title("Ventas por Categoría", fontsize=10, fontweight='bold', pad=10)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            fig.tight_layout()
            return fig

        sorted_categories = sorted(category_sales.items(), key=lambda x: x[1], reverse=True)[:5]
        labels = [label for label, _ in sorted_categories]
        values = [value for _, value in sorted_categories]
        palette = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

        ax.bar(labels, values, color=palette[:len(labels)])
        ax.set_title("Ventas por Categoría ($)", fontsize=10, fontweight='bold', pad=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.tight_layout()
        return fig

    def get_selected_invoice_data(self):
        """Devuelve el diccionario de la factura seleccionada en la tabla de facturas."""
        try:
            selection = self.invoices_tree.selection()
            if not selection:
                return None
            if len(selection) > 1:
                return None
            item = self.invoices_tree.item(selection[0])
            invoice_number = int(item["values"][0])
            for invoice in self.invoices:
                if invoice.get("number") == invoice_number:
                    return invoice
        except Exception:
            pass
        return None

    # === FUNCIONES PRINCIPALES ===

    def configure_ttk_styles(self):
        """Configurar estilos ttk para el tema claro con paleta moderna"""
        bg_color = "#F8FAFC"
        fg_color = "#1E293B"
        select_bg = "#2563EB"
        field_bg = "#FFFFFF"
        heading_bg = "#E2E8F0"
        heading_fg = "#475569"
        tab_bg = "#E2E8F0"
        tab_selected = "#2563EB"
        tab_fg = "#64748B"
        tab_selected_fg = "#FFFFFF"
        trough_color = "#E2E8F0"
        scrollbar_bg = "#CBD5E1"

        self.ttk_style.configure("Treeview",
                                background=bg_color,
                                foreground=fg_color,
                                fieldbackground=field_bg,
                                borderwidth=0,
                                rowheight=28,
                                font=("Segoe UI", 10))
        self.ttk_style.map('Treeview',
                          background=[('selected', select_bg)],
                          foreground=[('selected', '#FFFFFF')])
        self.ttk_style.configure("Treeview.Heading",
                                background=heading_bg,
                                foreground=heading_fg,
                                relief="flat",
                                font=("Segoe UI", 10, "bold"),
                                padding=6)
        self.ttk_style.map("Treeview.Heading",
                          background=[('active', select_bg)],
                          foreground=[('active', '#FFFFFF')])
        self.ttk_style.configure("TNotebook",
                                background=bg_color,
                                borderwidth=0,
                                tabmargins=[4, 4, 4, 0])
        self.ttk_style.configure("TNotebook.Tab",
                                background=tab_bg,
                                foreground=tab_fg,
                                borderwidth=0,
                                padding=[14, 6],
                                font=("Segoe UI", 11, "bold"))
        self.ttk_style.map("TNotebook.Tab",
                          background=[("selected", tab_selected)],
                          foreground=[("selected", tab_selected_fg)])
        self.ttk_style.configure("TCombobox",
                                fieldbackground=field_bg,
                                background=bg_color,
                                foreground=fg_color,
                                padding=4,
                                font=("Segoe UI", 10))
        self.ttk_style.configure("Vertical.TScrollbar",
                                background=scrollbar_bg,
                                troughcolor=trough_color,
                                borderwidth=0,
                                relief="flat")
        self.ttk_style.configure("Horizontal.TScrollbar",
                                background=scrollbar_bg,
                                troughcolor=trough_color,
                                borderwidth=0,
                                relief="flat")

    def create_new_invoice(self):
        """Crear una nueva factura"""
        self.current_invoice_items = []
        self.invoice_counter += 1
        self.clear_current_invoice()
        
        # Actualizar encabezado
        for widget in self.tab_point_of_sale.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ctk.CTkFrame):
                                for greatgrand in grandchild.winfo_children():
                                    if isinstance(greatgrand, ctk.CTkLabel) and "FACTURA #" in greatgrand.cget("text"):
                                        greatgrand.configure(text=f"FACTURA #{self.invoice_counter}")
        
        self.tab_control.select(self.tab_point_of_sale)
        ModernMessageBox.showinfo("Nueva Factura", f"Factura #{self.invoice_counter} creada")
        self.save_data()

    def add_product_to_invoice(self, event=None):
        """Agregar producto seleccionado a la factura"""
        selection = self.pos_tree.selection()
        if not selection:
            return
        
        item = self.pos_tree.item(selection[0])
        # Obtener id real y buscar producto en inventario para usar datos canonicos
        try:
            product_id = int(item["values"][0])
        except Exception:
            product_id = None

        product = None
        if product_id is not None:
            for p in self.products:
                if p.get("id") == product_id:
                    product = p
                    break

        # Fallback a los valores de la tabla
        product_name = item["values"][1]
        price = float(product.get("price", 0)) if product else 0.0
        
        # Diálogo para cantidad
        dialog = ctk.CTkToplevel(self)
        dialog.title("Agregar Producto")
        dialog.geometry("300x250")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        ctk.CTkLabel(dialog, text=product_name, font=("Segoe UI", 12, "bold")).pack(pady=10)
        ctk.CTkLabel(dialog, text=f"Precio: ${price:.2f}").pack()
        
        ctk.CTkLabel(dialog, text="Cantidad:").pack(pady=(10, 0))
        qty_entry = ctk.CTkEntry(dialog)
        qty_entry.insert(0, "1")
        qty_entry.pack(pady=5)
        
        def add_with_qty():
            try:
                qty = int(qty_entry.get())
                if qty <= 0:
                    ModernMessageBox.showerror("Error", "La cantidad debe ser mayor a 0", parent=dialog)
                    return
                
                # Verificar stock
                inv_product = None
                for p in self.products:
                    if p["name"] == product_name or p.get("id") == product_id:
                        inv_product = p
                        
                        # Calcular cantidad ya existente en la factura para este producto
                        already_in_invoice = sum(item["quantity"] for item in self.current_invoice_items 
                                              if item["product"] == product_name)
                        
                        total_requested = already_in_invoice + qty
                        
                        if p["stock"] < total_requested:
                            ModernMessageBox.showwarning(
                                "Stock Insuficiente",
                                f"Stock disponible: {p['stock']}\nEn factura: {already_in_invoice}\nTotal solicitado: {total_requested}",
                                parent=dialog
                            )
                            return
                        break

                unit_price = inv_product.get("price") if inv_product else price

                # Agrupar si ya existe el mismo producto en la factura (por nombre y precio)
                for existing in self.current_invoice_items:
                    if (existing["product"] == product_name and
                        existing.get("price") == unit_price):
                        existing["quantity"] += qty
                        existing["total"] = existing["quantity"] * unit_price
                        break
                else:
                    self.current_invoice_items.append({
                        "product": product_name,
                        "quantity": qty,
                        "price": unit_price,
                        "total": unit_price * qty
                    })

                self.refresh_invoice_tree()
                safe_destroy(dialog)
                
            except ValueError:
                ModernMessageBox.showerror("Error", "Cantidad inválida", parent=dialog)
        
        # Vincular tecla Enter
        dialog.bind("<Return>", lambda e: add_with_qty())

        ctk.CTkButton(dialog, text="Agregar", command=add_with_qty).pack(pady=20)

    def add_item_manual(self):
        """Agregar item manualmente (Agrupar)"""
        # Verificar si hay selección en el POS
        selection = self.pos_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Atención", "Seleccione un producto en la tabla de ventas para agrupar.")
            return

        sel_item = self.pos_tree.item(selection[0])
        try:
            sel_id = int(sel_item["values"][0])
            desc = str(sel_item["values"][1])
        except Exception:
            ModernMessageBox.showerror("Error", "No se pudo identificar el producto seleccionado.")
            return

        # Encontrar el producto en la lista para obtener el precio actual
        matched_product = next((p for p in self.products if p.get("id") == sel_id), None)
        if not matched_product:
            ModernMessageBox.showerror("Error", "Producto no encontrado en la base de datos local.")
            return

        unit_price = float(matched_product.get("price", 0))

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Agrupar: {desc}")
        dialog.geometry("350x200")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        # Centrar
        dialog.update_idletasks()
        dw, dh = 350, 200
        dx = self.winfo_x() + (self.winfo_width() // 2) - (dw // 2)
        dy = self.winfo_y() + (self.winfo_height() // 2) - (dh // 2)
        dialog.geometry(f"{dw}x{dh}+{dx}+{dy}")

        ctk.CTkLabel(dialog, text=f"Producto: {desc}", font=("Segoe UI", 12, "bold")).pack(pady=(20, 10))
        
        ctk.CTkLabel(dialog, text="Cantidad adicional:").pack(pady=(5, 0))
        qty_entry = ctk.CTkEntry(dialog, width=100, justify="center")
        qty_entry.insert(0, "1")
        qty_entry.pack(pady=5)
        qty_entry.focus()
        
        def add_manual_item():
            try:
                qty_text = qty_entry.get()
                if not qty_text: return
                qty = int(qty_text)

                if qty <= 0:
                    ModernMessageBox.showerror("Error", "La cantidad debe ser mayor a 0", parent=dialog)
                    return

                # Verificar stock
                total_requested = qty
                # Calcular cantidad ya existente en la factura para este producto
                already_in_invoice = sum(item["quantity"] for item in self.current_invoice_items 
                                      if item["product"] == desc)
                total_requested += already_in_invoice

                if matched_product["stock"] < total_requested:
                    ModernMessageBox.showwarning(
                        "Stock Insuficiente",
                        f"Stock disponible: {matched_product['stock']}\nEn factura: {already_in_invoice}\nTotal solicitado: {total_requested}",
                        parent=dialog
                    )
                    return

                # Agrupar si ya existe (por descripción y precio)
                for existing in self.current_invoice_items:
                    if (existing["product"] == desc and
                        existing.get("price") == unit_price):
                        existing["quantity"] += qty
                        existing["total"] = existing["quantity"] * unit_price
                        break
                else:
                    self.current_invoice_items.append({
                        "product": desc,
                        "quantity": qty,
                        "price": unit_price,
                        "total": unit_price * qty
                    })

                self.refresh_invoice_tree()
                safe_destroy(dialog)
                
            except ValueError:
                ModernMessageBox.showerror("Error", "Ingrese una cantidad válida", parent=dialog)
        
        qty_entry.bind("<Return>", lambda e: add_manual_item())
        ctk.CTkButton(dialog, text="Confirmar", command=add_manual_item, fg_color="#059669", hover_color="#047857").pack(pady=15)

    def refresh_invoice_tree(self):
        """Refrescar la tabla de items de la factura"""
        # Limpiar tabla
        for item in self.invoice_tree.get_children():
            self.invoice_tree.delete(item)
        
        # Agregar items
        subtotal = 0
        for idx, item in enumerate(self.current_invoice_items):
            self.invoice_tree.insert("", "end", values=(
                item["product"],
                item["quantity"],
                f"${item['price']:.2f}",
                f"${item['total']:.2f}"
            ))
            subtotal += item["total"]

        # Calcular impuestos y total (aplica IVA sobre el subtotal)
        tax = subtotal * self.iva_rate
        total = subtotal + tax
        
        # Actualizar labels
        self.subtotal_label.configure(text=f"Subtotal: ${subtotal:.2f}")
        self.tax_label.configure(text=f"IVA ({self.iva_rate*100:.0f}%): ${tax:.2f}")
        self.total_label.configure(text=f"TOTAL: ${total:.2f}")

    def remove_selected_invoice_item(self, event=None):
        """Eliminar el o los items seleccionados de la factura actual"""
        selection = self.invoice_tree.selection()
        if not selection:
            return
        
        # Obtener los índices de los items seleccionados en orden descendente para eliminarlos de forma segura
        indices = sorted([self.invoice_tree.index(item) for item in selection], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.current_invoice_items):
                self.current_invoice_items.pop(idx)
        
        # Refrescar vista
        self.refresh_invoice_tree()

    def clear_current_invoice(self):
        """Limpiar la factura actual"""
        self.current_invoice_items = []
        self.client_var.set("")
        self.refresh_invoice_tree()
        self.invoice_date_label.configure(text=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    def process_payment(self):
        """Procesar pago de la factura"""
        if not self.current_invoice_items:
            ModernMessageBox.showwarning("Factura Vacía", "Agregue productos a la factura primero")
            return

        client_name = self.client_var.get().strip()
        registered_client_names = {client.get("name", "").strip() for client in self.clients}
        if not client_name or client_name not in registered_client_names:
            ModernMessageBox.showwarning(
                "Cliente requerido",
                "Seleccione un cliente antes de procesar el pago."
            )
            self.client_combobox.focus_set()
            return
        
        # Calcular total y IVA
        subtotal = sum(item["total"] for item in self.current_invoice_items)
        tax = subtotal * self.iva_rate
        total = subtotal + tax
        
        # Diálogo de pago
        dialog = ctk.CTkToplevel(self)
        dialog.title("Procesar Pago")
        dialog.geometry("800x700")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        # Información del total
        ctk.CTkLabel(dialog, text="DETALLE DE PAGO", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        info_frame = ctk.CTkFrame(dialog)
        info_frame.pack(fill="x", padx=20, pady=30)
        
        ctk.CTkLabel(info_frame, text="Subtotal:", font=("Segoe UI", 11)).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"${subtotal:.2f}", font=("Segoe UI", 11)).pack(anchor="e")
        
        ctk.CTkLabel(info_frame, text=f"IVA ({self.iva_rate*100:.0f}%):", font=("Segoe UI", 11)).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"${tax:.2f}", font=("Segoe UI", 11)).pack(anchor="e")
        
        ctk.CTkLabel(info_frame, text="TOTAL A PAGAR:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"${total:.2f}", font=("Segoe UI", 14, "bold")).pack(anchor="e")
        
        # Mostrar en bolívares
        ctk.CTkLabel(info_frame, text="Subtotal en BS:", font=("Segoe UI", 11)).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"Bs.{subtotal * self.exchange_rate:,.2f}", font=("Segoe UI", 11)).pack(anchor="e")
        
        ctk.CTkLabel(info_frame, text=f"IVA en BS ({self.iva_rate*100:.0f}%):", font=("Segoe UI", 11)).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"Bs.{tax * self.exchange_rate:,.2f}", font=("Segoe UI", 11)).pack(anchor="e")
        
        ctk.CTkLabel(info_frame, text="TOTAL EN BOLÍVARES:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ctk.CTkLabel(info_frame, text=f"Bs.{total * self.exchange_rate:,.2f}", font=("Segoe UI", 14, "bold")).pack(anchor="e")
        
        # Método de pago
        ctk.CTkLabel(dialog, text="Método de Pago:", font=("Segoe UI", 11)).pack(pady=(10, 0))
        
        payment_method = tk.StringVar(value="Efectivo")
        credit_var = tk.IntVar(value=0)
        
        methods_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        methods_frame.pack(pady=5)
        
        ctk.CTkRadioButton(methods_frame, text="Efectivo", variable=payment_method, value="Efectivo").pack(side="left", padx=10)
        ctk.CTkRadioButton(methods_frame, text="Tarjeta", variable=payment_method, value="Tarjeta").pack(side="left", padx=10)
        ctk.CTkRadioButton(methods_frame, text="Transferencia", variable=payment_method, value="Transferencia").pack(side="left", padx=10)
        ctk.CTkRadioButton(methods_frame, text="Pago móvil", variable=payment_method, value="Pago móvil").pack(side="left", padx=10)
        ctk.CTkRadioButton(methods_frame, text="Divisas", variable=payment_method, value="Divisas").pack(side="left", padx=10)

        ctk.CTkLabel(dialog, text="").pack()
        
        due_date_label = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 11, "italic"), text_color="#2563EB")
        
        def update_due_date_preview(*args):
            if credit_var.get():
                client_name = self.client_var.get()
                client_obj = next((c for c in self.clients if c.get("name") == client_name), None)
                days = client_obj.get("credit_days", 0) if client_obj else 0
                due_dt = datetime.now() + timedelta(days=days)
                due_date_label.configure(text=f"Fecha de vencimiento: {due_dt.strftime('%d/%m/%Y')} ({days} días)")
                due_date_label.pack()
            else:
                due_date_label.pack_forget()

        credit_check = ctk.CTkCheckBox(dialog, text="Venta a Crédito", variable=credit_var, command=update_due_date_preview)
        credit_check.pack()
        
        # Trigger preview if already selected or client changes
        self.client_var.trace_add("write", update_due_date_preview)
        
        def complete_payment():
            # Crear factura
            is_credit = bool(credit_var.get())
            due_date = None
            balance = 0.0
            client_name = self.client_var.get()
            if is_credit:
                # calcular fecha de vencimiento según días de crédito del cliente
                client_obj = next((c for c in self.clients if c.get("name") == client_name), None)
                days = client_obj.get("credit_days", 0) if client_obj else 0
                due_dt = datetime.now() + timedelta(days=days)
                due_date = due_dt.strftime("%d/%m/%Y")
                status = "Pendiente"
                balance = total
                payment_method_value = "Pendiente"
            else:
                status = "Pagada"
                payment_method_value = payment_method.get()

            invoice = {
                "number": self.invoice_counter,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "client": client_name,
                "items": self.current_invoice_items.copy(),
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "payment_method": payment_method_value,
                "status": status,
                "due_date": due_date,
                "is_credit": int(is_credit),
                "balance": balance,
                "exchange_rate": self.exchange_rate,
                "payments": [] ,
                "documents": []
            }
            
            # Actualizar stock (con verificación final de seguridad)
            for item in self.current_invoice_items:
                for product in self.products:
                    if product["name"] == item["product"]:
                        if product["stock"] < item["quantity"]:
                            ModernMessageBox.showerror("Error Crítico de Stock", 
                                               f"El producto '{item['product']}' ya no tiene suficiente stock disponible.\n"
                                               f"Disponible: {product['stock']}, Requerido: {item['quantity']}.\n"
                                               "Por favor, revise la factura.")
                            return # Abortar el pago
                        product["stock"] -= item["quantity"]
                        break
            
            self.invoices.append(invoice)
            # Si es crédito, actualizar saldo del cliente
            if invoice.get("is_credit"):
                client_obj = next((c for c in self.clients if c.get("name") == invoice.get("client")), None)
                if client_obj is not None:
                    client_obj["balance"] = float(client_obj.get("balance", 0.0)) + float(invoice.get("balance", 0.0))
            self.save_data()
            self.refresh_inventory()
            self.refresh_pos_products()
            self.refresh_invoices()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after payment
            
            ModernMessageBox.showinfo("Pago Completado", f"Factura #{self.invoice_counter} procesada exitosamente", parent=dialog)
            safe_destroy(dialog)
            self.create_new_invoice()
        
        # Vincular tecla Enter al diálogo
        dialog.bind("<Return>", lambda e: complete_payment())
        
        ctk.CTkButton(dialog, text="COMPLETAR PAGO", command=complete_payment, 
                     fg_color="#059669", hover_color="#047857",
                     corner_radius=8,
                     height=40, font=("Segoe UI", 12, "bold")).pack(pady=20)

    def open_settings_dialog(self):
        """Abrir diálogo de configuración"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Configuración del Sistema")
        dialog.geometry("560x760")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        ctk.CTkLabel(dialog, text="CONFIGURACIÓN DEL SISTEMA", font=("Segoe UI", 16, "bold")).pack(pady=(15, 10))
        
        # ---- DATOS DE LA TIENDA ----
        store_label = ctk.CTkLabel(dialog, text="DATOS DE LA TIENDA", font=("Segoe UI", 13, "bold"), text_color="#2563EB")
        store_label.pack(pady=(5, 5))

        store_frame = ctk.CTkFrame(dialog, fg_color="#F8FAFC")
        store_frame.pack(fill="x", padx=20, pady=(0, 8))

        # Nombre de la tienda
        name_frame = ctk.CTkFrame(store_frame, fg_color="transparent")
        name_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(name_frame, text="Nombre de la Tienda:", font=("Segoe UI", 11)).pack(side="left", padx=5)
        store_name_entry = ctk.CTkEntry(name_frame, width=250)
        store_name_entry.insert(0, getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS'))
        store_name_entry.pack(side="right", padx=5, fill="x", expand=True)

        # RIF
        rif_frame = ctk.CTkFrame(store_frame, fg_color="transparent")
        rif_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(rif_frame, text="RIF de la Tienda:", font=("Segoe UI", 11)).pack(side="left", padx=5)
        rif_entry = ctk.CTkEntry(rif_frame, width=250)
        rif_entry.insert(0, getattr(self, 'company_rif', '') if getattr(self, 'company_rif', '') != 'RIF: N/A' else '')
        rif_entry.pack(side="right", padx=5, fill="x", expand=True)

        # Domicilio Fiscal
        domicile_frame = ctk.CTkFrame(store_frame, fg_color="transparent")
        domicile_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(domicile_frame, text="Domicilio Fiscal:", font=("Segoe UI", 11)).pack(side="left", padx=5)
        address_entry = ctk.CTkEntry(domicile_frame, width=250)
        address_entry.insert(0, getattr(self, 'company_address', '') if getattr(self, 'company_address', '') != 'Domicilio fiscal: N/A' else '')
        address_entry.pack(side="right", padx=5, fill="x", expand=True)

        # Teléfono
        phone_frame = ctk.CTkFrame(store_frame, fg_color="transparent")
        phone_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(phone_frame, text="Teléfono:", font=("Segoe UI", 11)).pack(side="left", padx=5)
        phone_entry = ctk.CTkEntry(phone_frame, width=250)
        phone_entry.insert(0, getattr(self, 'company_phone', '') if getattr(self, 'company_phone', '') != 'Teléfono: N/A' else '')
        phone_entry.pack(side="right", padx=5, fill="x", expand=True)

        # Separador
        ctk.CTkLabel(dialog, text="" ).pack()

        # IVA
        iva_frame = ctk.CTkFrame(dialog)
        iva_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(iva_frame, text="IVA (%):", font=("Segoe UI", 12)).pack(side="left", padx=10, pady=5)
        iva_entry = ctk.CTkEntry(iva_frame, width=100)
        iva_entry.insert(0, f"{self.iva_rate * 100:.0f}")
        iva_entry.pack(side="right", padx=10, pady=5)
        
        # Tasa de cambio
        exchange_frame = ctk.CTkFrame(dialog)
        exchange_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(exchange_frame, text="Tasa USD a VES:", font=("Segoe UI", 12)).pack(side="left", padx=10, pady=5)
        exchange_entry = ctk.CTkEntry(exchange_frame, width=100)
        exchange_entry.insert(0, f"{self.exchange_rate:.2f}")
        exchange_entry.pack(side="right", padx=10, pady=5)
        
        # Botón para consultar tasa oficial BCV
        query_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        query_frame.pack(fill="x", padx=20, pady=5)
        
        # Status Label para la consulta de tasa BCV
        status_label = ctk.CTkLabel(dialog, text="Consulte la tasa oficial BCV en tiempo real", font=("Segoe UI", 11, "italic"), text_color="#64748B")
        
        def fetch_bcv():
            status_label.configure(text="Consultando tasa oficial BCV...", text_color="#2563EB")
            bcv_btn.configure(state="disabled")
            
            import threading
            def run():
                rate, err = self.query_dolar_api("oficial")
                
                def update_gui():
                    bcv_btn.configure(state="normal")
                    if rate is not None:
                        exchange_entry.delete(0, "end")
                        exchange_entry.insert(0, f"{rate:.2f}")
                        status_label.configure(text=f"Tasa BCV obtenida: {rate:.2f} VES", text_color="#059669")
                    else:
                        status_label.configure(text=f"Error: {err}", text_color="#DC2626")
                        
                dialog.after(0, update_gui)
            
            threading.Thread(target=run, daemon=True).start()

        bcv_btn = ctk.CTkButton(
            query_frame, 
            text="Consultar Tasa Oficial BCV 🏛️", 
            command=fetch_bcv, 
            height=36,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=("Segoe UI", 12, "bold")
        )
        bcv_btn.pack(fill="x", padx=10, pady=5)
        
        status_label.pack(pady=(0, 5))
        
        # Controles de Auto-actualización (Exclusivo BCV)
        auto_frame = ctk.CTkFrame(dialog)
        auto_frame.pack(fill="x", padx=20, pady=5)
        
        auto_var = tk.BooleanVar(value=getattr(self, "auto_update_rate", False))
        auto_cb = ctk.CTkCheckBox(auto_frame, text="Auto-actualizar tasa oficial BCV automáticamente", variable=auto_var, font=("Segoe UI", 12))
        auto_cb.pack(side="left", padx=10, pady=5)
        
        # Inclusión de facturas pendientes en Dashboard
        pending_frame = ctk.CTkFrame(dialog)
        pending_frame.pack(fill="x", padx=20, pady=5)
        
        pending_var = tk.BooleanVar(value=self.include_pending_in_dashboard)
        pending_cb = ctk.CTkCheckBox(pending_frame, text="Incluir facturas pendientes en dashboard", 
                                   variable=pending_var, font=("Segoe UI", 12))
        pending_cb.pack(side="left", padx=10, pady=5)

        folder_frame = ctk.CTkFrame(dialog)
        folder_frame.pack(fill="x", padx=20, pady=(10, 5))
        
        ctk.CTkLabel(folder_frame, text="Exportaciones:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            folder_frame,
            text="Excel",
            command=self.open_excel_export_folder,
            width=130,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="right", padx=10)
        ctk.CTkButton(
            folder_frame,
            text="Facturas",
            command=self.open_pdf_export_folder,
            width=130,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="right", padx=10)
        ctk.CTkButton(
            folder_frame,
            text="Notas de Entrega",
            command=self.open_delivery_note_export_folder,
            width=130,
            fg_color="#0EA5E9",
            hover_color="#0284C7"
        ).pack(side="right", padx=10)
        
        def save_settings():
            try:
                self.iva_rate = float(iva_entry.get()) / 100
                self.exchange_rate = float(exchange_entry.get())
                self.include_pending_in_dashboard = pending_var.get()
                self.auto_update_rate = auto_var.get()
                self.rate_source = "oficial"
                
                # Guardar datos de la tienda
                self.company_name = store_name_entry.get().strip() or "SISTEMA DE FACTURACIÓN AS"
                self.company_rif = rif_entry.get().strip() or "RIF: N/A"
                self.company_address = address_entry.get().strip() or "Domicilio fiscal: N/A"
                self.company_phone = phone_entry.get().strip() or "Teléfono: N/A"
                
                self.save_data()
                self.update_dashboard() # Auto-refresh dashboard after settings change
                
                # Si se activa la auto-actualización, realizar una consulta inmediata
                if self.auto_update_rate:
                    self.trigger_immediate_auto_update()
                    
                ModernMessageBox.showinfo("Configuración Guardada", "Los ajustes han sido guardados exitosamente", parent=dialog)
                safe_destroy(dialog)
            except ValueError:
                ModernMessageBox.showerror("Error", "Ingrese valores numéricos válidos", parent=dialog)
        
        # Vincular teclas Enter y Escape
        dialog.bind("<Return>", lambda e: save_settings())
        dialog.bind("<Escape>", lambda e: safe_destroy(dialog))

        ctk.CTkButton(dialog, text="GUARDAR CONFIGURACIÓN", command=save_settings, 
                     fg_color="#059669", hover_color="#047857",
                     corner_radius=8,
                     height=40, font=("Segoe UI", 12, "bold")).pack(pady=15)

    def open_new_product_dialog(self):
        """Abrir diálogo para nuevo producto"""
        if not self._require_admin("crear productos"):
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nuevo Producto")
        dialog.geometry("500x550")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        # Campos del formulario
        fields = [
            ("Código", "entry"),
            ("Nombre", "entry"),
            ("Categoría", "combobox"),
            ("Precio de Compra", "entry"),
            ("Precio de Venta", "entry"),
            ("Stock Inicial", "entry"),
            ("Stock Mínimo", "entry"),
            ("Ubicación", "entry"),
            ("Proveedor", "entry"),
            ("Notas", "text"),
        ]
    
        
        entries = {}
        row = 0
        
        for field in fields:
            ctk.CTkLabel(dialog, text=f"{field[0]}:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
            
            if field[1] == "entry":
                entry = ctk.CTkEntry(dialog, width=300)
                entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = entry
            
            elif field[1] == "combobox":
                category_values = sorted(list(set(
                    str(p.get("category", "")).strip()
                    for p in self.products
                    if str(p.get("category", "")).strip()
                )))
                category_values.append("Añadir+")
                combo = ttk.Combobox(dialog, values=category_values, state="readonly", width=27)
                combo.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                combo.set(category_values[0] if len(category_values) > 1 else "Añadir+")

                def add_category(event=None, category_combo=combo):
                    if category_combo.get() != "Añadir+":
                        return
                    new_category = simpledialog.askstring(
                        "Nueva categoría",
                        "Ingrese el nombre de la nueva categoría:",
                        parent=dialog
                    )
                    new_category = (new_category or "").strip()
                    values = list(category_combo["values"])
                    if not new_category:
                        category_combo.set(values[0] if len(values) > 1 else "Añadir+")
                        return

                    values = [value for value in values if value != "Añadir+"]
                    if new_category not in values:
                        values.append(new_category)
                    values.sort()
                    values.append("Añadir+")
                    category_combo.configure(values=values)
                    category_combo.set(new_category)

                combo.bind("<<ComboboxSelected>>", add_category)
                entries[field[0]] = combo
            
            elif field[1] == "text":
                text_widget = ctk.CTkTextbox(dialog, width=300, height=60)
                text_widget.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = text_widget
            
            row += 1
        
        dialog.grid_columnconfigure(1, weight=1)
        
        def save_product():
            try:
                product = {
                    "id": max((p["id"] for p in self.products), default=0) + 1,
                    "code": entries["Código"].get(),
                    "name": entries["Nombre"].get(),
                    "category": entries["Categoría"].get(),
                    "purchase_price": float(entries["Precio de Compra"].get() or 0),
                    "price": float(entries["Precio de Venta"].get() or 0),
                    "stock": int(entries["Stock Inicial"].get() or 0),
                    "min_stock": int(entries["Stock Mínimo"].get() or 0),
                    "location": entries["Ubicación"].get(),
                    "supplier": entries["Proveedor"].get(),
                    "notes": entries["Notas"].get("1.0", "end-1c") if isinstance(entries["Notas"], ctk.CTkTextbox) else ""
                }
                
                # Validaciones
                if not product["name"]:
                    ModernMessageBox.showerror("Error", "El nombre es requerido", parent=dialog)
                    return
                
                self.products.append(product)
                self.save_data()
                self.refresh_inventory()
                self.refresh_pos_products()
                self.update_counters()
                self.update_dashboard() # Auto-refresh dashboard after new product
                
                ModernMessageBox.showinfo("Éxito", "Producto registrado correctamente", parent=dialog)
                safe_destroy(dialog)
                
            except ValueError:
                ModernMessageBox.showerror("Error", "Valores numéricos inválidos", parent=dialog)
        
        # Vincular tecla Enter
        dialog.bind("<Return>", lambda e: save_product())

        button_frame = ctk.CTkFrame(dialog)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(button_frame, text="Guardar", command=save_product, width=120).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, width=120, fg_color="#64748B").pack(side="left", padx=10)

    def open_edit_product_dialog(self):
        """Abrir diálogo para editar producto (estrictamente de uno en uno)"""
        if not self._require_admin("editar el inventario"):
            return
        selection = self.inventory_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione un producto para editar")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "La edición debe realizarse estrictamente de uno en uno. Por favor, seleccione un solo producto.")
            return
        
        item = self.inventory_tree.item(selection[0])
        product_id = int(item["values"][0])
        
        # Buscar producto
        product = None
        for p in self.products:
            if p["id"] == product_id:
                product = p
                break
        
        if not product:
            ModernMessageBox.showerror("Error", "Producto no encontrado")
            return
        
        # Diálogo de edición (similar al de nuevo producto pero con datos cargados)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Producto")
        dialog.geometry("500x550")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        fields = [
            ("Código", "entry", product["code"]),
            ("Nombre", "entry", product["name"]),
            ("Categoría", "combobox", ["Electrónica", "Ropa", "Alimentos", "Hogar", "Oficina", "Otros"], product["category"]),
            ("Precio de Compra", "entry", str(product["purchase_price"])),
            ("Precio de Venta", "entry", str(product["price"])),
            ("Stock Actual", "entry", str(product["stock"])),
            ("Stock Mínimo", "entry", str(product["min_stock"])),
            ("Ubicación", "entry", product["location"]),
            ("Proveedor", "entry", product["supplier"]),
            ("Notas", "text", product["notes"]),
        ]
        
        
        entries = {}
        row = 0
        
        for field in fields:
            ctk.CTkLabel(dialog, text=f"{field[0]}:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
            
            if field[1] == "entry":
                entry = ctk.CTkEntry(dialog, width=300)
                safe_widget_insert(entry, 0, field[2])
                entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = entry
            
            elif field[1] == "combobox":
                combo = ttk.Combobox(dialog, values=field[2], state="readonly", width=27)
                combo.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                try:
                    combo.set("") if len(field) < 4 else combo.set(str(field[3] or ""))
                except Exception:
                    try:
                        combo.set("")
                    except Exception:
                        pass
                entries[field[0]] = combo
            
            elif field[1] == "text":
                text_widget = ctk.CTkTextbox(dialog, width=300, height=60)
                safe_widget_insert(text_widget, "1.0", field[2])
                text_widget.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = text_widget
            
            
            row += 1
        
        dialog.grid_columnconfigure(1, weight=1)
        
        def update_product():
            try:
                product["code"] = entries["Código"].get()
                product["name"] = entries["Nombre"].get()
                product["category"] = entries["Categoría"].get()
                product["purchase_price"] = float(entries["Precio de Compra"].get() or 0)
                product["price"] = float(entries["Precio de Venta"].get() or 0)
                product["stock"] = int(entries["Stock Actual"].get() or 0)
                product["min_stock"] = int(entries["Stock Mínimo"].get() or 0)
                product["location"] = entries["Ubicación"].get()
                product["supplier"] = entries["Proveedor"].get()
                product["notes"] = entries["Notas"].get("1.0", "end-1c") if isinstance(entries["Notas"], ctk.CTkTextbox) else ""
                
                self.save_data()
                self.refresh_inventory()
                self.refresh_pos_products()
                self.update_dashboard() # Auto-refresh dashboard after edit
                
                ModernMessageBox.showinfo("Éxito", "Producto actualizado correctamente", parent=dialog)
                safe_destroy(dialog)
                
            except ValueError:
                ModernMessageBox.showerror("Error", "Valores numéricos inválidos", parent=dialog)
        
        # Vincular teclas Enter y Escape
        dialog.bind("<Return>", lambda e: update_product())
        dialog.bind("<Escape>", lambda e: safe_destroy(dialog))

        button_frame = ctk.CTkFrame(dialog)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(button_frame, text="Actualizar", command=update_product, width=120).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, width=120, fg_color="#64748B").pack(side="left", padx=10)

    def delete_product(self):
        """Eliminar producto(s) seleccionado(s) permitiendo selección múltiple"""
        if not self._require_admin("eliminar productos del inventario"):
            return
        selection = self.inventory_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione al menos un producto para eliminar")
            return
        
        if len(selection) == 1:
            item = self.inventory_tree.item(selection[0])
            product_name = item["values"][2]
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación",
                f"¿Está seguro de eliminar el producto '{product_name}'?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        else:
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación Múltiple",
                f"¿Está seguro de eliminar los {len(selection)} productos seleccionados?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        
        if confirm:
            ids_to_delete = set()
            for sel in selection:
                try:
                    ids_to_delete.add(int(self.inventory_tree.item(sel)["values"][0]))
                except Exception:
                    pass
            self.products = [p for p in self.products if p["id"] not in ids_to_delete]
            self.save_data()
            self.refresh_inventory()
            self.refresh_pos_products()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after delete
            if len(ids_to_delete) == 1:
                ModernMessageBox.showinfo("Éxito", "Producto eliminado correctamente")
            else:
                ModernMessageBox.showinfo("Éxito", f"{len(ids_to_delete)} productos eliminados correctamente")

    def open_new_client_dialog(self):
        """Abrir diálogo para nuevo cliente"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nuevo Cliente")
        dialog.geometry("500x500")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        fields = [
            ("Nombre/Razón Social", "entry"),
            ("RIF/Cédula de Identidad (CI)", "entry"),
            ("Tipo", "combobox", ["General", "Público", "Empresa", "Distribuidor"]),
            ("Teléfono", "entry"),
            ("Email", "entry"),
            ("Dirección", "text"),
            ("Días de crédito", "entry"),
            ("Ciudad", "entry"),
            ("Estado", "entry"),
            ("Código Postal", "entry"),
            ("Notas", "text")
        ]
        
        entries = {}
        row = 0
        
        for field in fields:
            ctk.CTkLabel(dialog, text=f"{field[0]}:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
            
            if field[1] == "entry":
                entry = ctk.CTkEntry(dialog, width=300)
                entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = entry
            
            elif field[1] == "combobox":
                combo = ttk.Combobox(dialog, values=field[2], state="readonly", width=27)
                combo.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                combo.set(field[2][0])
                entries[field[0]] = combo
            
            elif field[1] == "text":
                text_widget = ctk.CTkTextbox(dialog, width=300, height=40)
                text_widget.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = text_widget
            
            
            row += 1
        
        dialog.grid_columnconfigure(1, weight=1)
        
        def save_client():
            try:
                client = {
                    "id": max((c["id"] for c in self.clients), default=0) + 1,
                    "name": entries["Nombre/Razón Social"].get(),
                    "rif_ci": format_ci_rif(entries["RIF/Cédula de Identidad (CI)"].get()),
                    "type": entries["Tipo"].get(),
                    "phone": entries["Teléfono"].get(),
                    "email": entries["Email"].get(),
                    "address": entries["Dirección"].get("1.0", "end-1c") if isinstance(entries["Dirección"], ctk.CTkTextbox) else "",
                    "credit_days": int(entries.get("Días de crédito").get() or 0) if entries.get("Días de crédito") else 0,
                    "credit_start_date": datetime.now().strftime("%d/%m/%Y") if int(entries.get("Días de crédito").get() or 0) > 0 else None,
                    "city": entries["Ciudad"].get(),
                    "state": entries["Estado"].get(),
                    "postal_code": entries["Código Postal"].get(),
                    "notes": entries["Notas"].get("1.0", "end-1c") if isinstance(entries["Notas"], ctk.CTkTextbox) else ""
                }
                
                if not client["name"]:
                    ModernMessageBox.showerror("Error", "El nombre es requerido", parent=dialog)
                    return
                
                self.clients.append(client)
                self.save_data()
                self.refresh_clients()
                self.update_client_combobox()
                self.update_counters()
                self.update_dashboard() # Auto-refresh dashboard after new client
                
                ModernMessageBox.showinfo("Éxito", "Cliente registrado correctamente", parent=dialog)
                safe_destroy(dialog)
                
            except Exception as e:
                ModernMessageBox.showerror("Error", f"Error al guardar: {str(e)}", parent=dialog)
        
        # Vincular tecla Enter
        dialog.bind("<Return>", lambda e: save_client())

        button_frame = ctk.CTkFrame(dialog)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(button_frame, text="Guardar", command=save_client, width=120).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, width=120, fg_color="#64748B").pack(side="left", padx=10)

    def open_edit_client_dialog(self):
        """Abrir diálogo para editar cliente (estrictamente de uno en uno)"""
        if not self._require_admin("editar clientes"):
            return
        selection = self.clients_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione un cliente para editar")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "La edición debe realizarse estrictamente de uno en uno. Por favor, seleccione un solo cliente.")
            return
        
        item = self.clients_tree.item(selection[0])
        client_id = int(item["values"][0])
        
        # Buscar cliente
        client = None
        for c in self.clients:
            if c["id"] == client_id:
                client = c
                break
        
        if not client:
            ModernMessageBox.showerror("Error", "Cliente no encontrado")
            return
        
        # Diálogo de edición
        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Cliente")
        dialog.geometry("500x500")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        fields = [
            ("Nombre/Razón Social", "entry", client["name"]),
            ("RIF/Cédula de Identidad (CI)", "entry", client["rif_ci"]),
            ("Tipo", "combobox", ["General", "Público", "Empresa", "Distribuidor"], client["type"]),
            ("Teléfono", "entry", client["phone"]),
            ("Email", "entry", client["email"]),
            ("Dirección", "text", client["address"]),
            ("Días de crédito", "entry", str(client.get("credit_days", 0))),
            ("Ciudad", "entry", client["city"]),
            ("Estado", "entry", client["state"]),
            ("Código Postal", "entry", client["postal_code"]),
            ("Notas", "text", client["notes"])
        ]
        
        entries = {}
        row = 0
        
        for field in fields:
            ctk.CTkLabel(dialog, text=f"{field[0]}:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
            
            if field[1] == "entry":
                entry = ctk.CTkEntry(dialog, width=300)
                safe_widget_insert(entry, 0, field[2])
                entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = entry

            elif field[1] == "combobox":
                combo = ttk.Combobox(dialog, values=field[2], state="readonly", width=27)
                combo.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                try:
                    combo.set("") if len(field) < 4 else combo.set(str(field[3] or ""))
                except Exception:
                    try:
                        combo.set("")
                    except Exception:
                        pass
                entries[field[0]] = combo

            elif field[1] == "text":
                text_widget = ctk.CTkTextbox(dialog, width=300, height=40)
                safe_widget_insert(text_widget, "1.0", field[2])
                text_widget.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
                entries[field[0]] = text_widget
            
            row += 1
        
        dialog.grid_columnconfigure(1, weight=1)
        
        def update_client():
            try:
                client["name"] = entries["Nombre/Razón Social"].get()
                client["rif_ci"] = format_ci_rif(entries["RIF/Cédula de Identidad (CI)"].get())
                client["type"] = entries["Tipo"].get()
                client["phone"] = entries["Teléfono"].get()
                client["email"] = entries["Email"].get()
                client["address"] = entries["Dirección"].get("1.0", "end-1c") if isinstance(entries["Dirección"], ctk.CTkTextbox) else ""
                try:
                    client["credit_days"] = int(entries.get("Días de crédito").get() or 0) if entries.get("Días de crédito") else client.get("credit_days", 0)
                except Exception:
                    client["credit_days"] = client.get("credit_days", 0)
                
                if client.get("credit_days", 0) > 0 and not client.get("credit_start_date"):
                    client["credit_start_date"] = datetime.now().strftime("%d/%m/%Y")
                elif client.get("credit_days", 0) <= 0:
                    client["credit_start_date"] = None
                
                client["city"] = entries["Ciudad"].get()
                client["state"] = entries["Estado"].get()
                client["postal_code"] = entries["Código Postal"].get()
                client["notes"] = entries["Notas"].get("1.0", "end-1c") if isinstance(entries["Notas"], ctk.CTkTextbox) else ""
                
                self.save_data()
                self.refresh_clients()
                self.update_client_combobox()
                self.update_dashboard() # Auto-refresh dashboard after client edit
                
                ModernMessageBox.showinfo("Éxito", "Cliente actualizado correctamente", parent=dialog)
                safe_destroy(dialog)
                
            except Exception as e:
                ModernMessageBox.showerror("Error", f"Error al actualizar: {str(e)}", parent=dialog)
        
        # Vincular teclas Enter y Escape
        dialog.bind("<Return>", lambda e: update_client())
        dialog.bind("<Escape>", lambda e: safe_destroy(dialog))

        button_frame = ctk.CTkFrame(dialog)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(button_frame, text="Actualizar", command=update_client, width=120).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, width=120, fg_color="#64748B").pack(side="left", padx=10)

    def delete_client(self):
        """Eliminar cliente(s) seleccionado(s) permitiendo selección múltiple"""
        selection = self.clients_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione al menos un cliente para eliminar")
            return
        
        if len(selection) == 1:
            item = self.clients_tree.item(selection[0])
            client_name = item["values"][1]
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación",
                f"¿Está seguro de eliminar el cliente '{client_name}'?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        else:
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación Múltiple",
                f"¿Está seguro de eliminar los {len(selection)} clientes seleccionados?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        
        if confirm:
            ids_to_delete = set()
            for sel in selection:
                try:
                    ids_to_delete.add(int(self.clients_tree.item(sel)["values"][0]))
                except Exception:
                    pass
            self.clients = [c for c in self.clients if c["id"] not in ids_to_delete]
            self.save_data()
            self.refresh_clients()
            self.update_client_combobox()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after client delete
            if len(ids_to_delete) == 1:
                ModernMessageBox.showinfo("Éxito", "Cliente eliminado correctamente")
            else:
                ModernMessageBox.showinfo("Éxito", f"{len(ids_to_delete)} clientes eliminados correctamente")

    def add_client_from_pos(self):
        """Agregar cliente rápido desde el POS"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nuevo Cliente Rápido")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        ctk.CTkLabel(dialog, text="Nuevo Cliente", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        ctk.CTkLabel(dialog, text="Nombre:").pack(pady=(10, 0))
        name_entry = ctk.CTkEntry(dialog, width=300)
        name_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Teléfono:").pack(pady=(10, 0))
        phone_entry = ctk.CTkEntry(dialog, width=200)
        phone_entry.pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Email:").pack(pady=(10, 0))
        email_entry = ctk.CTkEntry(dialog, width=250)
        email_entry.pack(pady=5)
        
        def save_quick_client():
            name = name_entry.get()
            if not name:
                ModernMessageBox.showerror("Error", "El nombre es requerido", parent=dialog)
                return
            
            client = {
                "id": max((c["id"] for c in self.clients), default=0) + 1,
                "name": name,
                "phone": phone_entry.get(),
                "email": email_entry.get(),
                "type": "General"
            }
            
            self.clients.append(client)
            self.save_data()
            self.refresh_clients()
            self.update_client_combobox()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after quick client add
            
            self.client_var.set(name)
            ModernMessageBox.showinfo("Éxito", "Cliente agregado correctamente", parent=dialog)
            safe_destroy(dialog)
        
        # Vincular tecla Enter
        dialog.bind("<Return>", lambda e: save_quick_client())

        ctk.CTkButton(dialog, text="Guardar", command=save_quick_client).pack(pady=20)

    def quick_search_client_from_pos(self):
        """Buscar cliente rápido desde POS y asignarlo a la factura actual"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Buscar Cliente")
        dialog.geometry("450x400")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)

        ctk.CTkLabel(dialog, text="Buscar Cliente", font=("Segoe UI", 14, "bold")).pack(pady=8)
        search_entry = ctk.CTkEntry(dialog, width=360)
        search_entry.pack(pady=6)

        listbox = tk.Listbox(dialog, width=60, height=15)
        listbox.pack(padx=10, pady=6)

        def refresh_list(query=""):
            listbox.delete(0, tk.END)
            q = query.strip().lower()
            for c in self.clients:
                if not q or q in c.get("name", "").lower() or q in str(c.get("rif_ci", "")).lower():
                    display = f"{c.get('name')} -- {format_ci_rif(c.get('rif_ci',''))}"
                    listbox.insert(tk.END, display)

        def on_key(e=None):
            refresh_list(search_entry.get())

        def select_client(evt=None):
            sel = listbox.curselection()
            if not sel:
                return
            text = listbox.get(sel[0])
            name = text.split(" -- ")[0]
            self.client_var.set(name)
            safe_destroy(dialog)

        search_entry.bind("<KeyRelease>", on_key)
        listbox.bind("<Double-1>", select_client)
        # Vincular tecla Enter
        dialog.bind("<Return>", lambda e: select_client())

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=6)
        ctk.CTkButton(btn_frame, text="Seleccionar", command=select_client, width=120).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cerrar", command=dialog.destroy, width=120, fg_color="#64748B").pack(side="left", padx=6)

        refresh_list()

    def update_client_combobox(self):
        """Actualizar lista de clientes en el combobox"""
        client_names = [c["name"] for c in self.clients]
        self.client_combobox.configure(values=client_names)

    def generate_pdf_invoice(self, invoice_data=None, filename="factura.pdf"):
        """Generar una factura fiscal en formato carta, lista para imprimir."""
        if invoice_data is None:
            invoice_data = self.get_selected_invoice_data()

        if invoice_data is None and getattr(self, 'invoices', None):
            invoice_data = self.invoices[-1]

        if not invoice_data:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione una factura para generar el PDF.")
            return None

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            export_dir = os.path.join(base_dir, "Facturas")
            os.makedirs(export_dir, exist_ok=True)

            number = invoice_data.get('number', 'sin_numero')
            if not filename or filename == "factura.pdf":
                filename = f"Factura_{number}.pdf"

            filepath = os.path.join(export_dir, os.path.basename(filename))

            doc = SimpleDocTemplate(
                filepath,
                pagesize=letter,
                rightMargin=30,
                leftMargin=30,
                topMargin=28,
                bottomMargin=48,
            )
            styles = getSampleStyleSheet()
            def clean(value):
                return escape(str(value if value not in (None, '') else 'N/A'))

            def money(value, prefix='Bs. '):
                return f"{prefix}{float(value or 0):,.2f}"

            body_style = ParagraphStyle('InvoiceBody', parent=styles['Normal'], fontName='Helvetica', fontSize=8.2, leading=10, textColor=colors.HexColor('#1F2937'))
            small_style = ParagraphStyle('InvoiceSmall', parent=body_style, fontSize=7.3, leading=8.7)
            header_style = ParagraphStyle('InvoiceHeader', parent=body_style, fontSize=7.7, leading=9.3, alignment=2, textColor=colors.HexColor('#334155'))
            title_style = ParagraphStyle('InvoiceTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=17, leading=19, textColor=colors.HexColor('#0F172A'), alignment=2, spaceAfter=2)
            company_title_style = ParagraphStyle('InvoiceCompanyTitle', parent=body_style, fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#0F172A'), spaceAfter=2)
            table_header_style = ParagraphStyle('InvoiceTableHeader', parent=body_style, fontName='Helvetica-Bold', fontSize=7, leading=8, textColor=colors.white, alignment=1)
            table_cell_style = ParagraphStyle('InvoiceCell', parent=body_style, fontSize=7.4, leading=8.8)
            table_number_style = ParagraphStyle('InvoiceNumber', parent=table_cell_style, alignment=2)
            total_style = ParagraphStyle('InvoiceTotal', parent=body_style, fontName='Helvetica-Bold', fontSize=10.2, leading=12, textColor=colors.HexColor('#0F172A'))

            def label_value(label, value):
                return Paragraph(f"<font color='#64748B'>{label}</font><br/><b>{clean(value)}</b>", body_style)

            def cell(value, style=table_cell_style):
                return Paragraph(clean(value), style)

            client = next((c for c in self.clients if c.get('name') == invoice_data.get('client')), {})
            exchange_rate = float(invoice_data.get('exchange_rate') or getattr(self, 'exchange_rate', 1) or 1)
            issue_date = str(invoice_data.get('date', ''))
            issue_day = issue_date.split()[0] if issue_date else 'N/A'
            if invoice_data.get('control_number'):
                control_number = invoice_data['control_number']
            elif str(number).isdigit():
                control_number = f"00-{int(number):08d}"
            else:
                control_number = '00-00000000'
            assignment_date = invoice_data.get('assignment_date') or issue_day
            company_name = getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS')
            company_rif = getattr(self, 'company_rif', 'RIF: N/A')
            company_address = getattr(self, 'company_address', 'Domicilio fiscal: N/A')
            company_phone = getattr(self, 'company_phone', 'Teléfono: N/A')
            story = []

            logo = None
            logo_path = os.path.join(base_dir, 'img', 'logo.png')
            if os.path.exists(logo_path):
                try:
                    logo = RLImage(logo_path, width=0.62 * inch, height=0.62 * inch)
                except Exception:
                    logo = None
            company_block = [Paragraph(clean(company_name), company_title_style), Paragraph(clean(company_rif), body_style), Paragraph(clean(company_address), small_style), Paragraph(clean(company_phone), small_style)]
            left_header = [[logo, company_block]] if logo else [[company_block]]
            left_widths = [0.75 * inch, 3.25 * inch] if logo else [4 * inch]
            left_table = Table(left_header, colWidths=left_widths)
            left_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

            invoice_box = Table([
                [Paragraph('FACTURA', title_style)],
                [Paragraph(f"<b>N° {clean(number)}</b>", header_style)],
                [Paragraph(f"N° de control: <b>{clean(control_number)}</b>", header_style)],
                [Paragraph(f"Emisión: {clean(issue_day)} | Hora: {clean(issue_date.split()[-1] if issue_date else '')}", header_style)],
                [Paragraph(f"Asignación / período: <b>{clean(assignment_date)}</b>", header_style)],
            ], colWidths=[3.0 * inch])
            invoice_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')), ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#CBD5E1')), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
            header_table = Table([[left_table, invoice_box]], colWidths=[4.0 * inch, 3.0 * inch])
            header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.extend([header_table, Spacer(1, 10)])

            client_data = [[label_value('Nombre / razón social', invoice_data.get('client')), label_value('Cédula / RIF', format_ci_rif(client.get('rif_ci'))), label_value('Teléfono', client.get('phone'))], [label_value('Domicilio fiscal', ' '.join(filter(None, [client.get('address'), client.get('city'), client.get('state')]))), label_value('Código de cliente / contrato', invoice_data.get('client_code') or client.get('id')), label_value('Condición de pago', 'Crédito' if invoice_data.get('is_credit') else 'Contado')]]
            client_table = Table(client_data, colWidths=[2.4 * inch] * 3)
            client_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')), ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#CBD5E1')), ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#E2E8F0')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
            story.extend([client_table, Spacer(1, 10)])

            item_rows = [[Paragraph('CANT.', table_header_style), Paragraph('CÓDIGO', table_header_style), Paragraph('DESCRIPCIÓN', table_header_style), Paragraph('P. UNIT.<br/>Bs.', table_header_style), Paragraph('P. UNIT.<br/>USD', table_header_style), Paragraph('TOTAL<br/>Bs. / USD', table_header_style)]]
            for item in invoice_data.get('items', []):
                product = next((p for p in self.products if p.get('name') == item.get('product')), {})
                quantity = float(item.get('quantity', 0) or 0)
                unit_usd = float(item.get('price', 0) or 0)
                total_usd = float(item.get('total', unit_usd * quantity) or 0)
                total_cell = [
                    Paragraph(clean(money(total_usd * exchange_rate)), table_number_style),
                    Paragraph(f"<font color='#64748B'>{clean(money(total_usd, '$ '))}</font>", table_number_style),
                ]
                item_rows.append([cell(item.get('quantity', 0), table_number_style), cell(item.get('code') or product.get('code')), Paragraph(clean(item.get('product')), table_cell_style), cell(money(unit_usd * exchange_rate), table_number_style), cell(money(unit_usd, '$ '), table_number_style), total_cell])

            items_table = Table(item_rows, colWidths=[0.5 * inch, 0.75 * inch, 2.25 * inch, 1.05 * inch, 1.0 * inch, 1.45 * inch], repeatRows=1)
            item_style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (2, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#CBD5E1')), ('TOPPADDING', (0, 0), (-1, 0), 7), ('BOTTOMPADDING', (0, 0), (-1, 0), 7), ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6)])
            for row_index in range(1, len(item_rows)):
                if row_index % 2 == 0:
                    item_style.add('BACKGROUND', (0, row_index), (-1, row_index), colors.HexColor('#F8FAFC'))
            items_table.setStyle(item_style)
            story.extend([items_table, Spacer(1, 9)])

            payments = invoice_data.get('payments') or []
            payment_rows = [[Paragraph('DESCRIPCIÓN / MONEDA', table_header_style), Paragraph('FECHA DE PAGO / ABONO', table_header_style)]]
            if payments:
                payment_rows.extend([[cell(p.get('method') or invoice_data.get('payment_method')), cell(p.get('date'))] for p in payments])
            else:
                payment_rows.append([cell(invoice_data.get('payment_method')), cell(issue_day)])
            payment_table = Table(payment_rows, colWidths=[2.1 * inch, 2.25 * inch])
            payment_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#64748B')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#CBD5E1')), ('FONTSIZE', (0, 1), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
            subtotal = float(invoice_data.get('subtotal', 0.0) or 0.0)
            tax = float(invoice_data.get('tax', 0.0) or 0.0)
            total = float(invoice_data.get('total', 0.0) or 0.0)
            totals_table = Table([[Paragraph('Base imponible Bs.', body_style), Paragraph(f"<b>{money(subtotal * exchange_rate)}</b>", body_style)], [Paragraph(f"I.V.A. ({self.iva_rate * 100:.2f}%) Bs.", body_style), Paragraph(f"<b>{money(tax * exchange_rate)}</b>", body_style)], [Paragraph('MONTO TOTAL Bs.', total_style), Paragraph(money(total * exchange_rate), total_style)]], colWidths=[1.7 * inch, 1.3 * inch])
            totals_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')), ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')), ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0F172A')), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6)]))
            lower_table = Table([[payment_table, totals_table]], colWidths=[4.35 * inch, 3.0 * inch])
            lower_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
            story.append(lower_table)

            rate_note_style = ParagraphStyle('InvoiceRateNote', parent=small_style, textColor=colors.HexColor('#475569'))
            rate_bold_style = ParagraphStyle('InvoiceRateBold', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor('#1E293B'))
            rate_note = Table([
                [Paragraph(f"<font color='#64748B'>Tasa BCV del día (VES/USD):</font>", rate_note_style),
                 Paragraph(f"<b>{exchange_rate:,.2f} VES/USD</b>", rate_bold_style)]
            ], colWidths=[2.6 * inch, 1.4 * inch])
            rate_note.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')), ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')), ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6)]))
            rate_wrap = Table([[rate_note, '']], colWidths=[4.0 * inch, 3.0 * inch])
            rate_wrap.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
            story.extend([Spacer(1, 5), rate_wrap])

            def draw_footer(canvas_obj, document_obj):
                canvas_obj.saveState()
                canvas_obj.setStrokeColor(colors.HexColor('#CBD5E1'))
                canvas_obj.line(30, 38, letter[0] - 30, 38)
                canvas_obj.setFont('Helvetica', 8)
                canvas_obj.setFillColor(colors.HexColor('#475569'))
                canvas_obj.drawCentredString(letter[0] / 2, 25, 'DOCUMENTO EMITIDO CONFORME A LA PROVIDENCIA ADMINISTRATIVA SNAT/2024/000102')
                canvas_obj.restoreState()

            doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)

            try:
                if os.name == 'nt':
                    os.startfile(filepath)
            except Exception:
                pass

            ModernMessageBox.showinfo("PDF generado", f"Factura exportada correctamente en:\n{filepath}")
            return filepath
        except Exception as e:
            ModernMessageBox.showerror("Error al generar PDF", f"No se pudo generar el archivo PDF: {e}")
            return None

    def generate_pdf_delivery_note(self, invoice_data=None):
        """Generar un Comprobante / Nota de Entrega informal (sin elementos fiscales).
        Excluye N° de control, desgloses del SENIAT, RIF y leyendas obligatorias.
        La tabla de productos y el total se muestran únicamente en USD."""
        if invoice_data is None:
            invoice_data = self.get_selected_invoice_data()

        if invoice_data is None and getattr(self, 'invoices', None):
            invoice_data = self.invoices[-1]

        if not invoice_data:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione una factura para generar la Nota de Entrega.")
            return None

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            export_dir = os.path.join(base_dir, "NotasDeEntrega")
            os.makedirs(export_dir, exist_ok=True)

            number = invoice_data.get('number', 'sin_numero')
            filename = f"NotaDeEntrega_{number}.pdf"
            filepath = os.path.join(export_dir, os.path.basename(filename))

            doc = SimpleDocTemplate(
                filepath,
                pagesize=letter,
                rightMargin=30,
                leftMargin=30,
                topMargin=28,
                bottomMargin=48,
            )
            styles = getSampleStyleSheet()
            def clean(value):
                return escape(str(value if value not in (None, '') else 'N/A'))

            def money_usd(value):
                return f"$ {float(value or 0):,.2f}"

            body_style = ParagraphStyle('NDBody', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=11, textColor=colors.HexColor('#1F2937'))
            small_style = ParagraphStyle('NDSmall', parent=body_style, fontSize=7.6, leading=9.2)
            header_style = ParagraphStyle('NDHeader', parent=body_style, fontSize=8, leading=9.6, alignment=2, textColor=colors.HexColor('#334155'))
            title_style = ParagraphStyle('NDTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=20, textColor=colors.HexColor('#0F172A'), alignment=2, spaceAfter=2)
            company_title_style = ParagraphStyle('NDCompanyTitle', parent=body_style, fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#0F172A'), spaceAfter=2)
            table_header_style = ParagraphStyle('NDTableHeader', parent=body_style, fontName='Helvetica-Bold', fontSize=8, leading=9, textColor=colors.white, alignment=1)
            table_cell_style = ParagraphStyle('NDCell', parent=body_style, fontSize=8.4, leading=10)
            table_number_style = ParagraphStyle('NDNumber', parent=table_cell_style, alignment=2)
            total_style = ParagraphStyle('NDTotal', parent=body_style, fontName='Helvetica-Bold', fontSize=11, leading=13, textColor=colors.HexColor('#0F172A'))
            section_style = ParagraphStyle('NDSection', parent=body_style, fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#475569'))
            signature_style = ParagraphStyle('NDSignature', parent=body_style, fontSize=8.6, leading=10, alignment=1)

            def cell(value, style=table_cell_style):
                return Paragraph(clean(value), style)

            client = next((c for c in self.clients if c.get('name') == invoice_data.get('client')), {})
            issue_date = str(invoice_data.get('date', ''))
            issue_day = issue_date.split()[0] if issue_date else 'N/A'

            company_name = getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS')
            company_address = getattr(self, 'company_address', '')
            if company_address == 'Domicilio fiscal: N/A':
                company_address = ''
            company_phone = getattr(self, 'company_phone', '')
            if company_phone == 'Teléfono: N/A':
                company_phone = ''

            story = []

            logo = None
            logo_path = os.path.join(base_dir, 'img', 'logo.png')
            if os.path.exists(logo_path):
                try:
                    logo = RLImage(logo_path, width=0.62 * inch, height=0.62 * inch)
                except Exception:
                    logo = None

            company_lines = [Paragraph(clean(company_name), company_title_style)]
            if company_address:
                company_lines.append(Paragraph(clean(company_address), small_style))
            if company_phone:
                company_lines.append(Paragraph(clean(company_phone), small_style))
            company_block = company_lines

            left_header = [[logo, company_block]] if logo else [[company_block]]
            left_widths = [0.75 * inch, 3.25 * inch] if logo else [4 * inch]
            left_table = Table(left_header, colWidths=left_widths)
            left_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

            doc_box = Table([
                [Paragraph('COMPROBANTE DE ENTREGA', title_style)],
                [Paragraph(f"<b>N° {clean(number)}</b>", header_style)],
                [Paragraph(f"Fecha: {clean(issue_day)}", header_style)],
            ], colWidths=[3.0 * inch])
            doc_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')), ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#CBD5E1')), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
            header_table = Table([[left_table, doc_box]], colWidths=[4.0 * inch, 3.0 * inch])
            header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.extend([header_table, Spacer(1, 10)])

            client_data = [[Paragraph(f"<font color='#64748B'>Cliente</font><br/><b>{clean(invoice_data.get('client'))}</b>", body_style), Paragraph(f"<font color='#64748B'>Teléfono</font><br/><b>{clean(client.get('phone'))}</b>", body_style), Paragraph(f"<font color='#64748B'>Condición</font><br/><b>{'Crédito' if invoice_data.get('is_credit') else 'Contado'}</b>", body_style)]]
            client_table = Table(client_data, colWidths=[2.4 * inch] * 3)
            client_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')), ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#CBD5E1')), ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#E2E8F0')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
            story.extend([client_table, Spacer(1, 10)])

            item_rows = [[Paragraph('CANT.', table_header_style), Paragraph('CÓDIGO', table_header_style), Paragraph('DESCRIPCIÓN', table_header_style), Paragraph('P. UNIT.<br/>USD', table_header_style), Paragraph('IMPORTE<br/>USD', table_header_style)]]
            for item in invoice_data.get('items', []):
                product = next((p for p in self.products if p.get('name') == item.get('product')), {})
                quantity = float(item.get('quantity', 0) or 0)
                unit_usd = float(item.get('price', 0) or 0)
                total_usd = float(item.get('total', unit_usd * quantity) or 0)
                item_rows.append([cell(item.get('quantity', 0), table_number_style), cell(item.get('code') or product.get('code')), Paragraph(clean(item.get('product')), table_cell_style), cell(money_usd(unit_usd), table_number_style), cell(money_usd(total_usd), table_number_style)])

            items_table = Table(item_rows, colWidths=[0.6 * inch, 0.9 * inch, 2.45 * inch, 1.4 * inch, 1.65 * inch], repeatRows=1)
            item_style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (2, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#CBD5E1')), ('TOPPADDING', (0, 0), (-1, 0), 7), ('BOTTOMPADDING', (0, 0), (-1, 0), 7), ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6)])
            for row_index in range(1, len(item_rows)):
                if row_index % 2 == 0:
                    item_style.add('BACKGROUND', (0, row_index), (-1, row_index), colors.HexColor('#F8FAFC'))
            items_table.setStyle(item_style)
            story.extend([items_table, Spacer(1, 9)])

            subtotal = float(invoice_data.get('subtotal', 0.0) or 0.0)
            total = float(invoice_data.get('total', 0.0) or 0.0)
            totals_table = Table([[Paragraph('MONTO TOTAL (USD)', total_style), Paragraph(money_usd(total), total_style)]], colWidths=[2.0 * inch, 1.5 * inch])
            totals_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')), ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')), ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0F172A')), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6)]))
            totals_wrap = Table([[totals_table, '']], colWidths=[3.5 * inch, 3.5 * inch])
            totals_wrap.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
            story.extend([totals_wrap, Spacer(1, 14)])

            obs_style = ParagraphStyle('NDObs', parent=table_cell_style, fontSize=8.6, leading=10.5)
            observations = [
                Paragraph('- Precios sujetos a cambios sin previo aviso.', obs_style),
                Paragraph('- Condición de pago: pago en dólares o la tasa de cambio del día.', obs_style),
            ]
            obs_cell = Table([[observations]], colWidths=[7.0 * inch])
            obs_cell.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
            story.append(Paragraph('OBSERVACIONES', section_style))
            story.append(Spacer(1, 3))
            story.append(Table([[obs_cell]], colWidths=[7.0 * inch], style=TableStyle([('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#CBD5E1')), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF'))])))
            story.append(Spacer(1, 22))

            signature_table = Table([
                [Paragraph('Entregado por: ______________________________', signature_style),
                 Paragraph('Recibido por: ______________________________', signature_style)],
                [Paragraph('Firma y sello', small_style),
                 Paragraph('Firma', small_style)],
            ], colWidths=[3.5 * inch, 3.5 * inch])
            signature_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
            story.append(signature_table)

            def draw_footer(canvas_obj, document_obj):
                canvas_obj.saveState()
                canvas_obj.setStrokeColor(colors.HexColor('#CBD5E1'))
                canvas_obj.line(30, 38, letter[0] - 30, 38)
                canvas_obj.setFont('Helvetica', 7.5)
                canvas_obj.setFillColor(colors.HexColor('#475569'))
                canvas_obj.drawCentredString(letter[0] / 2, 25, 'Documento sin validez fiscal — constancia informal de entrega de mercancía')
                canvas_obj.restoreState()

            doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)

            try:
                if os.name == 'nt':
                    os.startfile(filepath)
            except Exception:
                pass

            ModernMessageBox.showinfo("Nota de Entrega", f"Nota de Entrega generada correctamente en:\n{filepath}")
            return filepath
        except Exception as e:
            ModernMessageBox.showerror("Error al generar Nota de Entrega", f"No se pudo generar el archivo PDF: {e}")
            return None

    def create_professional_pdf(self, invoice, filepath):
        """Crea un documento PDF profesional usando ReportLab"""
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Estilo personalizado para el título
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor("#1D4ED8"),
            alignment=1, # Centro
            spaceAfter=20
        )

        # Encabezado con Logo y Datos de la Empresa
        company_name = getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS')
        company_rif = getattr(self, 'company_rif', 'RIF: N/A')
        company_address = getattr(self, 'company_address', 'Domicilio fiscal: N/A')
        company_phone = getattr(self, 'company_phone', 'Teléfono: N/A')

        # Tabla de encabezado (Logo + Info Empresa)
        logo_path = "img/logo.png"
        if os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=1*inch, height=1*inch)
                header_data = [[logo, [Paragraph(f"<b>{company_name}</b>", styles['Normal']),
                                     Paragraph(company_rif, styles['Normal']),
                                     Paragraph(company_address, styles['Normal']),
                                     Paragraph(company_phone, styles['Normal'])]]]
            except:
                header_data = [[[Paragraph(f"<b>{company_name}</b>", styles['Normal']),
                               Paragraph(company_rif, styles['Normal']),
                               Paragraph(company_address, styles['Normal']),
                               Paragraph(company_phone, styles['Normal'])]]]
        else:
            header_data = [[[Paragraph(f"<b>{company_name}</b>", styles['Normal']),
                           Paragraph(company_rif, styles['Normal']),
                           Paragraph(company_address, styles['Normal']),
                           Paragraph(company_phone, styles['Normal'])]]]

        header_table = Table(header_data, colWidths=[1.2*inch, 5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 20))

        # Título de Factura
        elements.append(Paragraph(f"FACTURA # {invoice['number']:06d}", title_style))
        elements.append(Spacer(1, 10))

        # Información de la Factura y Cliente
        # Buscar datos del cliente para más detalle si están disponibles
        client_obj = next((c for c in self.clients if c.get("name") == invoice["client"]), {})
        
        info_data = [
            [Paragraph(f"<b>Fecha:</b> {invoice['date']}", styles['Normal']), 
             Paragraph(f"<b>Estado:</b> {invoice['status']}", styles['Normal'])],
            [Paragraph(f"<b>Cliente:</b> {invoice['client']}", styles['Normal']),
             Paragraph(f"<b>RIF/CI:</b> {format_ci_rif(client_obj.get('rif_ci', 'N/A'))}", styles['Normal'])],
            [Paragraph(f"<b>Dirección:</b> {client_obj.get('address', 'N/A')}", styles['Normal']),
             Paragraph(f"<b>Teléfono:</b> {client_obj.get('phone', 'N/A')}", styles['Normal'])]
        ]
        
        info_table = Table(info_data, colWidths=[3.1*inch, 3.1*inch])
        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))

        # Tabla de Productos
        product_data = [["Descripción", "Cant.", "P. Unitario", "Total"]]
        for item in invoice["items"]:
            product_data.append([
                item["product"],
                str(item["quantity"]),
                f"${item['price']:,.2f}",
                f"${item['total']:,.2f}"
            ])

                # Totales
        product_data.append(["", "", "Subtotal:", f"${invoice['subtotal']:,.2f}"])
        product_data.append(["", "", f"IVA ({self.iva_rate*100:.0f}%):", f"${invoice['tax']:,.2f}"])
        product_data.append(["", "", "TOTAL USD:", f"${invoice['total']:,.2f}"])
        
        # Agregar total en Bolívares si existe tasa de cambio
        invoice_rate = float(invoice.get('exchange_rate') or getattr(self, 'exchange_rate', 1) or 1)
        if invoice_rate > 1:
            total_bs = invoice['total'] * invoice_rate
            product_data.append(["", "", "TOTAL VES:", f"Bs.{total_bs:,.2f}"])
            product_data.append(["", "", "Tasa de Cambio:", f"{invoice_rate:,.2f}"])

        prod_table = Table(product_data, colWidths=[3.2*inch, 0.8*inch, 1.1*inch, 1.1*inch])
        
                # Estilo de la tabla de productos
        invoice_rate = float(invoice.get('exchange_rate') or getattr(self, 'exchange_rate', 1) or 1)
        summary_rows = 5 if invoice_rate > 1 else 3
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'), 
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'), 
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -(summary_rows + 1)), colors.white),
            ('GRID', (0, 0), (-1, -(summary_rows + 1)), 1, colors.grey),
            ('FONTNAME', (0, -summary_rows), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (2, -summary_rows), (-1, -summary_rows), 1, colors.black),
            # Resaltar Totales (USD y VES si aplica)
            ('FONTSIZE', (0, -3 if invoice_rate > 1 else -1), (-1, -2 if invoice_rate > 1 else -1), 14),
            ('TEXTCOLOR', (2, -3 if invoice_rate > 1 else -1), (-1, -2 if invoice_rate > 1 else -1), colors.HexColor("#1D4ED8")),
        ])
        
        # Filas alternas
        for i in range(1, len(invoice["items"]) + 1):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F1F5F9"))

        prod_table.setStyle(style)
        elements.append(prod_table)
        elements.append(Spacer(1, 30))

        # Pie de página / Notas
        footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.grey)
        elements.append(Paragraph("¡Gracias por su preferencia!", footer_style))
        elements.append(Paragraph("Esta factura es un documento legal de compra.", footer_style))
        
        if invoice.get("payment_method"):
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"Método de pago: {invoice['payment_method']}", styles['Normal']))

        # Generar PDF
        doc.build(elements)


    def view_invoice_detail(self):
        """Ver detalle de factura seleccionada (estrictamente de una en una)"""
        selection = self.invoices_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione una factura para ver el detalle")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione una sola factura para ver el detalle.")
            return
        
        item = self.invoices_tree.item(selection[0])
        invoice_number = int(item["values"][0])
        
        # Buscar factura
        invoice = None
        for inv in self.invoices:
            if inv["number"] == invoice_number:
                invoice = inv
                break
        
        if not invoice:
            ModernMessageBox.showerror("Error", "Factura no encontrada")
            return
        
        # Mostrar diálogo con detalles
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Detalle Factura #{invoice_number}")
        dialog.geometry("800x800")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        # Contenido principal
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Información de la factura
        info_frame = ctk.CTkFrame(main_frame)
        info_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            info_frame,
            text=f"FACTURA #{invoice_number:06d}",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=5)
        
        info_grid = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_grid.pack(pady=10)
        
        inv_rate = invoice.get('exchange_rate') or getattr(self, 'exchange_rate', 1)
        labels = [
            ("Fecha:", invoice['date']),
            ("Cliente:", invoice['client']),
            ("Método de Pago:", invoice['payment_method']),
            ("Estado:", invoice['status']),
            ("Tasa aplicada:", f"{float(inv_rate):,.2f} VES/USD")
        ]
        
        for i, (label, value) in enumerate(labels):
            ctk.CTkLabel(info_grid, text=label, font=("Segoe UI", 11, "bold")).grid(row=i, column=0, sticky="w", padx=10, pady=2)
            ctk.CTkLabel(info_grid, text=value).grid(row=i, column=1, sticky="w", padx=10, pady=2)
        
        # Tabla de items
        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        columns = ("Producto", "Cantidad", "Precio Unitario", "Total")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor="center")
        
        tree.column("Producto", width=300, anchor="w")
        tree.column("Precio Unitario", anchor="e")
        tree.column("Total", anchor="e")
        
        for item in invoice["items"]:
            tree.insert("", "end", values=(
                item["product"],
                item["quantity"],
                f"${item['price']:.2f}",
                f"${item['total']:.2f}"
            ))
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Totales
        totals_frame = ctk.CTkFrame(main_frame)
        totals_frame.pack(fill="x")
        
        ctk.CTkLabel(totals_frame, text="Subtotal:", font=("Segoe UI", 12)).pack(anchor="e", padx=20)
        ctk.CTkLabel(totals_frame, text=f"${invoice['subtotal']:.2f}", font=("Segoe UI", 12)).pack(anchor="e", padx=20)
        
        ctk.CTkLabel(totals_frame, text="IVA:", font=("Segoe UI", 12)).pack(anchor="e", padx=20)
        ctk.CTkLabel(totals_frame, text=f"${invoice['tax']:.2f}", font=("Segoe UI", 12)).pack(anchor="e", padx=20)
        
        ctk.CTkLabel(totals_frame, text="TOTAL:", font=("Segoe UI", 14, "bold")).pack(anchor="e", padx=20)
        ctk.CTkLabel(totals_frame, text=f"${invoice['total']:.2f}", font=("Segoe UI", 14, "bold")).pack(anchor="e", padx=20)

        inv_rate = invoice.get('exchange_rate') or getattr(self, 'exchange_rate', 1)
        ctk.CTkLabel(totals_frame, text=f"TOTAL EN Bs. (tasa {float(inv_rate):,.2f}):", font=("Segoe UI", 11, "bold")).pack(anchor="e", padx=20, pady=(6, 0))
        ctk.CTkLabel(totals_frame, text=f"Bs.{float(invoice['total']) * float(inv_rate):,.2f}", font=("Segoe UI", 11, "bold")).pack(anchor="e", padx=20)

        # Notas adicionales de la factura
        if invoice.get("cancel_note"):
            ctk.CTkLabel(main_frame, text="Nota de Cancelación:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10,0))
            cancel_box = ctk.CTkTextbox(main_frame, width=300, height=60)
            cancel_box.pack(fill="x", pady=5)
            cancel_box.insert("1.0", invoice.get("cancel_note"))
            cancel_box.configure(state="disabled")

    def mark_invoice_as_paid(self):
        """Marcar factura seleccionada como pagada y registrar pago en la base de datos (estrictamente de una en una)"""
        selection = self.invoices_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione una factura para marcar como pagada")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione una sola factura para registrar pago.")
            return

        item = self.invoices_tree.item(selection[0])
        invoice_number = int(item["values"][0])

        # Buscar factura
        invoice = next((inv for inv in self.invoices if inv.get("number") == invoice_number), None)
        if not invoice:
            ModernMessageBox.showerror("Error", "Factura no encontrada")
            return

        if invoice.get("status") == "Pagada":
            ModernMessageBox.showinfo("Info", "La factura ya está pagada")
            return

        # Diálogo simple para elegir método de pago
        dialog = ctk.CTkToplevel(self)
        dialog.title("Registrar Pago")
        dialog.geometry("840x220")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)

        ctk.CTkLabel(dialog, text=f"Registrar pago para Factura #{invoice_number}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        amount = float(invoice.get("balance", invoice.get("total", 0.0)))
        ctk.CTkLabel(dialog, text=f"Monto a registrar: ${amount:.2f}").pack()

        method_var = tk.StringVar(value="Efectivo")
        methods_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        methods_frame.pack(pady=10)
        for m in ["Efectivo", "Tarjeta", "Transferencia", "Pago móvil", "Divisas"]:
            ctk.CTkRadioButton(methods_frame, text=m, variable=method_var, value=m).pack(side="left", padx=6)

        def confirm_payment():
            method = method_var.get()
            pay = {
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "amount": amount,
                "method": method,
                "note": "Pago registrado desde lista de facturas"
            }
            invoice.setdefault("payments", []).append(pay)
            invoice["status"] = "Pagada"
            invoice["balance"] = 0.0
            invoice["payment_method"] = method

            # Actualizar saldo del cliente si existe
            client_obj = next((c for c in self.clients if c.get("name") == invoice.get("client")), None)
            try:
                if client_obj is not None:
                    client_obj["balance"] = float(client_obj.get("balance", 0.0)) - float(amount)
                    if client_obj["balance"] < 0:
                        client_obj["balance"] = 0.0
            except Exception:
                pass

            self.save_data()
            self.refresh_invoices()
            self.refresh_clients()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after payment
            safe_destroy(dialog)
            ModernMessageBox.showinfo("Éxito", f"Factura #{invoice_number} marcada como pagada")

        ctk.CTkButton(dialog, text="Confirmar Pago", command=confirm_payment, fg_color="#059669", hover_color="#047857", corner_radius=8).pack(pady=12)
        ctk.CTkButton(dialog, text="Cancelar", command=dialog.destroy, fg_color="#64748B", hover_color="#475569", corner_radius=8).pack()

    def cancel_invoice(self):
        """Cancelar factura seleccionada (estrictamente de una en una)"""
        if not self._require_admin("cancelar facturas"):
            return
        selection = self.invoices_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione una factura para cancelar")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "La cancelación debe realizarse de una en una. Seleccione una sola factura.")
            return
        
        item = self.invoices_tree.item(selection[0])
        invoice_number = int(item["values"][0])
        
        confirm = ModernMessageBox.askyesno(
            "Confirmar Cancelación",
            f"¿Está seguro de cancelar la factura #{invoice_number}?\n\nEsta acción revertirá el stock de productos.",
            icon="warning"
        )
        
        if confirm:
            # Buscar y cancelar factura
            for invoice in self.invoices:
                if invoice["number"] == invoice_number:
                    if invoice["status"] == "Cancelada":
                        ModernMessageBox.showwarning("Ya Cancelada", "Esta factura ya está cancelada")
                        return
                    
                    # Revertir stock
                    for item in invoice["items"]:
                        for product in self.products:
                            if product["name"] == item["product"]:
                                product["stock"] += item["quantity"]
                                break
                    # pedir método y nota de cancelación
                    cancel_method = simpledialog.askstring("Método de Cancelación", "Indique método o motivo (ej: Reembolso, Anulación por cliente, Otros):")
                    cancel_note = simpledialog.askstring("Nota de Cancelación", "Ingrese una nota o detalle adicional (opcional):")

                    invoice["status"] = "Cancelada"
                    invoice["cancel_method"] = cancel_method
                    invoice["cancel_note"] = cancel_note
                    self.save_data()
                    self.refresh_inventory()
                    self.refresh_invoices()
                    self.update_dashboard() # Auto-refresh dashboard after invoice cancellation
                    
                    ModernMessageBox.showinfo("Éxito", f"Factura #{invoice_number} cancelada correctamente")
                    break

    def delete_invoice(self):
        """Eliminar factura(s) seleccionada(s) permitiendo selección múltiple"""
        if not self._require_admin("eliminar facturas"):
            return
        selection = self.invoices_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione al menos una factura para eliminar")
            return
        
        if len(selection) == 1:
            item = self.invoices_tree.item(selection[0])
            invoice_number = int(item["values"][0])
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación",
                f"¿Está seguro de eliminar la factura #{invoice_number}?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        else:
            confirm = ModernMessageBox.askyesno(
                "Confirmar Eliminación Múltiple",
                f"¿Está seguro de eliminar las {len(selection)} facturas seleccionadas?\n\nEsta acción no se puede deshacer.",
                icon="warning"
            )
        
        if confirm:
            nums_to_delete = set()
            for sel in selection:
                try:
                    nums_to_delete.add(int(self.invoices_tree.item(sel)["values"][0]))
                except Exception:
                    pass
            self.invoices = [inv for inv in self.invoices if inv["number"] not in nums_to_delete]
            self.save_data()
            self.refresh_invoices()
            self.update_counters()
            self.update_dashboard() # Auto-refresh dashboard after invoice deletion
            if len(nums_to_delete) == 1:
                ModernMessageBox.showinfo("Éxito", "Factura eliminada correctamente")
            else:
                ModernMessageBox.showinfo("Éxito", f"{len(nums_to_delete)} facturas eliminadas correctamente")

    def apply_invoice_filters(self):
        """Aplicar filtros a la lista de facturas"""
        date_from = self.date_from_entry.get()
        date_to = self.date_to_entry.get()
        
        # Limpiar tabla
        for item in self.invoices_tree.get_children():
            self.invoices_tree.delete(item)
        
        # Aplicar filtros
        filtered_invoices = self.invoices.copy()
        
        if date_from:
            try:
                day, month, year = map(int, date_from.split('/'))
                from_date = datetime(year, month, day)
                filtered_invoices = [
                    inv for inv in filtered_invoices
                    if datetime.strptime(inv['date'].split()[0], '%d/%m/%Y') >= from_date
                ]
            except ValueError:
                pass
        
        if date_to:
            try:
                day, month, year = map(int, date_to.split('/'))
                to_date = datetime(year, month, day)
                filtered_invoices = [
                    inv for inv in filtered_invoices
                    if datetime.strptime(inv['date'].split()[0], '%d/%m/%Y') <= to_date
                ]
            except ValueError:
                pass
        # Filtrar por estado si se seleccionó uno
        try:
            status = self.status_filter_var.get()
            if status and status != "Todos":
                filtered_invoices = [inv for inv in filtered_invoices if inv.get("status") == status]
        except Exception:
            pass
        
        # Mostrar facturas filtradas
        for invoice in filtered_invoices:
            self.invoices_tree.insert("", "end", values=(
                invoice["number"],
                invoice["date"],
                invoice["client"],
                f"${invoice['subtotal']:.2f}",
                f"${invoice['tax']:.2f}",
                f"${invoice['total']:.2f}",
                invoice["status"],
                invoice["payment_method"]
            ))

    def clear_invoice_filters(self):
        """Limpiar filtros de facturas"""
        self.date_from_entry.delete(0, "end")
        self.date_to_entry.delete(0, "end")
        try:
            if hasattr(self, 'status_filter_combobox'):
                self.status_filter_combobox.set("Todos")
        except Exception:
            pass
        self.refresh_invoices()

    def export_invoices_excel(self):
        """Exportar facturas a archivos Excel organizados por fecha."""
        if Workbook is None:
            ModernMessageBox.showerror(
                "Error",
                "La biblioteca openpyxl no está instalada. Instale openpyxl y vuelva a intentar."
            )
            return

        if not self.invoices:
            ModernMessageBox.showwarning("Sin Facturas", "No hay facturas para exportar.")
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        excel_root = os.path.join(base_dir, "Excel")
        os.makedirs(excel_root, exist_ok=True)

        exported_files = []
        for inv in self.invoices:
            date_part = str(inv.get("date", "")).split()[0]
            if date_part:
                try:
                    date_folder = datetime.strptime(date_part, "%d/%m/%Y").strftime("%d_%m_%Y")
                except Exception:
                    date_folder = date_part.replace("/", "_").replace("-", "_").replace(" ", "_")
            else:
                date_folder = "Sin_Fecha"

            folder_path = os.path.join(excel_root, date_folder)
            os.makedirs(folder_path, exist_ok=True)

            filename = f"Factura{inv.get('number', 'N/A')}.xlsx"
            filepath = os.path.join(folder_path, filename)

            wb = Workbook()
            sheet = wb.active
            sheet.title = "Factura"

            headers = ["Campo", "Valor"]
            sheet.append(headers)

            inv_rate = inv.get("exchange_rate") or getattr(self, "exchange_rate", 1)
            metadata = [
                ("N° Factura", inv.get("number", "")),
                ("Fecha", inv.get("date", "")),
                ("Cliente", inv.get("client", "")),
                ("Estado", inv.get("status", "")),
                ("Método Pago", inv.get("payment_method", "")),
                ("Es Crédito", "Sí" if inv.get("is_credit") else "No"),
                ("Saldo Pendiente", inv.get("balance", 0.0)),
                ("Vence", inv.get("due_date", "")),
                ("Cancel. Método", inv.get("cancel_method", "")),
                ("Cancel. Nota", inv.get("cancel_note", "")),
                ("Tasa de Cambio (VES/USD)", inv_rate),
                ("Subtotal", inv.get("subtotal", 0.0)),
                ("IVA", inv.get("tax", 0.0)),
                ("Total", inv.get("total", 0.0)),
                ("Total en Bs.", float(inv.get("total", 0.0)) * float(inv_rate))
            ]

            for key, value in metadata:
                sheet.append([key, value])

            sheet.append([])
            sheet.append(["Producto", "Cantidad", "Precio Unitario", "Total"])
            for item in inv.get("items", []):
                sheet.append([
                    item.get("product", ""),
                    item.get("quantity", 0),
                    item.get("price", 0.0),
                    item.get("total", 0.0)
                ])

            for col, width in [("A", 24), ("B", 40), ("C", 18), ("D", 18)]:
                try:
                    sheet.column_dimensions[col].width = width
                except Exception:
                    pass

            wb.save(filepath)
            exported_files.append(filepath)

        if exported_files:
            ModernMessageBox.showinfo(
                "Exportado",
                f"{len(exported_files)} facturas exportadas en: {excel_root}"
            )
        else:
            ModernMessageBox.showwarning("Exportación vacía", "No se exportaron facturas.")

    def open_excel_export_folder(self):
        """Abrir carpeta raíz de exportaciones Excel en el explorador de archivos."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        excel_root = os.path.join(base_dir, "Excel")
        os.makedirs(excel_root, exist_ok=True)

        try:
            os.startfile(excel_root)
        except Exception as e:
            ModernMessageBox.showerror("Error", f"No se pudo abrir la carpeta Excel:\n{str(e)}")

    def open_pdf_export_folder(self):
        """Abrir carpeta raíz de exportaciones PDF en el explorador de archivos."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pdf_root = os.path.join(base_dir, "Facturas")
        os.makedirs(pdf_root, exist_ok=True)

        try:
            os.startfile(pdf_root)
        except Exception as e:
            ModernMessageBox.showerror("Error", f"No se pudo abrir la carpeta PDF:\n{str(e)}")

    def open_delivery_note_export_folder(self):
        """Abrir la carpeta raíz de notas de entrega en el explorador de archivos."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        delivery_note_root = os.path.join(base_dir, "NotasDeEntrega")
        os.makedirs(delivery_note_root, exist_ok=True)

        try:
            os.startfile(delivery_note_root)
        except Exception as e:
            ModernMessageBox.showerror("Error", f"No se pudo abrir la carpeta Notas de Entrega:\n{str(e)}")

    def generate_report(self):
        """Generar reporte seleccionado con UI premium"""
        # Limpiar área de contenido (excepto cabecera)
        for widget in self.report_content_area.winfo_children():
            if widget not in (self.report_header, self.report_text):
                safe_destroy(widget)
        
        if self.report_text.winfo_exists():
            self.report_text.pack_forget() # Ocultar textbox por defecto

        # Ocultar botón de refrescar en reportes específicos para evitar confusión (se refrescan al entrar)
        if hasattr(self, 'refresh_report_btn') and self.refresh_report_btn.winfo_exists():
            self.refresh_report_btn.pack_forget()

        report_type = self.report_var.get()
        self.report_title_label.configure(text=report_type)

        # Normalizar búsqueda para que coincida con el sidebar
        if "Ventas por Día" in report_type:
            self.show_daily_sales_report()
        elif "Ventas por Mes" in report_type:
            self.show_monthly_sales_report()
        elif "Ventas por Cliente" in report_type:
            self.show_sales_by_client_report()
        elif "Productos Top" in report_type: # Ajustado a sidebar "📦 Productos Top"
            self.show_top_products_report()
        elif "Stock Crítico" in report_type: # Ajustado a sidebar "⚠️ Stock Crítico"
            self.show_low_stock_report()
        elif "Flujo de Caja" in report_type: # Ajustado a sidebar "💰 Flujo de Caja"
            self.show_cash_flow_report()
        elif "Desempeño" in report_type: # Ajustado a sidebar "🏪 Desempeño"
            self.show_performance_report()
        elif "Pendientes" in report_type: # Ajustado a sidebar "📋 Pendientes"
            self.show_pending_clients_report()
        elif "Banco" in report_type: # Ajustado a sidebar "🏦 Banco"
            self.show_bank_report()

    def show_daily_sales_report(self):
        """Mostrar reporte de ventas por día con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Agrupar ventas por día
        sales_by_day = {}
        for invoice in self.invoices:
            if invoice["status"] != "Cancelada":
                date = invoice["date"].split()[0]
                sales_by_day[date] = sales_by_day.get(date, 0) + invoice["total"]
        
        if not sales_by_day:
            ctk.CTkLabel(container, text="No hay datos de ventas disponibles.", font=("Inter", 14)).pack(pady=50)
            return

        sorted_dates = sorted(sales_by_day.keys(), reverse=True)

        # 1. Gráfico de Tendencia
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Tendencia de Ventas (Últimos Días)", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        canvas = FigureCanvasTkAgg(self.create_sales_trend_chart(plt_bg, plt_fg), master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Desglose por Fecha", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        columns = ("Fecha", "Total Ventas", "N° Facturas")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=10)
        tree.heading("Fecha", text="FECHA")
        tree.heading("Total Ventas", text="TOTAL VENTAS")
        tree.heading("N° Facturas", text="N° FACTURAS")
        
        tree.column("Fecha", width=200, anchor="center")
        tree.column("Total Ventas", width=200, anchor="e")
        tree.column("N° Facturas", width=150, anchor="center")
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        total_sales = 0
        total_invoices = 0
        for date in sorted_dates[:30]:  # Últimos 30 días
            day_invoices = [inv for inv in self.invoices if inv["date"].startswith(date) and inv["status"] != "Cancelada"]
            tree.insert("", "end", values=(date, f"${sales_by_day[date]:,.2f}", len(day_invoices)))
            total_sales += sales_by_day[date]
            total_invoices += len(day_invoices)

        tree.insert("", "end", values=("TOTAL (30d)", f"${total_sales:,.2f}", total_invoices), tags=('total',))
        tree.tag_configure('total', font=("Segoe UI", 10, "bold"), background="#F1F5F9")

    def show_monthly_sales_report(self):
        """Mostrar reporte de ventas por mes con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Agrupar ventas por mes
        sales_by_month = {}
        for invoice in self.invoices:
            if invoice["status"] != "Cancelada":
                date = invoice["date"].split()[0]
                month_year = date[3:]  # MM/AAAA
                sales_by_month[month_year] = sales_by_month.get(month_year, 0) + invoice["total"]
        
        if not sales_by_month:
            ctk.CTkLabel(container, text="No hay datos de ventas disponibles.", font=("Inter", 14)).pack(pady=50)
            return

        sorted_months = sorted(sales_by_month.keys(), reverse=True)

        # 1. Gráfico de Barras Mensual (Usar una versión del gráfico de tendencia adaptada a meses)
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Histórico de Ventas Mensuales", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        # Crear gráfico ad-hoc para meses
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=plt_bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(plt_bg)
        m_keys = sorted(sales_by_month.keys())
        m_vals = [sales_by_month[k] for k in m_keys]
        ax.bar(m_keys, m_vals, color="#10B981")
        ax.set_title("Ventas por Mes ($)", fontsize=10, fontweight='bold', color=plt_fg)
        ax.tick_params(colors=plt_fg)
        for spine in ax.spines.values(): spine.set_color(plt_fg)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Ingresos por Mes", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        columns = ("Mes", "Total Ventas", "N° Facturas")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=10)
        tree.heading("Mes", text="MES/AÑO")
        tree.heading("Total Ventas", text="TOTAL VENTAS")
        tree.heading("N° Facturas", text="N° FACTURAS")
        
        tree.column("Mes", width=200, anchor="center")
        tree.column("Total Ventas", width=200, anchor="e")
        tree.column("N° Facturas", width=150, anchor="center")
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        total_sales = 0
        total_invoices = 0
        for m_y in sorted_months:
            month_invoices = [inv for inv in self.invoices if inv["date"].split()[0][3:] == m_y and inv["status"] != "Cancelada"]
            tree.insert("", "end", values=(m_y, f"${sales_by_month[m_y]:,.2f}", len(month_invoices)))
            total_sales += sales_by_month[m_y]
            total_invoices += len(month_invoices)

        tree.insert("", "end", values=("TOTAL", f"${total_sales:,.2f}", total_invoices), tags=('total',))
        tree.tag_configure('total', font=("Segoe UI", 10, "bold"), background="#F1F5F9")

    def show_sales_by_client_report(self):
        """Mostrar reporte de ventas por cliente con UI premium"""
        # Contenedor con scroll para el reporte
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Preparar datos
        sales_by_client = {}
        for invoice in self.invoices:
            if invoice["status"] != "Cancelada":
                client = invoice["client"]
                if client not in sales_by_client:
                    sales_by_client[client] = {"total": 0, "count": 0}
                sales_by_client[client]["total"] += invoice["total"]
                sales_by_client[client]["count"] += 1
        
        sorted_clients = sorted(sales_by_client.items(), key=lambda x: x[1]["total"], reverse=True)

        if not sorted_clients:
            ctk.CTkLabel(container, text="No hay datos de ventas disponibles.", font=("Inter", 14)).pack(pady=50)
            return

        # 1. Sección de Gráfico (Card)
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Distribución de Ventas por Cliente", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        canvas = FigureCanvasTkAgg(self.create_top_clients_chart(plt_bg, plt_fg), master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Sección de Tabla (Card)
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Detalle de Facturación por Cliente", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        # Treeview para los datos
        columns = ("Cliente", "Total Ventas", "N° Facturas")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=10)
        tree.heading("Cliente", text="CLIENTE")
        tree.heading("Total Ventas", text="TOTAL VENTAS")
        tree.heading("N° Facturas", text="N° FACTURAS")
        
        tree.column("Cliente", width=300, anchor="w")
        tree.column("Total Ventas", width=150, anchor="e")
        tree.column("N° Facturas", width=120, anchor="center")
        
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        total_sales = 0
        total_count = 0
        for client, data in sorted_clients:
            tree.insert("", "end", values=(
                client, 
                f"${data['total']:,.2f}", 
                data['count']
            ))
            total_sales += data["total"]
            total_count += data["count"]

        # Fila de Total (Insertar al final con estilo si es posible, o simplemente al final)
        tree.insert("", "end", values=("TOTAL", f"${total_sales:,.2f}", total_count), tags=('total',))
        tree.tag_configure('total', font=("Segoe UI", 10, "bold"), background="#F1F5F9")

    def show_top_products_report(self):
        """Mostrar reporte de productos más vendidos con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Calcular ventas por producto
        product_sales = {}
        for invoice in self.invoices:
            if invoice["status"] != "Cancelada":
                for item in invoice["items"]:
                    product = item["product"]
                    if product not in product_sales:
                        product_sales[product] = {"quantity": 0, "revenue": 0}
                    product_sales[product]["quantity"] += item["quantity"]
                    product_sales[product]["revenue"] += item["total"]
        
        if not product_sales:
            ctk.CTkLabel(container, text="No hay datos de ventas disponibles.", font=("Inter", 14)).pack(pady=50)
            return

        # 1. Gráfico de Barras de Productos
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Top 5 Productos por Cantidad", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        canvas = FigureCanvasTkAgg(self.create_top_products_chart(plt_bg, plt_fg), master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Ranking de Ventas", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        columns = ("Producto", "Cantidad", "Ingresos")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=12)
        tree.heading("Producto", text="PRODUCTO")
        tree.heading("Cantidad", text="CANTIDAD")
        tree.heading("Ingresos", text="INGRESOS")
        
        tree.column("Producto", width=300, anchor="w")
        tree.column("Cantidad", width=120, anchor="center")
        tree.column("Ingresos", width=150, anchor="e")
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        sorted_products = sorted(product_sales.items(), key=lambda x: x[1]["quantity"], reverse=True)
        for prod, data in sorted_products:
            tree.insert("", "end", values=(prod, data["quantity"], f"${data['revenue']:,.2f}"))

    def show_low_stock_report(self):
        """Mostrar reporte de productos bajos en stock con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        low_stock_products = [p for p in self.products if p["stock"] <= p.get("min_stock", 5)]
        
        if not low_stock_products:
            ctk.CTkLabel(container, text="¡Todos los productos tienen stock suficiente!", font=("Inter", 14), text_color="#10B981").pack(pady=50)
            return

        # 1. Gráfico de Stock (Top 10 más bajos)
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Productos con Stock Crítico", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=plt_bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(plt_bg)
        sorted_low = sorted(low_stock_products, key=lambda x: x["stock"])[:10]
        names = [p["name"][:15] for p in sorted_low]
        vals = [p["stock"] for p in sorted_low]
        ax.bar(names, vals, color="#EF4444")
        ax.set_title("Cantidad en Almacén", fontsize=10, fontweight='bold', color=plt_fg)
        ax.tick_params(colors=plt_fg)
        for spine in ax.spines.values(): spine.set_color(plt_fg)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(table_card, text="Listado de Reposición Urgente", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        columns = ("Producto", "Stock Actual", "Mínimo", "Diferencia")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=10)
        tree.heading("Producto", text="PRODUCTO")
        tree.heading("Stock Actual", text="STOCK ACTUAL")
        tree.heading("Mínimo", text="MÍNIMO")
        tree.heading("Diferencia", text="FALTANTE")
        
        tree.column("Producto", width=300, anchor="w")
        tree.column("Stock Actual", width=120, anchor="center")
        tree.column("Mínimo", width=120, anchor="center")
        tree.column("Diferencia", width=120, anchor="center")
        tree.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for p in sorted_low:
            min_s = p.get("min_stock", 5)
            diff = p["stock"] - min_s
            tree.insert("", "end", values=(p["name"], p["stock"], min_s, diff))

    def show_cash_flow_report(self):
        """Mostrar reporte de flujo de caja con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Cálculos de ingresos por método
        payment_methods = {}
        total_income = 0
        for invoice in self.invoices:
            if invoice["status"] != "Cancelada":
                method = invoice["payment_method"]
                payment_methods[method] = payment_methods.get(method, 0) + invoice["total"]
                total_income += invoice["total"]
        
        if not payment_methods:
            ctk.CTkLabel(container, text="No hay datos de flujo de caja disponibles.", font=("Inter", 14)).pack(pady=50)
            return

        # 1. Gráfico Circular de Métodos
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Distribución por Método de Pago", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=plt_bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(plt_bg)
        labels = list(payment_methods.keys())
        sizes = list(payment_methods.values())
        colors = ["#3B82F6", "#10B981", "#6366F1", "#F59E0B", "#EF4444", "#8B5CF6"]
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, textprops={'color': plt_fg, 'fontsize': 9})
        ax.set_title(f"Ingresos Totales: ${total_income:,.2f}", fontsize=11, fontweight='bold', color=plt_fg)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Resumen
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        
        columns = ("Método", "Monto", "Porcentaje")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=len(payment_methods))
        tree.heading("Método", text="MÉTODO DE PAGO")
        tree.heading("Monto", text="MONTO ASOCIADO")
        tree.heading("Porcentaje", text="PORCENTAJE (%)")
        
        tree.column("Método", width=250, anchor="w")
        tree.column("Monto", width=150, anchor="e")
        tree.column("Porcentaje", width=120, anchor="center")
        tree.pack(fill="both", expand=True, padx=20, pady=20)

        for m, amt in payment_methods.items():
            perc = (amt / total_income * 100) if total_income > 0 else 0
            tree.insert("", "end", values=(m, f"${amt:,.2f}", f"{perc:.1f}%"))

    def show_performance_report(self):
        """Mostrar reporte de desempeño general con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Estadísticas básicas
        total_invoices = len([inv for inv in self.invoices if inv["status"] != "Cancelada"])
        total_sales = sum(invoice["total"] for invoice in self.invoices if invoice["status"] != "Cancelada")
        avg_sale = total_sales / total_invoices if total_invoices > 0 else 0
        
        # 1. Gráfico de Desempeño (Ventas por Categoría)
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Desempeño por Categoría de Producto", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        canvas = FigureCanvasTkAgg(self.create_category_sales_chart(plt_bg, plt_fg), master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Resumen de Métricas
        metrics_card = ctk.CTkFrame(container, fg_color="transparent")
        metrics_card.pack(fill="x", padx=10, pady=10)
        
        metrics = [
            ("Facturas Emitidas", str(total_invoices), "#3B82F6"),
            ("Ingresos Totales", f"${total_sales:,.2f}", "#10B981"),
            ("Ticket Promedio", f"${avg_sale:,.2f}", "#6366F1"),
            ("Productos en Catálogo", str(len(self.products)), "#F59E0B")
        ]
        
        for i, (label, val, col) in enumerate(metrics):
            card = ctk.CTkFrame(metrics_card, corner_radius=12, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
            card.pack(side="left", fill="both", expand=True, padx=5)
            ctk.CTkLabel(card, text=label, font=("Inter", 11), text_color=("#64748B", "#94A3B8")).pack(pady=(15, 0))
            ctk.CTkLabel(card, text=val, font=("Inter", 16, "bold"), text_color=col).pack(pady=(5, 15))

    def show_pending_clients_report(self):
        """Mostrar listado de clientes con saldos pendientes con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        pending = {}
        for inv in self.invoices:
            if inv.get("status") != "Cancelada":
                bal = float(inv.get("balance", inv.get("total", 0.0))) if inv.get("is_credit") else 0
                if bal > 0:
                    c = inv.get("client")
                    pending[c] = pending.get(c, 0.0) + bal

        if not pending:
            ctk.CTkLabel(container, text="No hay clientes con saldo pendiente.", font=("Inter", 14), text_color="#10B981").pack(pady=50)
            return

        # 1. Gráfico de Deuda por Cliente
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Mayores Deudores", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=plt_bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(plt_bg)
        sorted_p = sorted(pending.items(), key=lambda x: x[1], reverse=True)[:10]
        names = [x[0][:15] for x in sorted_p]
        vals = [x[1] for x in sorted_p]
        ax.barh(names, vals, color="#F59E0B")
        ax.set_title("Saldos Pendientes ($)", fontsize=10, fontweight='bold', color=plt_fg)
        ax.tick_params(colors=plt_fg)
        for spine in ax.spines.values(): spine.set_color(plt_fg)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle (Transaccional)
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        
        columns = ("Factura", "Cliente", "Emisión", "Vencimiento", "Saldo Pendiente", "Días Restantes")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=15)
        tree.heading("Factura", text="FACTURA #")
        tree.heading("Cliente", text="CLIENTE")
        tree.heading("Emisión", text="EMISIÓN")
        tree.heading("Vencimiento", text="VENCIMIENTO")
        tree.heading("Saldo Pendiente", text="SALDO PENDIENTE ($)")
        tree.heading("Días Restantes", text="DÍAS RESTANTES")
        
        tree.column("Factura", width=100, anchor="center")
        tree.column("Cliente", width=250, anchor="w")
        tree.column("Emisión", width=120, anchor="center")
        tree.column("Vencimiento", width=120, anchor="center")
        tree.column("Saldo Pendiente", width=150, anchor="e")
        tree.column("Días Restantes", width=150, anchor="center")
        tree.pack(fill="both", expand=True, padx=20, pady=20)

        total_pending = 0
        # Filtrar facturas con saldo pendiente
        pending_invoices = [inv for inv in self.invoices if inv.get("status") != "Cancelada" and inv.get("is_credit") and float(inv.get("balance", 0.0)) > 0]
        
        for inv in sorted(pending_invoices, key=lambda x: x["number"]):
            client_name = inv.get("client")
            amt = float(inv.get("balance", 0.0))
            rem_days_num = self.get_remaining_days_for_invoice(inv)
            rem_days_str = f"{rem_days_num} días"
            if rem_days_num < 0:
                rem_days_str = f"VENCIDO ({rem_days_num})"
            
            tree.insert("", "end", values=(
                f"#{inv['number']}",
                client_name,
                inv.get("date", "").split()[0],
                inv.get("due_date", "N/A"),
                f"${amt:,.2f}",
                rem_days_str
            ))
            total_pending += amt

        tree.insert("", "end", values=("TOTAL DEUDA", f"${total_pending:,.2f}"), tags=('total',))
        total_bg = "#FEF3C7" if ctk.get_appearance_mode() == "Light" else "#78350F"
        tree.tag_configure('total', font=("Segoe UI", 10, "bold"), background=total_bg)

    def show_bank_report(self):
        """Mostrar reporte de banco con UI premium"""
        container = ctk.CTkScrollableFrame(self.report_content_area, fg_color="transparent")
        container.pack(fill="both", expand=True)

        payments = {}
        for inv in self.invoices:
            if inv.get("status") != "Cancelada":
                method = inv.get("payment_method", "Otros")
                payments[method] = payments.get(method, 0.0) + float(inv.get("total", 0.0))

        if not payments:
            ctk.CTkLabel(container, text="No hay movimientos bancarios registrados.", font=("Inter", 14)).pack(pady=50)
            return

        # 1. Gráfico de Ingresos por Banco/Método
        chart_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        chart_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(chart_card, text="Resumen de Canales de Pago", font=("Inter", 14, "bold"), text_color=("#475569", "#CBD5E1")).pack(pady=15, padx=20, anchor="w")

        plt_bg = "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#1E293B"
        plt_fg = "#1E293B" if ctk.get_appearance_mode() == "Light" else "#F8FAFC"
        
        fig = Figure(figsize=(8, 4), dpi=100, facecolor=plt_bg)
        ax = fig.add_subplot(111)
        ax.set_facecolor(plt_bg)
        labels = list(payments.keys())
        vals = list(payments.values())
        ax.bar(labels, vals, color="#6366F1")
        ax.set_title("Fondos Captados por Método ($)", fontsize=10, fontweight='bold', color=plt_fg)
        ax.tick_params(colors=plt_fg)
        for spine in ax.spines.values(): spine.set_color(plt_fg)
        
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 2. Tabla de Detalle
        table_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("#FFFFFF", "#1E293B"), border_width=1, border_color=("#F1F5F9", "#334155"))
        table_card.pack(fill="both", expand=True, padx=10, pady=10)
        
        columns = ("Canal", "Monto Total")
        tree = ttk.Treeview(table_card, columns=columns, show="headings", height=len(payments))
        tree.heading("Canal", text="CANAL / MÉTODO")
        tree.heading("Monto Total", text="MONTO TOTAL ($)")
        
        tree.column("Canal", width=400, anchor="w")
        tree.column("Monto Total", width=200, anchor="e")
        tree.pack(fill="both", expand=True, padx=20, pady=20)

        for method, amt in payments.items():
            tree.insert("", "end", values=(method, f"${amt:,.2f}"))

    def on_global_search(self, event):
        """Ejecutar la búsqueda global solo al confirmar con Enter."""
        try:
            if event is None or event.keysym in ("Return", "KP_Enter"):
                self.perform_global_search()
        except Exception:
            # no bloquear por errores en eventos de teclado
            pass

    def perform_global_search(self):
        """Ejecutar búsqueda global"""
        query = self.global_search_entry.get().lower()
        if not query:
            return
        
        # Buscar en productos
        results = []
        for product in self.products:
            if (query in product["name"].lower() or 
                query in product.get("code", "").lower() or
                query in product.get("category", "").lower()):
                results.append(f"📦 {product['name']} - Stock: {product['stock']} - ${product['price']:.2f}")
        
        # Buscar en clientes
        for client in self.clients:
            if (query in client["name"].lower() or 
                query in str(client.get("rif_ci", "")).lower() or
                query in str(client.get("phone", "")).lower()):
                results.append(f"👤 {client['name']} - {client.get('phone', 'Sin teléfono')}")
        
        # Mostrar resultados
        if results:
            dialog = ctk.CTkToplevel(self)
            dialog.title(f"Resultados de búsqueda: {query}")
            dialog.geometry("600x400")
            dialog.transient(self)
            
            text_widget = ctk.CTkTextbox(dialog)
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)
            text_widget.insert("1.0", "\n".join(results))
            text_widget.configure(state="disabled")
        else:
            ModernMessageBox.showinfo("Búsqueda", "No se encontraron resultados")

    def on_pos_search(self, event):
        """Buscar productos en el POS"""
        query = self.pos_search_entry.get().lower()
        self.refresh_pos_products(query)

    def add_first_pos_search_result(self, event=None):
        """Añadir el primer resultado de la búsqueda POS a la factura"""
        children = self.pos_tree.get_children()
        if children:
            self.pos_tree.selection_set(children[0])
            self.add_product_to_invoice()
            self.pos_search_entry.delete(0, 'end')
            self.refresh_pos_products()

    def on_inventory_search(self, event):
        """Buscar productos en el inventario"""
        query = self.inventory_search_entry.get().lower()
        self.refresh_inventory(query)

    def refresh_pos_products(self, filter_text=""):
        """Refrescar lista de productos en el POS"""
        # Limpiar tabla
        for item in self.pos_tree.get_children():
            self.pos_tree.delete(item)
        
        # Filtrar y mostrar productos con stock > 0
        filtered_products = [p for p in self.products if p.get("stock", 0) > 0]
        if filter_text:
            filtered_products = [
                p for p in filtered_products
                if filter_text in p["name"].lower() or 
                   filter_text in str(p.get("code", "")).lower()
            ]
        
        for product in filtered_products:
            self.pos_tree.insert("", "end", values=(
                product["id"],
                product["name"],
                f"${product['price']:.2f}",
                product["stock"]
            ))

    def refresh_inventory(self, filter_text=""):
        """Refrescar inventario aplicando texto, categoría y proveedor."""
        # Actualizar lista de categorías en el combo (si existe el widget)
        if hasattr(self, 'category_filter'):
            current_cat = self.category_filter.get()
            categories = sorted(list(set(str(p.get("category", "")).strip() for p in self.products if p.get("category"))))
            new_values = ["Todas"] + categories
            if list(self.category_filter.cget("values")) != new_values:
                self.category_filter.configure(values=new_values)
                if current_cat not in new_values:
                    self.category_filter.set("Todas")

        # Actualizar lista de proveedores en el combo (si existe el widget)
        if hasattr(self, 'supplier_filter'):
            current_supplier = self.supplier_filter.get()
            suppliers = sorted(list(set(
                str(p.get("supplier", "")).strip()
                for p in self.products
                if str(p.get("supplier", "")).strip()
            )))
            new_values = ["Todos"] + suppliers
            if list(self.supplier_filter.cget("values")) != new_values:
                self.supplier_filter.configure(values=new_values)
                if current_supplier not in new_values:
                    self.supplier_filter.set("Todos")

        # Limpiar tabla
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)
        
        # Obtener categoría seleccionada
        selected_category = "Todas"
        if hasattr(self, 'category_filter'):
            selected_category = self.category_filter.get()

        selected_supplier = "Todos"
        if hasattr(self, 'supplier_filter'):
            selected_supplier = self.supplier_filter.get()

        # Filtrar y mostrar productos
        filtered_products = self.products
        
        # Filtro por texto
        if filter_text:
            ft = filter_text.lower()
            filtered_products = [
                p for p in filtered_products
                if ft in str(p.get("name", "")).lower() or 
                   ft in str(p.get("code", "")).lower()
            ]
        
        # Filtro por categoría
        if selected_category != "Todas":
            filtered_products = [
                p for p in filtered_products
                if str(p.get("category", "")) == selected_category
            ]

        # Filtro por proveedor
        if selected_supplier != "Todos":
            filtered_products = [
                p for p in filtered_products
                if str(p.get("supplier", "")).strip() == selected_supplier
            ]
        
        for product in filtered_products:
            self.inventory_tree.insert("", "end", values=(
                product["id"],
                product.get("code", ""),
                product["name"],
                product.get("category", ""),
                f"${product['price']:.2f}",
                product["stock"],
                product.get("min_stock", 5),
                product.get("location", "")
            ))

    def get_remaining_credit_days_for_client(self, client):
        """Calcular días de crédito restantes para un cliente (Asignación General)"""
        if not client.get("credit_days") or client.get("credit_days") <= 0:
            return 0
        
        start_date_str = client.get("credit_start_date")
        if not start_date_str:
            return client.get("credit_days", 0)
        
        try:
            # Soportar formatos comunes
            fmt = "%d/%m/%Y"
            start_date = datetime.strptime(start_date_str.split()[0], fmt)
            current_date = datetime.now()
            # Truncar a día
            current_date_day = datetime(current_date.year, current_date.month, current_date.day)
            
            elapsed = (current_date_day - start_date).days
            remaining = client.get("credit_days", 0) - elapsed
            return max(0, remaining)
        except Exception as e:
            print(f"Error calculando días restantes: {e}")
            return client.get("credit_days", 0)

    def get_remaining_days_for_invoice(self, invoice):
        """Calcular días restantes para una factura específica"""
        if not invoice.get("due_date"):
            return 0
        
        try:
            fmt = "%d/%m/%Y"
            due_date = datetime.strptime(invoice.get("due_date").split()[0], fmt)
            current_date = datetime.now()
            # Truncar a día
            current_date_day = datetime(current_date.year, current_date.month, current_date.day)
            
            remaining = (due_date - current_date_day).days
            return remaining # Puede ser negativo si está vencida
        except Exception:
            return 0

    def on_client_search(self, event):
        """Buscar clientes en la lista"""
        query = self.client_search_entry.get().lower()
        self.refresh_clients(query)

    def refresh_clients(self, filter_text=""):
        """Refrescar lista de clientes"""
        # Limpiar tabla
        for item in self.clients_tree.get_children():
            self.clients_tree.delete(item)
        
        # Filtrar clientes
        filtered_clients = self.clients
        
        # Filtro de texto
        if filter_text:
            filtered_clients = [
                c for c in filtered_clients
                if filter_text in c["name"].lower() or 
                   filter_text in c.get("rif_ci", "").lower() or
                   filter_text in c.get("email", "").lower()
            ]
        
        # Filtro de tipo
        if hasattr(self, 'client_type_filter'):
            type_filter = self.client_type_filter.get()
            if type_filter != "Todos":
                filtered_clients = [
                    c for c in filtered_clients
                    if c.get("type") == type_filter
                ]

        for client in filtered_clients:
            rem_days = self.get_remaining_credit_days_for_client(client)
            rem_str = f"{rem_days} días" if client.get("credit_days", 0) > 0 else "N/A"
            
            self.clients_tree.insert("", "end", values=(
                client["id"],
                client["name"],
                format_ci_rif(client.get("rif_ci", "")),
                client.get("phone", ""),
                client.get("email", ""),
                client.get("address", "")[:30] + "..." if len(client.get("address", "")) > 30 else client.get("address", ""),
                client.get("type", "General") + f" ({rem_str})" if client.get("credit_days", 0) > 0 else client.get("type", "General")
            ))

    def view_inventory_detail(self):
        """Ver detalle completo del producto seleccionado (estrictamente de uno en uno)"""
        selection = self.inventory_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione un producto para ver el detalle")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione un solo producto para ver el detalle.")
            return
        
        item = self.inventory_tree.item(selection[0])
        product_id = int(item["values"][0])
        product = next((p for p in self.products if p["id"] == product_id), None)
        
        if not product: return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Detalle de Producto: {product['name']}")
        dialog.geometry("800x800")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        dialog.bind("<Escape>", lambda e: safe_destroy(dialog))
        
        content_frame = ctk.CTkFrame(dialog)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        fields = [
            ("ID", product.get("id")),
            ("Código", product.get("code")),
            ("Nombre", product.get("name")),
            ("Categoría", product.get("category")),
            ("Precio Compra", f"${product.get('purchase_price',0):.2f}"),
            ("Precio Venta", f"${product.get('price',0):.2f}"),
            ("Stock Actual", product.get("stock")),
            ("Stock Mínimo", product.get("min_stock")),
            ("Ubicación", product.get("location")),
            ("Proveedor", product.get("supplier")),
        ]
        
        for i, (label, value) in enumerate(fields):
            ctk.CTkLabel(content_frame, text=label, font=("Segoe UI", 11, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            ctk.CTkLabel(content_frame, text=str(value)).grid(row=i, column=1, sticky="w", padx=10, pady=2)
            
        ctk.CTkLabel(content_frame, text="Notas:", font=("Segoe UI", 11, "bold")).grid(row=len(fields), column=0, sticky="nw", pady=10)
        notes_box = ctk.CTkTextbox(content_frame, width=300, height=100)
        notes_box.grid(row=len(fields), column=1, padx=10, pady=10, sticky="ew")
        notes_box.insert("1.0", product.get("notes", "Sin notas."))
        notes_box.configure(state="disabled")
        
        ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)

    def view_client_detail(self):
        """Ver detalle completo del cliente seleccionado (estrictamente de uno en uno)"""
        selection = self.clients_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione un cliente para ver el detalle")
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione un solo cliente para ver el detalle.")
            return
        
        item = self.clients_tree.item(selection[0])
        client_id = int(item["values"][0])
        client = next((c for c in self.clients if c["id"] == client_id), None)
        
        if not client: return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Detalle de Cliente: {client['name']}")
        dialog.geometry("500x600")
        dialog.transient(self)
        dialog.grab_set()
        fade_in_window(dialog)
        
        content_frame = ctk.CTkFrame(dialog)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        rem_days = self.get_remaining_credit_days_for_client(client)
        rem_str = f"{rem_days} días" if client.get("credit_days", 0) > 0 else "N/A"
        
        fields = [
            ("ID", client.get("id")),
            ("Nombre", client.get("name")),
            ("RIF/CI", format_ci_rif(client.get("rif_ci"))),
            ("Tipo", client.get("type")),
            ("Teléfono", client.get("phone")),
            ("Email", client.get("email")),
            ("Ciudad", client.get("city")),
            ("Estado", client.get("state")),
            ("Crédito (Días)", client.get("credit_days")),
            ("Saldo Actual", f"${client.get('balance',0):.2f}"),
            ("Días Restantes", rem_str),
        ]
        
        for i, (label, value) in enumerate(fields):
            ctk.CTkLabel(content_frame, text=label, font=("Segoe UI", 11, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            ctk.CTkLabel(content_frame, text=str(value)).grid(row=i, column=1, sticky="w", padx=10, pady=2)
            
        ctk.CTkLabel(content_frame, text="Dirección:", font=("Segoe UI", 11, "bold")).grid(row=len(fields), column=0, sticky="nw", pady=2)
        ctk.CTkLabel(content_frame, text=client.get("address", ""), wraplength=300).grid(row=len(fields), column=1, sticky="w", padx=10, pady=2)

        ctk.CTkLabel(content_frame, text="Notas:", font=("Segoe UI", 11, "bold")).grid(row=len(fields)+1, column=0, sticky="nw", pady=10)
        notes_box = ctk.CTkTextbox(content_frame, width=300, height=100)
        notes_box.grid(row=len(fields)+1, column=1, padx=10, pady=10, sticky="ew")
        notes_box.insert("1.0", client.get("notes", "Sin notas."))
        notes_box.configure(state="disabled")
        
        ctk.CTkButton(dialog, text="Cerrar", command=dialog.destroy).pack(pady=10)

    def refresh_invoices(self):
        """Refrescar lista de facturas"""
        # Limpiar tabla
        for item in self.invoices_tree.get_children():
            self.invoices_tree.delete(item)
        
        for invoice in reversed(self.invoices):  # Mostrar las más recientes primero
            self.invoices_tree.insert("", "end", values=(
                invoice["number"],
                invoice["date"],
                invoice["client"],
                f"${invoice['subtotal']:.2f}",
                f"${invoice['tax']:.2f}",
                f"${invoice['total']:.2f}",
                invoice["status"],
                invoice["payment_method"]
            ))

    def update_counters(self):
        """Actualizar contadores en la barra superior"""
        self.product_count_label.configure(text=f"Productos: {len(self.products)}")
        self.client_count_label.configure(text=f"Clientes: {len(self.clients)}")
        self.invoice_count_label.configure(text=f"Facturas: {len([inv for inv in self.invoices if inv['status'] != 'Cancelada'])}")

    def refresh_all_views(self, event=None):
        """Refrescar todas las vistas manualmente o por automatización"""
        self.refresh_inventory()
        self.refresh_pos_products()
        self.refresh_clients()
        self.refresh_invoices()
        self.update_counters()
        self.update_dashboard()
        if self.user_role == "admin" and hasattr(self, "users_tree"):
            self.refresh_user_list()
        ModernMessageBox.showinfo("Refrescado", "Todas las vistas han sido actualizadas.")

    # ─── PESTAÑA DE GESTIÓN DE USUARIOS (SOLO ADMIN) ───────────────────────────

    def create_users_tab(self):
        """Crear la interfaz de gestión de usuarios (solo para administradores)"""
        main_frame = ctk.CTkFrame(self.tab_users)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Cabecera ---
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header_frame,
            text="Gestión de Usuarios del Sistema",
            font=("Segoe UI", 15, "bold")
        ).pack(side="left", padx=10)

        # --- Botones de Acción ---
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['add']} Nuevo Usuario",
            command=self.open_new_user_from_tab,
            width=150,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['edit']} Editar / Recuperar",
            command=self.open_edit_user_from_tab,
            width=160,
            corner_radius=8,
            fg_color="#F59E0B",
            hover_color="#D97706"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text=f"{self.icons['delete']} Eliminar",
            command=self.delete_user_from_tab,
            width=110,
            corner_radius=8,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            controls_frame,
            text="🔄 Refrescar",
            command=self.refresh_user_list,
            width=110,
            corner_radius=8,
            fg_color="#6366F1",
            hover_color="#4F46E5"
        ).pack(side="left", padx=5)

        # --- Tabla de Usuarios ---
        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("Usuario", "Nombre Completo", "Rol", "Email", "Institución", "Área")
        self.users_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=20
        )

        col_widths = {
            "Usuario": 120, "Nombre Completo": 200, "Rol": 100,
            "Email": 200, "Institución": 160, "Área": 150
        }
        for col in columns:
            self.users_tree.heading(col, text=col.upper())
            self.users_tree.column(col, width=col_widths.get(col, 120), anchor="center")
        self.users_tree.column("Nombre Completo", anchor="w")
        self.users_tree.column("Email", anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.users_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.users_tree.xview)
        self.users_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.users_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Eventos
        self.users_tree.bind("<Double-1>", lambda e: self.open_edit_user_from_tab())
        self.users_tree.bind("<Delete>", lambda e: self.delete_user_from_tab())
        self.users_tree.bind("<Return>", lambda e: self.open_edit_user_from_tab())

        # Menú contextual
        users_ctx_menu = tk.Menu(self, tearoff=0)
        users_ctx_menu.add_command(label=" Nuevo Usuario", command=self.open_new_user_from_tab)
        users_ctx_menu.add_separator()
        users_ctx_menu.add_command(label=" Editar / Recuperar Contraseña", command=self.open_edit_user_from_tab)
        users_ctx_menu.add_command(label=" Eliminar Usuario", command=self.delete_user_from_tab)

        def show_users_ctx(event):
            item = self.users_tree.identify_row(event.y)
            if item:
                if item not in self.users_tree.selection():
                    self.users_tree.selection_set(item)
                users_ctx_menu.post(event.x_root, event.y_root)

        self.users_tree.bind("<Button-3>", show_users_ctx)

        self.refresh_user_list()

    def refresh_user_list(self):
        """Recargar la lista de usuarios en la pestaña Usuarios"""
        if not hasattr(self, "users_tree"):
            return
        try:
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            users = db.get_users()
            for u in users:
                role_display = "🛡️ Admin" if u.get("role") == "admin" else "👤 Empleado"
                self.users_tree.insert("", "end", values=(
                    u.get("username", ""),
                    u.get("full_name") or "N/A",
                    role_display,
                    u.get("email") or "N/A",
                    u.get("institution") or "N/A",
                    u.get("area") or "N/A"
                ))
        except Exception as e:
            print(f"Error al refrescar lista de usuarios: {e}")

    def open_new_user_from_tab(self):
        """Abrir ventana de registro directamente desde la pestaña de usuarios"""
        win = RegisterWindow(self)
        self.wait_window(win)
        self.refresh_user_list()

    def open_edit_user_from_tab(self):
        """Editar o recuperar contraseña de un usuario sin requerir contraseña anterior (estrictamente 1 por 1)"""
        selection = self.users_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione un usuario para editar", parent=self)
            return
        if len(selection) > 1:
            ModernMessageBox.showwarning("Atención", "La edición debe realizarse estrictamente de uno en uno. Por favor, seleccione un solo usuario.", parent=self)
            return
        username = self.users_tree.item(selection[0])["values"][0]
        win = EditUserWindow(self, username)
        self.wait_window(win)
        self.refresh_user_list()

    def delete_user_from_tab(self):
        """Eliminar usuario(s) desde la pestaña de administración permitiendo selección múltiple"""
        selection = self.users_tree.selection()
        if not selection:
            ModernMessageBox.showwarning("Sin selección", "Seleccione al menos un usuario para eliminar", parent=self)
            return
        
        usernames = [self.users_tree.item(s)["values"][0] for s in selection]
        if "admin" in usernames:
            ModernMessageBox.showwarning(
                "Acción Denegada",
                "El usuario 'admin' es vital para el sistema y no puede ser eliminado.",
                parent=self
            )
            usernames = [u for u in usernames if u != "admin"]
            if not usernames:
                return

        if len(usernames) == 1:
            prompt_msg = f"Para eliminar permanentemente al usuario '{usernames[0]}',\nescribe la palabra: borrar"
        else:
            prompt_msg = f"Para eliminar permanentemente a los {len(usernames)} usuarios seleccionados ({', '.join(usernames)}),\nescribe la palabra: borrar"

        confirm = simpledialog.askstring(
            "Confirmar Eliminación",
            prompt_msg,
            parent=self
        )
        if confirm and confirm.strip().lower() == "borrar":
            for u in usernames:
                db.delete_user(u)
            self.refresh_user_list()
            if len(usernames) == 1:
                ModernMessageBox.showinfo("Éxito", f"Usuario '{usernames[0]}' eliminado correctamente.", parent=self)
            else:
                ModernMessageBox.showinfo("Éxito", f"{len(usernames)} usuarios eliminados correctamente.", parent=self)
        elif confirm is not None:
            ModernMessageBox.showerror(
                "Error de Validación",
                "La palabra de confirmación no coincide. Acción cancelada.",
                parent=self
            )

    # ───────────────────────────────────────────────────────────────────────────

    def on_closing(self):
        """Guardar datos al cerrar la aplicación"""
        try:
            self.cancel_all_after()
        except Exception:
            pass
        self.save_data()
        # Destruir esta ventana segura y terminar la aplicación principal (root)
        try:
            try:
                safe_destroy(self)
            except Exception:
                pass
            # finalizar loop principal
            root = tk._default_root
            if root:
                try:
                    root.quit()
                except Exception:
                    pass
        except Exception:
            pass

    def cancel_all_after(self):
        """Cancelar todos los callbacks `after` pendientes en este intérprete"""
        try:
            # obtener ids de after pendientes (tupla)
            pending = self.tk.call('after', 'info')
            # cancelar cada id
            for aid in pending:
                try:
                    self.after_cancel(aid)
                except Exception:
                    # ignorar ids que no pertenezcan a este widget
                    pass
        except Exception:
            pass

    def logout(self):
        """Cerrar sesión: guardar, cancelar timers, destruir y reabrir login"""
        if not ModernMessageBox.askyesno("Cerrar Sesión", "¿Desea cerrar la sesión actual?"):
            return

        try:
            self.cancel_all_after()
        except Exception:
            pass

        try:
            self.save_data()
        except Exception:
            pass

        # Intentar destruir la ventana actual y cualquier Toplevel huérfano
        try:
            try:
                safe_destroy(self)
            except Exception:
                pass

            root = tk._default_root
            if root is None:
                root = tk.Tk()
                root.withdraw()

            # Asegurarse de eliminar otros Toplevels pendientes ligados a la raíz
            try:
                for child in list(root.winfo_children()):
                    try:
                        if isinstance(child, (tk.Toplevel, ctk.CTkToplevel)):
                            safe_destroy(child)
                    except Exception:
                        try:
                            safe_destroy(child)
                        except Exception:
                            pass
            except Exception:
                pass

            # Abrir la ventana de login usando la raíz oculta (no deiconificar la raíz)
            try:
                login_win = LoginWindow(lambda role: BillingSystem(master=root, user_role=role), master=root)
            except Exception:
                # intentar crear login en una nueva raíz si falla
                try:
                    new_root = tk.Tk()
                    new_root.withdraw()
                    LoginWindow(lambda role: BillingSystem(master=new_root, user_role=role), master=new_root)
                except Exception:
                    pass
            try:
                login_win.focus_force()
            except Exception:
                pass

        except Exception:
            # Fallback: crear nueva raíz y mostrar login
            try:
                new_root = tk.Tk()
                new_root.withdraw()
                LoginWindow(lambda role: BillingSystem(master=new_root, user_role=role), master=new_root)
            except Exception:
                pass

    def save_data(self):
        """Guardar datos en SQLite y respaldo en JSON"""
        try:
            # Guardar en SQLite (principal)
            db.save_state(
                self.products, self.clients, self.invoices, 
                self.invoice_counter, self.iva_rate, self.exchange_rate,
                self.include_pending_in_dashboard, self.auto_update_rate,
                self.rate_source,
                getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS'),
                getattr(self, 'company_rif', 'RIF: N/A'),
                getattr(self, 'company_address', 'Domicilio fiscal: N/A'),
                getattr(self, 'company_phone', 'Teléfono: N/A')
            )

            # Respaldo en JSON
            data = {
                "products": self.products,
                "clients": self.clients,
                "invoices": self.invoices,
                "invoice_counter": self.invoice_counter,
                "iva_rate": self.iva_rate,
                "exchange_rate": self.exchange_rate,
                "include_pending_in_dashboard": self.include_pending_in_dashboard,
                "auto_update_rate": self.auto_update_rate,
                "rate_source": self.rate_source,
                "store_config": {
                    "store_name": getattr(self, 'company_name', 'SISTEMA DE FACTURACIÓN AS'),
                    "rif": getattr(self, 'company_rif', 'RIF: N/A'),
                    "fiscal_domicile": getattr(self, 'company_address', 'Domicilio fiscal: N/A'),
                    "phone": getattr(self, 'company_phone', 'Teléfono: N/A')
                },
                "version": "3.3"
            }
            with open("billing_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            ModernMessageBox.showerror("Error Crítico", f"No se pudieron guardar los datos: {e}")
            print(f"Error al guardar datos: {e}")

    def load_data(self):
        """Cargar datos desde la base de datos o JSON de respaldo"""
        try:
            # Inicializar la base de datos
            db.init_db()
            
            # Intentar cargar desde SQLite (Principal)
            (products, clients, invoices, invoice_counter, iva_rate, exchange_rate, 
             include_pending_in_dashboard, auto_update_rate, rate_source,
             store_name, company_rif, company_address, company_phone) = db.load_state()
            
            if products or clients or invoices:
                self.products = products
                self.clients = clients
                self.invoices = invoices
                self.invoice_counter = invoice_counter
                self.iva_rate = iva_rate
                self.exchange_rate = exchange_rate
                self.include_pending_in_dashboard = include_pending_in_dashboard
                self.auto_update_rate = auto_update_rate
                self.rate_source = rate_source
                self.company_name = store_name or "SISTEMA DE FACTURACIÓN AS"
                self.company_rif = company_rif or "RIF: N/A"
                self.company_address = company_address or "Domicilio fiscal: N/A"
                self.company_phone = company_phone or "Teléfono: N/A"
                return
            
            # Si SQLite está vacío, intentar cargar desde JSON (Respaldo/Migración)
            if os.path.exists("billing_data.json"):
                with open("billing_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.products = data.get("products", [])
                    self.clients = data.get("clients", [])
                    self.invoices = data.get("invoices", [])
                    self.invoice_counter = data.get("invoice_counter", 1000)
                    self.iva_rate = data.get("iva_rate", 0.16)
                    self.exchange_rate = data.get("exchange_rate", 350.0)
                    self.include_pending_in_dashboard = data.get("include_pending_in_dashboard", True)
                    self.auto_update_rate = data.get("auto_update_rate", False)
                    self.rate_source = data.get("rate_source", "oficial")
                    store_config = data.get("store_config", {})
                    self.company_name = store_config.get("store_name", "SISTEMA DE FACTURACIÓN AS")
                    self.company_rif = store_config.get("rif", "RIF: N/A")
                    self.company_address = store_config.get("fiscal_domicile", "Domicilio fiscal: N/A")
                    self.company_phone = store_config.get("phone", "Teléfono: N/A")
                    # Persistir en SQLite para futuras cargas
                    self.save_data()
            else:
                # Datos de ejemplo si no existe nada
                    self.products = [
                        {"id": 1, "code": "PROD001", "name": "Laptop HP 15", "category": "Electrónica", 
                         "price": 899.99, "stock": 15, "min_stock": 3, "location": "A1"},
                        {"id": 2, "code": "PROD002", "name": "Mouse Inalámbrico", "category": "Electrónica", 
                         "price": 29.99, "stock": 50, "min_stock": 10, "location": "A2"},
                        {"id": 3, "code": "PROD003", "name": "Teclado Mecánico", "category": "Electrónica", 
                         "price": 79.99, "stock": 25, "min_stock": 5, "location": "A3"},
                        {"id": 4, "code": "PROD004", "name": "Monitor 24\"", "category": "Electrónica", 
                         "price": 199.99, "stock": 12, "min_stock": 3, "location": "B1"},
                        {"id": 5, "code": "PROD005", "name": "Impresora Multifuncional", "category": "Electrónica", 
                         "price": 149.99, "stock": 8, "min_stock": 2, "location": "B2"}
                    ]

                    self.clients = [
                        {"id": 1, "name": "Empresa XYZ S.A.", "rif_ci": "XYZ123456789", "type": "Empresa", 
                         "phone": "555-1234", "email": "contacto@xyz.com"},
                        {"id": 2, "name": "Juan Pérez", "type": "Público", "phone": "555-5678", 
                         "email": "juan@email.com"}
                    ]

                    self.invoices = []
                    self.invoice_counter = 1000
                    self.company_name = "SISTEMA DE FACTURACIÓN AS"
                    self.company_rif = "RIF: N/A"
                    self.company_address = "Domicilio fiscal: N/A"
                    self.company_phone = "Teléfono: N/A"
                    self.save_data()

        except Exception as e:
            ModernMessageBox.showerror("Error al cargar datos", f"Ocurrió un error al cargar los datos: {e}")
            print(f"Error al cargar datos: {e}")
            # En caso de error, inicializar estructuras vacías
            self.products = []
            self.clients = []
            self.invoices = []
            self.invoice_counter = 1000
            self.company_name = "SISTEMA DE FACTURACIÓN AS"
            self.company_rif = "RIF: N/A"
            self.company_address = "Domicilio fiscal: N/A"
            self.company_phone = "Teléfono: N/A"

    def query_dolar_api(self, source_type="oficial"):
        """Consulta la API de ve.dolarapi.com para obtener la tasa de cambio oficial del BCV.
        Retorna (tasa, None) en éxito, o (None, error_str) en caso de error.
        """
        import urllib.request
        import urllib.error
        import json
        
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    res_bytes = response.read()
                    data = json.loads(res_bytes.decode('utf-8'))
                    rate = data.get('promedio') or data.get('venta') or data.get('compra')
                    if rate:
                        return float(rate), None
                    return None, "No se encontró un valor de tasa en la respuesta"
                else:
                    return None, f"Error HTTP: {response.status}"
        except urllib.error.URLError as e:
            return None, f"Error de red: {e.reason}"
        except Exception as e:
            return None, f"Error: {str(e)}"

    def start_auto_update_loop(self):
        """Inicia el temporizador de auto-actualización de la tasa de cambio"""
        self.check_and_perform_auto_update()

    def check_and_perform_auto_update(self):
        """Verifica si está activa la opción de auto-actualización y realiza la consulta en segundo plano"""
        if getattr(self, "auto_update_rate", False):
            import threading
            def run():
                rate, err = self.query_dolar_api("oficial")
                if rate is not None:
                    self.after(0, lambda: self.apply_auto_updated_rate(rate))
            threading.Thread(target=run, daemon=True).start()
        
        # Programar próxima consulta para dentro de 30 minutos (1800000 ms)
        self.after(1800000, self.check_and_perform_auto_update)

    def apply_auto_updated_rate(self, rate):
        """Aplica la tasa auto-actualizada y la persiste"""
        self.exchange_rate = rate
        self.rate_source = "oficial"
        self.save_data()
        print(f"INFO: Tasa auto-actualizada BCV a {rate:.2f} VES")

    def trigger_immediate_auto_update(self):
        """Fuerza una consulta inmediata de auto-actualización"""
        import threading
        def run():
            rate, err = self.query_dolar_api("oficial")
            if rate is not None:
                self.after(0, lambda: self.apply_auto_updated_rate(rate))
        threading.Thread(target=run, daemon=True).start()


class SplashScreen(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("")
        self.overrideredirect(True)  # Sin barra de título para look minimalista
        self.attributes("-topmost", True)
        
        w, h = 440, 360
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.configure(bg="#FFFFFF")
        
        # Canvas para la animación
        self.canvas = tk.Canvas(self, width=w, height=h, bg="#FFFFFF", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Logo (si existe)
        self.logo_photo = None
        logo_y = 80
        try:
            if os.path.exists("img/logo.png"):
                logo_img = Image.open("img/logo.png")
                logo_img = logo_img.resize((100, 100), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                self.canvas.create_image(w // 2, logo_y, image=self.logo_photo)
                logo_y += 80 # Bajar el texto si hay logo
        except Exception as e:
            print(f"Error loading logo in splash: {e}")
            logo_y = 80

        # Título (aparece con fade-in)
        self.title_id = self.canvas.create_text(
            w // 2, logo_y, text="Facturación AS",
            font=("Segoe UI", 28, "bold"), fill="#FFFFFF"  # empieza invisible
        )
        # Subtítulo
        self.sub_id = self.canvas.create_text(
            w // 2, logo_y + 40, text="3.3v",
            font=("Segoe UI", 14), fill="#FFFFFF"
        )
        
        # Puntos de carga animados
        self.dots = []
        dot_y = logo_y + 80
        dot_spacing = 18
        start_x = w // 2 - dot_spacing * 1.5
        for i in range(4):
            dot = self.canvas.create_oval(
                start_x + i * dot_spacing - 4, dot_y - 4,
                start_x + i * dot_spacing + 4, dot_y + 4,
                fill="#E2E8F0", outline=""
            )
            self.dots.append(dot)
        
        # Línea de progreso minimalista
        bar_y = dot_y + 40
        bar_w = 200
        bar_x = (w - bar_w) // 2
        self.canvas.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + 3,
                                      fill="#F1F5F9", outline="")
        self.progress_bar = self.canvas.create_rectangle(
            bar_x, bar_y, bar_x, bar_y + 3,
            fill="#2563EB", outline=""
        )
        self.bar_x = bar_x
        self.bar_w = bar_w
        self.bar_y = bar_y
        
        # Estado de animación
        self._progress = 0
        self._dot_step = 0
        self._fade_step = 0
        
        # Iniciar animaciones
        self.after(50, self._animate_fade_in)
        self.after(200, self._animate_dots)
        self.after(100, self._animate_progress)
    
    def _animate_fade_in(self):
        """Fade-in del texto título"""
        if not self.winfo_exists():
            return
        self._fade_step += 1
        steps = 15
        if self._fade_step <= steps:
            # Interpolar de blanco (#FFFFFF) a color final
            t = self._fade_step / steps
            title_r = int(255 - t * (255 - 0x1E))
            title_g = int(255 - t * (255 - 0x29))
            title_b = int(255 - t * (255 - 0x3B))
            sub_r = int(255 - t * (255 - 0x64))
            sub_g = int(255 - t * (255 - 0x74))
            sub_b = int(255 - t * (255 - 0x8B))
            self.canvas.itemconfig(self.title_id,
                                    fill=f"#{title_r:02x}{title_g:02x}{title_b:02x}")
            self.canvas.itemconfig(self.sub_id,
                                    fill=f"#{sub_r:02x}{sub_g:02x}{sub_b:02x}")
            self.after(30, self._animate_fade_in)
    
    def _animate_dots(self):
        """Pulsar los puntos secuencialmente"""
        if not self.winfo_exists():
            return
        active = self._dot_step % 4
        for i, dot in enumerate(self.dots):
            self.canvas.itemconfig(dot, fill="#2563EB" if i == active else "#E2E8F0")
        self._dot_step += 1
        if self._progress < 100:
            self.after(250, self._animate_dots)
        else:
            for dot in self.dots:
                self.canvas.itemconfig(dot, fill="#2563EB")
    
    def _animate_progress(self):
        """Avance suave de la barra de progreso"""
        if not self.winfo_exists():
            return
        self._progress += 4
        if self._progress > 100:
            self._progress = 100
        fill_w = int(self.bar_w * self._progress / 100)
        self.canvas.coords(self.progress_bar,
                           self.bar_x, self.bar_y,
                           self.bar_x + fill_w, self.bar_y + 3)
        if self._progress < 100:
            self.after(50, self._animate_progress)
        else:
            self.after(400, self._fade_out)
    
    def _fade_out(self, alpha=1.0):
        """Fade-out suave al terminar"""
        if not self.winfo_exists():
            return
        alpha -= 0.08
        if alpha <= 0:
            safe_destroy(self)
            return
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            safe_destroy(self)
            return
        self.after(16, lambda: self._fade_out(alpha))


class LoginWindow(ctk.CTkToplevel):
    def __init__(self, on_login_success, master=None):
        super().__init__(master)
        self.on_login_success = on_login_success
        self.title("Iniciar Sesión")
        self.resizable(True, True)
        self.minsize(420, 580)

        # Centrar inicial
        self.update_idletasks()
        self.w = 420
        self.h = 480
        
        x = (self.winfo_screenwidth() // 2) - (self.w // 2)
        y = (self.winfo_screenheight() // 2) - (self.h // 2)
        self.geometry(f"{self.w}x{self.h}+{x}+{y}")

        # --- Contenedor Principal Responsivo ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=0, sticky="nsew")
        
        # Frame central para mantener el contenido agrupado
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_frame.place(relx=0.5, rely=0.5, anchor="center")

        # --- Contenido centrado ---
        # Logo
        try:
            if os.path.exists("img/logo.png"):
                logo_img = Image.open("img/logo.png")
                self.logo_img = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(80, 80))
                ctk.CTkLabel(self.content_frame, text="", image=self.logo_img).pack(pady=(20, 0))
        except Exception as e:
            print(f"Error loading logo in login: {e}")

        # Título
        ctk.CTkLabel(self.content_frame, text="Facturación AS", font=("Segoe UI", 24, "bold")).pack(pady=(10, 5))
        ctk.CTkLabel(self.content_frame, text="Inicia sesión para continuar", font=("Segoe UI", 12),
                     text_color=("#64748B", "#94A3B8")).pack(pady=(0, 20))

        # Card de login
        card = ctk.CTkFrame(self.content_frame, corner_radius=12, width=340)
        card.pack(padx=40, fill="x")
        card.pack_propagate(False)
        card.configure(height=290) # Altura fija para la card de login ajustada para dos botones

        ctk.CTkLabel(card, text="Usuario", font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x", padx=20, pady=(18, 4))
        self.username_entry = ctk.CTkEntry(card, height=38, corner_radius=8,
                                           placeholder_text="Ingrese su usuario")
        self.username_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(card, text="Contraseña", font=("Segoe UI", 11, "bold"),
                     anchor="w").pack(fill="x", padx=20, pady=(14, 4))
        
        pass_frame = ctk.CTkFrame(card, fg_color="transparent")
        pass_frame.pack(fill="x", padx=20)
        
        self.password_entry = ctk.CTkEntry(pass_frame, height=38, corner_radius=8,
                                           placeholder_text="Ingrese su contraseña", show="*")
        self.password_entry.pack(side="left", fill="x", expand=True)
        
        self.pass_toggle_btn = ctk.CTkButton(pass_frame, text="🔒", width=35, height=38, 
                                            corner_radius=8, fg_color="transparent", 
                                            text_color=("#64748B", "#94A3B8"),
                                            hover_color=("#E2E8F0", "#2A2A3C"),
                                            command=lambda: toggle_password_visibility(self.password_entry, self.pass_toggle_btn))
        self.pass_toggle_btn.pack(side="right", padx=(5, 0))

        # Botón principal
        ctk.CTkButton(card, text="Iniciar Sesión", command=self.login,
                     corner_radius=8, height=40,
                     fg_color="#2563EB", hover_color="#1D4ED8",
                     font=("Segoe UI", 13, "bold")).pack(fill="x", padx=20, pady=(20, 8))

        # Botón secundario
        ctk.CTkButton(card, text="Registrarse", command=self.open_register,
                     corner_radius=8, height=40,
                     fg_color="#059669", hover_color="#047857",
                     font=("Segoe UI", 12, "bold")).pack(fill="x", padx=20, pady=(0, 10))

        # Botón toggle para usuarios (Abrir ventana independiente)
        self.toggle_btn = ctk.CTkButton(self.content_frame, text="👥 Seleccionar Usuario Registrado", 
                                       command=self.open_user_selection,
                                       fg_color="transparent", text_color=("#64748B", "#94A3B8"),
                                       font=("Segoe UI", 11), hover_color=("#E2E8F0", "#2A2A3C"),
                                       width=200)
        self.toggle_btn.pack(pady=(15, 0))

        # Atajos de teclado en login (Enter para avanzar o iniciar sesión)
        def on_user_enter(event=None):
            if self.username_entry.get().strip() and not self.password_entry.get():
                self.password_entry.focus()
            else:
                self.login()

        self.username_entry.bind("<Return>", on_user_enter)
        self.password_entry.bind("<Return>", lambda e: self.login())
        self.bind("<Return>", lambda e: self.login())

        self.username_entry.focus()

        # Fade-in animation
        self.attributes("-alpha", 0.0)
        self._fade_in()

    def open_user_selection(self):
        """Abrir la ventana de selección de usuarios"""
        UserSelectionWindow(self)

    def select_user(self, username):
        """Rellenar los campos con el usuario seleccionado"""
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, username)
        self.password_entry.delete(0, tk.END)
        self.password_entry.focus()

    def _fade_in(self, alpha=0.0):
        """Animación de fade-in sutil"""
        if alpha < 1.0:
            alpha = min(alpha + 0.06, 1.0)
            try:
                self.attributes("-alpha", alpha)
            except Exception:
                return
            self.after(16, lambda: self._fade_in(alpha))

    def login(self, event=None):
        username = self.username_entry.get()
        password = self.password_entry.get()
        success, role = db.authenticate_user(username, password)
        if success:
            ModernMessageBox.showinfo("Éxito", f"Bienvenido, {username}!")
            safe_destroy(self)
            self.on_login_success(role)
        else:
            ModernMessageBox.showerror("Error", "Usuario o contraseña incorrectos")
            # Agitar animación sutil
            self._shake()

    def _shake(self, count=0):
        """Animación de shake sutil en error de login"""
        if count >= 6:
            return
        try:
            x = self.winfo_x()
            offset = 8 if count % 2 == 0 else -8
            self.geometry(f"+{x + offset}+{self.winfo_y()}")
            self.after(50, lambda: self._shake(count + 1))
        except Exception:
            pass

    def open_register(self):
        """Abrir la ventana de registro independiente"""
        RegisterWindow(self)

    def register(self):
        # Esta función ahora es reemplazada por open_register, pero se mantiene por compatibilidad si se llama internamente
        self.open_register()



class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Registro de Usuario")
        self.geometry("600x700")
        self.resizable(False, False)
        self.configure(fg_color=("#F8FAFC", "#1A1A2E")) # Adaptable
        self.transient(parent)
        self.grab_set()
        fade_in_window(self)

        # Centrar
        self.update_idletasks()
        w, h = 600, 700
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Título
        ctk.CTkLabel(self, text="Registro de Nuevo Usuario", 
                     font=("Segoe UI", 24, "bold"), 
                     text_color=("#1E293B", "white")).pack(pady=(30, 40))

        # Contenedor de Formulario
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(padx=50, fill="both", expand=True)

        # Campos
        fields = [
            ("Nombre Completo", "full_name"),
            ("Correo Electrónico", "email"),
            ("Usuario", "username"),
            ("Contraseña", "password"),
            ("Confirmar Contraseña", "confirm_password"),
            ("Área de Experiencia", "area")
        ]

        self.entries = {}
        for label_text, var_name in fields:
            row = ctk.CTkFrame(form_frame, fg_color="transparent")
            row.pack(fill="x", pady=8)
            
            ctk.CTkLabel(row, text=label_text, width=150, anchor="w", 
                         font=("Segoe UI", 12), 
                         text_color=("#64748B", "#A0A0B8")).pack(side="left")
            
            show_char = "*" if "password" in var_name else ""
            entry = ctk.CTkEntry(row, height=35, corner_radius=6, 
                                 fg_color=("#FFFFFF", "#2A2A3C"), 
                                 border_color=("#E2E8F0", "#3F3F5F"), 
                                 text_color=("#1E293B", "white"),
                                 placeholder_text=f"Ingrese {label_text.lower()}")
            if show_char: 
                entry.configure(show=show_char)
                entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
                
                # Botón de toggle individual para cada campo de contraseña
                toggle_btn = ctk.CTkButton(row, text="🔒", width=35, height=35, 
                                          corner_radius=6, fg_color="transparent", 
                                          text_color=("#64748B", "#94A3B8"),
                                          hover_color=("#E2E8F0", "#2A2A3C"),
                                          font=("Segoe UI", 12))
                toggle_btn.configure(command=lambda e=entry, b=toggle_btn: toggle_password_visibility(e, b))
                toggle_btn.pack(side="right", padx=(5, 0))
            else:
                entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
            
            self.entries[var_name] = entry

        # Rol
        rol_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        rol_row.pack(fill="x", pady=20)
        ctk.CTkLabel(rol_row, text="Rol:", width=150, anchor="w", 
                     font=("Segoe UI", 12, "bold"), 
                     text_color=("#64748B", "#A0A0B8")).pack(side="left")
        
        self.role_var = tk.StringVar(value="empleado")
        ctk.CTkRadioButton(rol_row, text="Empleado", variable=self.role_var, value="empleado", 
                           text_color=("#1E293B", "white"), fg_color="#2563EB").pack(side="left", padx=10)
        ctk.CTkRadioButton(rol_row, text="Administrador", variable=self.role_var, value="admin", 
                           text_color=("#1E293B", "white"), fg_color="#2563EB").pack(side="left", padx=10)

        # Botones
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=40)

        ctk.CTkButton(btn_frame, text="Registrarse", command=self.do_register,
                     width=140, height=40, corner_radius=8,
                     fg_color="#2563EB", hover_color="#1D4ED8",
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=10)

        ctk.CTkButton(btn_frame, text="Cancelar", command=self.destroy,
                     width=140, height=40, corner_radius=8,
                     fg_color=("#94A3B8", "#475569"), hover_color=("#64748B", "#334155"),
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=10)

        # Vincular teclas Enter y Escape
        self.bind("<Return>", lambda e: self.do_register())
        self.bind("<Escape>", lambda e: self.destroy())

    def do_register(self):
        data = {k: v.get() for k, v in self.entries.items()}
        role = self.role_var.get()

        if not data["username"] or not data["password"]:
            ModernMessageBox.showerror("Error", "Usuario y Contraseña son obligatorios", parent=self)
            return

        if data["password"] != data["confirm_password"]:
            ModernMessageBox.showerror("Error", "Las contraseñas no coinciden", parent=self)
            return

        try:
            success = db.create_user(
                username=data["username"],
                password=data["password"],
                role=role,
                full_name=data["full_name"],
                email=data["email"],
                institution=data.get("institution", ""),
                area=data["area"]
            )
            if success:
                ModernMessageBox.showinfo("Éxito", "Usuario registrado correctamente", parent=self)
                self.destroy()
                # Notificar al padre para refrescar la lista de usuarios si la tiene
                if hasattr(self.master, "refresh_user_list"):
                    try:
                        self.master.refresh_user_list()
                    except Exception:
                        pass
            else:
                ModernMessageBox.showerror("Error", "El usuario ya existe o hubo un problema", parent=self)
        except Exception as e:
            ModernMessageBox.showerror("Error", f"Error en el registro: {e}", parent=self)


class EditUserWindow(ctk.CTkToplevel):
    def __init__(self, parent, username):
        super().__init__(parent)
        self.parent = parent
        self.username = username
        self.title(f"Editar Perfil: {username}")
        self.geometry("600x750")
        self.resizable(False, False)
        self.configure(fg_color=("#F8FAFC", "#1A1A2E"))
        self.transient(parent)
        self.grab_set()
        fade_in_window(self)

        # Centrar
        self.update_idletasks()
        w, h = 600, 750
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        user_data = db.get_user_by_username(username)

        # Header elegante
        ctk.CTkLabel(self, text=f"Editando Usuario: {username}", 
                     font=("Segoe UI", 22, "bold"), 
                     text_color=("#1E293B", "white")).pack(pady=(30, 20))

        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(padx=50, fill="both", expand=True)

        # Configuración de campos
        fields = [
            ("Nombre Completo", "full_name"),
            ("Correo Electrónico", "email"),
            ("Área de Experiencia", "area"),
            ("Institución", "institution"),
            ("Nueva Contraseña (opcional)", "password"),
            ("Confirmar Nueva Contraseña", "confirm_password")
        ]

        self.entries = {}
        for label_text, var_name in fields:
            row = ctk.CTkFrame(form_frame, fg_color="transparent")
            row.pack(fill="x", pady=8)
            
            ctk.CTkLabel(row, text=label_text, width=170, anchor="w", 
                         font=("Segoe UI", 12), 
                         text_color=("#64748B", "#A0A0B8")).pack(side="left")
            
            show_char = "*" if "password" in var_name else ""
            entry = ctk.CTkEntry(row, height=35, corner_radius=6, 
                                 fg_color=("#FFFFFF", "#2A2A3C"), 
                                 border_color=("#E2E8F0", "#3F3F5F"), 
                                 text_color=("#1E293B", "white"))
            
            # Pre-rellenar datos existentes si no es campo de contraseña
            if "password" not in var_name and var_name in user_data:
                entry.insert(0, user_data[var_name] or "")
                
            if show_char: 
                entry.configure(show=show_char)
                entry.pack(side="left", fill="x", expand=True)
                
                # Botón de visibilidad
                toggle_btn = ctk.CTkButton(row, text="🔒", width=35, height=35, 
                                          corner_radius=6, fg_color="transparent", 
                                          text_color=("#64748B", "#94A3B8"),
                                          hover_color=("#E2E8F0", "#2A2A3C"),
                                          font=("Segoe UI", 12))
                toggle_btn.configure(command=lambda e=entry, b=toggle_btn: toggle_password_visibility(e, b))
                toggle_btn.pack(side="right", padx=(5, 0))
            else:
                entry.pack(side="left", fill="x", expand=True)
            
            self.entries[var_name] = entry

        # Selección de Rol
        rol_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        rol_row.pack(fill="x", pady=20)
        ctk.CTkLabel(rol_row, text="Rol del Usuario:", width=170, anchor="w", 
                     font=("Segoe UI", 12, "bold"), 
                     text_color=("#64748B", "#A0A0B8")).pack(side="left")
        
        self.role_var = tk.StringVar(value=user_data.get('role', 'empleado'))
        ctk.CTkRadioButton(rol_row, text="Empleado", variable=self.role_var, value="empleado", 
                           text_color=("#1E293B", "white"), fg_color="#2563EB").pack(side="left", padx=10)
        ctk.CTkRadioButton(rol_row, text="Administrador", variable=self.role_var, value="admin", 
                           text_color=("#1E293B", "white"), fg_color="#2563EB").pack(side="left", padx=10)

        # Botones de Acción
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=30)

        ctk.CTkButton(btn_frame, text="GUARDAR CAMBIOS", command=self.save_edits,
                     width=180, height=45, corner_radius=10,
                     fg_color="#10B981", hover_color="#059669",
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=15)

        ctk.CTkButton(btn_frame, text="CANCELAR", command=self.destroy,
                     width=180, height=45, corner_radius=10,
                     fg_color=("#94A3B8", "#475569"), hover_color=("#64748B", "#334155"),
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=15)

    def save_edits(self):
        data = {k: v.get() for k, v in self.entries.items()}
        role = self.role_var.get()

        # Validación de contraseña si se intentó cambiar
        if data["password"] and data["password"] != data["confirm_password"]:
            ModernMessageBox.showerror("Error", "Las nuevas contraseñas no coinciden entre sí.", parent=self)
            return

        try:
            success = db.update_user(
                username=self.username,
                password=data["password"] if data["password"] else None,
                role=role,
                full_name=data["full_name"],
                email=data["email"],
                institution=data["institution"],
                area=data["area"]
            )
            if success:
                ModernMessageBox.showinfo("Éxito", f"El perfil de '{self.username}' ha sido actualizado.", parent=self)
                if hasattr(self.parent, "refresh_user_list"):
                    self.parent.refresh_user_list()
                self.destroy()
            else:
                ModernMessageBox.showerror("Error", "No se pudieron guardar los cambios en la base de datos.", parent=self)
        except Exception as e:
            ModernMessageBox.showerror("Error", f"Ocurrió un error inesperado: {e}", parent=self)

class UserSelectionWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Gestión de Usuarios")
        self.geometry("700x550")
        self.resizable(False, False)
        self.configure(fg_color=("#F1F5F9", "#0F172A")) # Slate background
        self.transient(parent)
        self.grab_set()
        fade_in_window(self)

        # Centrar
        self.update_idletasks()
        w, h = 700, 550
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Header elegante
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(30, 20))
        
        ctk.CTkLabel(header_frame, text="Gestión de Acceso", 
                     font=("Segoe UI", 24, "bold"),
                     text_color=("#1E293B", "#F8FAFC")).pack()
        ctk.CTkLabel(header_frame, text="Seleccione un usuario para iniciar sesión o gestionar la lista", 
                     font=("Segoe UI", 13),
                     text_color=("#64748B", "#94A3B8")).pack()

        # Contenedor principal con sombra simulada (borde)
        main_container = ctk.CTkFrame(self, corner_radius=15, 
                                     fg_color=("#FFFFFF", "#1E293B"),
                                     border_width=1, border_color=("#E2E8F0", "#334155"))
        main_container.pack(padx=30, fill="both", expand=True)

        # Estilo para Treeview (Row height)
        style = ttk.Style()
        style.configure("User.Treeview", rowheight=35, font=("Segoe UI", 11))
        style.configure("User.Treeview.Heading", font=("Segoe UI", 11, "bold"))

        # Frame para la tabla
        table_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        table_frame.pack(padx=15, pady=15, fill="both", expand=True)

        columns = ("Usuario", "Nombre Completo", "Rol")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", 
                                style="User.Treeview")
        
        self.tree.heading("Usuario", text="USUARIO")
        self.tree.heading("Nombre Completo", text="NOMBRE COMPLETO")
        self.tree.heading("Rol", text="ROL")
        
        self.tree.column("Usuario", width=120, anchor="center")
        self.tree.column("Nombre Completo", width=300, anchor="w")
        self.tree.column("Rol", width=120, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.select_and_close())
        self.tree.bind("<Return>", lambda e: self.select_and_close())
        self.tree.bind("<Delete>", lambda e: self.delete_user())
        self.tree.bind("<Button-3>", self.show_users_menu)
        self.bind("<Escape>", lambda e: self.destroy())

        # Scrollbar moderna
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Botones de acción (Más robustos)
        btn_container = ctk.CTkFrame(self, fg_color="transparent")
        btn_container.pack(fill="x", padx=30, pady=30)

        # Botón Seleccionar
        self.select_btn = ctk.CTkButton(
            btn_container, 
            text="✅ SELECCIONAR USUARIO", 
            command=self.select_and_close,
            height=50, 
            corner_radius=10,
            fg_color="#2563EB", 
            hover_color="#1D4ED8",
            font=("Segoe UI", 13, "bold")
        )
        self.select_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Botón Eliminar
        self.delete_btn = ctk.CTkButton(
            btn_container, 
            text="❌ ELIMINAR", 
            command=self.delete_user,
            height=50, 
            width=150,
            corner_radius=10,
            fg_color="#EF4444", 
            hover_color="#DC2626",
            font=("Segoe UI", 13, "bold")
        )
        self.delete_btn.pack(side="left", padx=(10, 0))

        self.refresh_user_list()

    def refresh_user_list(self):
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            users = db.get_users()
            for u in users:
                role_display = "🛡️ Admin" if u.get('role') == 'admin' else "👤 Empleado"
                self.tree.insert("", tk.END, values=(
                    u.get('username'), 
                    u.get('full_name', 'N/A'), 
                    role_display
                ))
        except Exception as e:
            print(f"Error refreshing users: {e}")

    def select_and_close(self):
        selected = self.tree.selection()
        if not selected:
            ModernMessageBox.showerror("Error", "Por favor, seleccione un usuario de la lista", parent=self)
            return
        if len(selected) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione un solo usuario para continuar.", parent=self)
            return
        
        username = self.tree.item(selected[0])['values'][0]
        self.parent.select_user(username)
        self.destroy()

    def delete_user(self, event=None):
        selected = self.tree.selection()
        if not selected:
            ModernMessageBox.showerror("Error", "Seleccione al menos un usuario para eliminar", parent=self)
            return
        
        usernames = [self.tree.item(s)['values'][0] for s in selected]
        if "admin" in usernames:
            ModernMessageBox.showwarning("Acceso Denegado", "El usuario 'admin' es vital para el sistema y no puede ser eliminado.", parent=self)
            usernames = [u for u in usernames if u != "admin"]
            if not usernames:
                return
        
        if len(usernames) == 1:
            prompt_msg = f"¿Está seguro de eliminar permanentemente al usuario '{usernames[0]}'?\n\nPara confirmar, escriba la palabra: borrar"
        else:
            prompt_msg = f"¿Está seguro de eliminar permanentemente a los {len(usernames)} usuarios seleccionados ({', '.join(usernames)})?\n\nPara confirmar, escriba la palabra: borrar"

        # Diálogo de confirmación con palabra clave
        confirm_word = simpledialog.askstring(
            "Confirmar Eliminación Crítica", 
            prompt_msg,
            parent=self
        )

        if confirm_word and confirm_word.strip().lower() == "borrar":
            for u in usernames:
                db.delete_user(u)
            self.refresh_user_list()
            if len(usernames) == 1:
                ModernMessageBox.showinfo("Éxito", f"El usuario '{usernames[0]}' ha sido eliminado correctamente.", parent=self)
            else:
                ModernMessageBox.showinfo("Éxito", f"{len(usernames)} usuarios han sido eliminados correctamente.", parent=self)
        elif confirm_word is not None:
            ModernMessageBox.showerror("Error de Validación", "La palabra de confirmación es incorrecta. Acción cancelada.", parent=self)

    def show_users_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
            menu.add_command(label="📋 Consultar Datos", command=self.view_user_details)
            menu.add_command(label="✏️ Editar Usuario", command=self.open_edit_user)
            menu.add_separator()
            menu.add_command(label="❌ Eliminar Usuario", command=self.delete_user)
            menu.post(event.x_root, event.y_root)

    def view_user_details(self):
        selected = self.tree.selection()
        if not selected: return
        if len(selected) > 1:
            ModernMessageBox.showwarning("Atención", "Por favor, seleccione un solo usuario para consultar sus datos.", parent=self)
            return
        username = self.tree.item(selected[0])['values'][0]
        user_data = db.get_user_by_username(username)
        if user_data:
            details = f"👤 Usuario: {user_data['username']}\n\n"
            details += f"📝 Nombre: {user_data['full_name'] or 'N/A'}\n"
            details += f"✉️ Email: {user_data['email'] or 'N/A'}\n"
            details += f"🎭 Rol: {user_data['role'].capitalize()}\n"
            details += f"🏢 Institución: {user_data['institution'] or 'N/A'}\n"
            details += f"📍 Área: {user_data['area'] or 'N/A'}"
            ModernMessageBox.showinfo("Información de Usuario", details, parent=self)

    def open_edit_user(self):
        selected = self.tree.selection()
        if not selected: return
        if len(selected) > 1:
            ModernMessageBox.showwarning("Atención", "La edición debe realizarse estrictamente de uno en uno. Por favor, seleccione un solo usuario.", parent=self)
            return
        username = self.tree.item(selected[0])['values'][0]
        
        pwd = simpledialog.askstring("Autenticación Requerida", 
                                    f"Para editar al usuario '{username}', por favor ingrese SU CONTRASEÑA:", 
                                    show="*", parent=self)
        if pwd:
            success, _ = db.authenticate_user(username, pwd)
            if success:
                EditUserWindow(self, username)
            else:
                ModernMessageBox.showerror("Error", "Contraseña incorrecta. No puede editar este perfil.", parent=self)


# --- Punto de entrada principal ---
if __name__ == "__main__":
    # Inicializar base de datos
    db.init_db()
    
    # Crear raíz Tk oculta para evitar múltiples raíces
    root = tk.Tk()
    root.withdraw()
    
    # Splash screen
    splash = SplashScreen(root)
    splash.wait_window()
    
    # Login (usar la raíz oculta como master para evitar creación implícita)
    def start_app(role):
        BillingSystem(master=root, user_role=role)
    login = LoginWindow(start_app, master=root)

    # Ejecutar un único mainloop sobre la raíz
    root.mainloop()