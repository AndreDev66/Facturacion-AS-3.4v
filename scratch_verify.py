import os
import sys
import tkinter as tk
from unittest.mock import patch, MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"

# Import Main
import Main

print("=== INICIANDO PRUEBAS DE VERIFICACIÓN ===")

# 1. Probar LoginWindow
print("\n--- 1. Verificando LoginWindow ---")
root = tk.Tk()
root.withdraw()

login_called = []
def mock_on_success(role):
    login_called.append(role)

lw = Main.LoginWindow(mock_on_success, master=root)

# Comprobar que existen los bindings de Return
assert any("Return" in b for b in lw.bind()), "Falta bind <Return> en LoginWindow"
assert any("Return" in b for b in lw.username_entry._entry.bind()), "Falta bind <Return> en username_entry"
assert any("Return" in b for b in lw.password_entry._entry.bind()), "Falta bind <Return> en password_entry"

# Simular Enter en username cuando está vacío/lleno
lw.username_entry.insert(0, "testuser")
with patch.object(Main.db, 'authenticate_user', return_value=(False, None)) as mock_auth:
    lw.password_entry._entry.focus_force()
    lw.password_entry._entry.event_generate("<Return>", keysym="Return", keycode=13)
    lw.update()
    mock_auth.assert_called()

print("✓ Bindings y comportamiento de Enter en LoginWindow verificados.")
lw.destroy()

# 2. Probar Main App y Navegación de Pestañas
print("\n--- 2. Verificando Atajos en Main App ---")
with patch.object(Main.db, "init_db"), \
     patch.object(Main.Main, "start_auto_update_loop"), \
     patch.object(Main.Main, "load_main_logo"), \
     patch.object(Main.Main, "_fade_in"):
    
    app = Main.Main(user_role="admin")
    app.withdraw()

    # Comprobar bindings globales
    all_binds = app.bind_all()
    assert any("Control" in b and "Tab" in b for b in all_binds), "Falta <Control-Tab>"
    assert any("Shift" in b and "Tab" in b for b in all_binds) or any("ISO_Left_Tab" in b for b in all_binds), "Falta <Control-Shift-Tab>"
    assert any("Control" in b and "1" in b for b in all_binds), "Falta <Control-Key-1>"
    assert any("Escape" in b for b in all_binds), "Falta <Escape>"

    # Probar navegación de pestañas
    app.tab_control.select(0)
    assert app.tab_control.index(app.tab_control.select()) == 0
    
    # Siguiente pestaña
    app.switch_tab_next()
    assert app.tab_control.index(app.tab_control.select()) == 1
    
    # Pestaña previa
    app.switch_tab_prev()
    assert app.tab_control.index(app.tab_control.select()) == 0
    
    # Salto directo a pestaña 3 (Facturas, index 3)
    app.switch_tab_index(3)
    assert app.tab_control.index(app.tab_control.select()) == 3
    print("✓ Cambio de pestañas con Ctrl+Tab, Ctrl+Shift+Tab y salto numérico funcionando.")

    # 3. Probar Carrito POS: eliminación múltiple
    print("\n--- 3. Verificando eliminación múltiple en Carrito POS ---")
    app.current_invoice_items = [
        {"product": "Item 1", "quantity": 1, "price": 10.0, "total": 10.0},
        {"product": "Item 2", "quantity": 2, "price": 5.0, "total": 10.0},
        {"product": "Item 3", "quantity": 1, "price": 15.0, "total": 15.0},
    ]
    app.refresh_invoice_tree()
    children = app.invoice_tree.get_children()
    assert len(children) == 3

    # Seleccionar items 0 y 2
    app.invoice_tree.selection_set(children[0], children[2])
    app.remove_selected_invoice_item()
    assert len(app.current_invoice_items) == 1
    assert app.current_invoice_items[0]["product"] == "Item 2"
    print("✓ Eliminación múltiple en carrito POS funcionando correctamente.")

    # 4. Probar Inventario: edición estricta 1 a 1 y borrado múltiple
    print("\n--- 4. Verificando Inventario ---")
    app.products = [
        {"id": 1, "code": "P1", "name": "Prod 1", "category": "General", "purchase_price": 5, "price": 10, "stock": 50, "min_stock": 5, "location": "A", "supplier": "S", "notes": ""},
        {"id": 2, "code": "P2", "name": "Prod 2", "category": "General", "purchase_price": 5, "price": 10, "stock": 50, "min_stock": 5, "location": "A", "supplier": "S", "notes": ""},
        {"id": 3, "code": "P3", "name": "Prod 3", "category": "General", "purchase_price": 5, "price": 10, "stock": 50, "min_stock": 5, "location": "A", "supplier": "S", "notes": ""},
    ]
    app.refresh_inventory()
    inv_children = app.inventory_tree.get_children()
    assert len(inv_children) == 3

    # Edición con múltiples seleccionados debe mostrar advertencia y no abrir diálogo
    app.inventory_tree.selection_set(inv_children[0], inv_children[1])
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.open_edit_product_dialog()
        mock_warn.assert_called_once()
        assert "estrictamente de uno en uno" in mock_warn.call_args[0][1]

    # Borrado múltiple de productos 1 y 2
    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo"):
        app.delete_product()
        remaining_ids = [p["id"] for p in app.products]
        assert remaining_ids == [3], f"Esperado solo [3], obtenido: {remaining_ids}"
    print("✓ Inventario: restricción 1 a 1 en edición y borrado múltiple verificados.")

    # 5. Probar Clientes: edición estricta 1 a 1 y borrado múltiple
    print("\n--- 5. Verificando Clientes ---")
    app.clients = [
        {"id": 1, "name": "Cliente 1", "rif_ci": "V1", "type": "General", "phone": "", "email": "", "address": "", "city": "", "state": "", "postal_code": "", "notes": ""},
        {"id": 2, "name": "Cliente 2", "rif_ci": "V2", "type": "General", "phone": "", "email": "", "address": "", "city": "", "state": "", "postal_code": "", "notes": ""},
        {"id": 3, "name": "Cliente 3", "rif_ci": "V3", "type": "General", "phone": "", "email": "", "address": "", "city": "", "state": "", "postal_code": "", "notes": ""},
    ]
    app.refresh_clients()
    cli_children = app.clients_tree.get_children()
    assert len(cli_children) == 3

    # Edición con múltiples seleccionados debe mostrar advertencia
    app.clients_tree.selection_set(cli_children[0], cli_children[1])
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.open_edit_client_dialog()
        mock_warn.assert_called_once()
        assert "estrictamente de uno en uno" in mock_warn.call_args[0][1]

    # Borrado múltiple de clientes 1 y 2
    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo"):
        app.delete_client()
        rem_cli_ids = [c["id"] for c in app.clients]
        assert rem_cli_ids == [3], f"Esperado solo [3], obtenido: {rem_cli_ids}"
    print("✓ Clientes: restricción 1 a 1 en edición y borrado múltiple verificados.")

    # 6. Probar Facturas: acciones 1 a 1 y borrado múltiple
    print("\n--- 6. Verificando Facturas ---")
    app.invoices = [
        {"number": 1001, "date": "11/09/2026", "client": "Cliente 1", "items": [], "subtotal": 10, "tax": 1.6, "total": 11.6, "status": "Pagada", "payment_method": "Efectivo"},
        {"number": 1002, "date": "11/09/2026", "client": "Cliente 2", "items": [], "subtotal": 20, "tax": 3.2, "total": 23.2, "status": "Pendiente", "payment_method": "Efectivo"},
        {"number": 1003, "date": "11/09/2026", "client": "Cliente 3", "items": [], "subtotal": 30, "tax": 4.8, "total": 34.8, "status": "Pendiente", "payment_method": "Efectivo"},
    ]
    app.refresh_invoices()
    inv_rows = app.invoices_tree.get_children()
    assert len(inv_rows) == 3

    # Probar que imprimir, ver detalle, marcar pagada y cancelar advierten si hay múltiples
    app.invoices_tree.selection_set(inv_rows[0], inv_rows[1])
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.print_invoice()
        assert mock_warn.called
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.view_invoice_detail()
        assert mock_warn.called
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.mark_invoice_as_paid()
        assert mock_warn.called
    with patch("tkinter.messagebox.showwarning") as mock_warn:
        app.cancel_invoice()
        assert mock_warn.called

    # Borrado múltiple de facturas 1001 y 1002
    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo"):
        app.delete_invoice()
        rem_invs = [inv["number"] for inv in app.invoices]
        assert rem_invs == [1003], f"Esperado solo [1003], obtenido: {rem_invs}"
    print("✓ Facturas: restricción 1 a 1 en acciones y borrado múltiple verificados.")

    # 7. Probar consulta exclusiva BCV
    print("\n--- 7. Verificando Tasa Exclusiva BCV ---")
    assert hasattr(app, "rate_source")
    assert app.rate_source == "oficial"
    print("✓ Tasa oficial BCV establecida por defecto.")

    app.destroy()

root.destroy()
print("\n=== TODAS LAS PRUEBAS PASARON SATISFACTORIAMENTE ===")
