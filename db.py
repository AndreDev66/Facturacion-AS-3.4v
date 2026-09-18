import sqlite3
import threading
from typing import List, Dict, Tuple, Any, Optional
import hashlib

import config


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Conexiones persistentes — se abren una sola vez por base de datos y se
# reutilizan en lugar de crear/cerrar una conexión en cada operación.
# ---------------------------------------------------------------------------
_connections: Dict[str, sqlite3.Connection] = {}
_connection_lock = threading.Lock()


def _connection(db_path: str) -> sqlite3.Connection:
    """Devuelve (creándola si hace falta) la conexión persistente de ``db_path``."""
    with _connection_lock:
        conn = _connections.get(db_path)
        if conn is None:
            conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
            _connections[db_path] = conn
        return conn


def close_connections() -> None:
    """Cierra todas las conexiones persistentes (llamar al salir)."""
    with _connection_lock:
        for conn in _connections.values():
            try:
                conn.close()
            except sqlite3.DatabaseError:
                pass
        _connections.clear()


def _rollback(db_path: str) -> None:
    """Descarta cualquier transacción pendiente de la conexión persistente."""
    conn = _connections.get(db_path)
    if conn is None:
        return
    try:
        conn.rollback()
    except sqlite3.DatabaseError:
        pass


class _PersistentContext:
    """Emula el `with sqlite3.connect(...) as conn:` pero reutiliza la conexión
    persistente: confirma al salir sin errores y revierte si hubo excepción."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self.conn: sqlite3.Connection

    def __enter__(self) -> sqlite3.Connection:
        self.conn = _connection(self._db_path)
        return self.conn

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is None:
            try:
                self.conn.commit()
            except sqlite3.DatabaseError:
                raise
        else:
            _rollback(self._db_path)
        return False


# ---------------------------------------------------------------------------
# Caché incremental de estado (evita reescribir filas sin cambios)
# ---------------------------------------------------------------------------
_STATE_CACHE: Dict[str, Dict[str, Any]] = {}


def _as_float(value: Any, default: float = 0.0) -> float:
    """Convierte ``value`` a float de forma defensiva."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """Convierte ``value`` a int de forma defensiva."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _product_signature(product: Dict[str, Any]) -> Tuple[Any, ...]:
    """Huella de comparación para detectar cambios en un producto."""
    return (
        product.get("code"), product.get("name"), product.get("category"),
        _as_float(product.get("purchase_price", 0)), _as_float(product.get("price", 0)),
        _as_int(product.get("stock", 0)), _as_int(product.get("min_stock", 5)),
        product.get("location"), product.get("supplier"), product.get("notes", ""),
        int(bool(product.get("tax_exempt", 0))),
    )


def _client_signature(client: Dict[str, Any]) -> Tuple[Any, ...]:
    """Huella de comparación para detectar cambios en un cliente."""
    return (
        client.get("name"), client.get("rif_ci"), client.get("type"),
        client.get("phone"), client.get("email"), client.get("address", ""),
        client.get("city"), client.get("state"), client.get("postal_code"),
        client.get("notes", ""), _as_int(client.get("credit_days", 0)),
        _as_float(client.get("balance", 0.0)), client.get("credit_start_date"),
    )


def _invoice_signature(invoice: Dict[str, Any], client_id: Optional[int]) -> Tuple[Any, ...]:
    """Huella de comparación para detectar cambios en una factura y sus hijos."""
    items = tuple(
        (
            item.get("product_id"), item.get("product"),
            _as_int(item.get("quantity", 0)),
            _as_float(item.get("price", 0)),
            _as_float(item.get("total", 0)),
            int(bool(item.get("tax_exempt", False))),
        )
        for item in invoice.get("items", [])
    )
    payments = tuple(
        (pay.get("date"), _as_float(pay.get("amount", 0)), pay.get("method"), pay.get("note"))
        for pay in invoice.get("payments", [])
    )
    documents = tuple(
        (doc.get("type"), doc.get("date"), _as_float(doc.get("amount", 0)), doc.get("reason"))
        for doc in invoice.get("documents", [])
    )
    return (
        invoice.get("number"), invoice.get("date"), client_id, invoice.get("client"),
        _as_float(invoice.get("subtotal", 0)), _as_float(invoice.get("tax", 0)),
        _as_float(invoice.get("total", 0)), invoice.get("payment_method", ""),
        invoice.get("status", ""), invoice.get("due_date"),
        int(bool(invoice.get("is_credit", 0))), _as_float(invoice.get("balance", 0.0)),
        invoice.get("cancel_method"), invoice.get("cancel_note"), invoice.get("exchange_rate"),
        items, payments, documents,
    )


def init_db(db_path: str = config.AppConfig.DB_PATH) -> None:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT NOT NULL,
                category TEXT,
                purchase_price REAL DEFAULT 0,
                price REAL DEFAULT 0,
                stock INTEGER DEFAULT 0,
                min_stock INTEGER DEFAULT 5,
                location TEXT,
                supplier TEXT,
                notes TEXT,
                tax_exempt INTEGER DEFAULT 0
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                rif_ci TEXT,
                type TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                postal_code TEXT,
                notes TEXT,
                credit_days INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                credit_start_date TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                full_name TEXT,
                email TEXT,
                institution TEXT,
                area TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                number INTEGER PRIMARY KEY,
                date TEXT,
                client_id INTEGER,
                client_name TEXT,
                subtotal REAL,
                tax REAL,
                total REAL,
                payment_method TEXT,
                status TEXT,
                due_date TEXT,
                is_credit INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                cancel_method TEXT,
                cancel_note TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
            """)

            # Tabla para registrar pagos
            cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number INTEGER,
                date TEXT,
                amount REAL,
                method TEXT,
                note TEXT,
                FOREIGN KEY (invoice_number) REFERENCES invoices(number)
            )
            """)

            # Tabla para notas de crédito/débito y devoluciones
            cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                invoice_number INTEGER,
                date TEXT,
                amount REAL,
                reason TEXT,
                FOREIGN KEY (invoice_number) REFERENCES invoices(number)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number INTEGER,
                product_id INTEGER,
                product_name TEXT,
                quantity INTEGER,
                price REAL,
                total REAL,
                tax_exempt INTEGER DEFAULT 0,
                FOREIGN KEY (invoice_number) REFERENCES invoices(number),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS store_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

            # En caso de no existir Usuario incializar por defecto con admin
            try:
                cur.execute("SELECT COUNT(*) FROM users")
                if cur.fetchone()[0] == 0:
                    cur.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                                ("admin", hash_password("admin"), "admin", "Administrador del Sistema"))
            except sqlite3.OperationalError:
                pass  

            # Migraciones para la tabla users
            try:
                cur.execute("PRAGMA table_info(users)")
                user_cols = [col[1] for col in cur.fetchall()]
                if 'full_name' not in user_cols:
                    cur.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
                if 'email' not in user_cols:
                    cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
                if 'institution' not in user_cols:
                    cur.execute("ALTER TABLE users ADD COLUMN institution TEXT")
                if 'area' not in user_cols:
                    cur.execute("ALTER TABLE users ADD COLUMN area TEXT")
            except sqlite3.DatabaseError as e:
                print(f"Error migrando tabla users: {e}")

            # Migraciones y actualizaciones de esquema
            try:
                cur.execute("PRAGMA table_info(clients)")
                columns = cur.fetchall()
                column_names = [col[1] for col in columns]
                if 'rfc' in column_names and 'rif_ci' not in column_names:
                    cur.execute("ALTER TABLE clients RENAME COLUMN rfc TO rif_ci")
                
                if 'credit_days' not in column_names:
                    cur.execute("ALTER TABLE clients ADD COLUMN credit_days INTEGER DEFAULT 0")
                if 'balance' not in column_names:
                    cur.execute("ALTER TABLE clients ADD COLUMN balance REAL DEFAULT 0")
                if 'credit_start_date' not in column_names:
                    cur.execute("ALTER TABLE clients ADD COLUMN credit_start_date TEXT")
            except sqlite3.DatabaseError as e:
                print(f"Error migrando tabla clients: {e}")

            try:
                cur.execute("PRAGMA table_info(products)")
                prod_cols = [c[1] for c in cur.fetchall()]
                if 'tax_exempt' not in prod_cols:
                    cur.execute("ALTER TABLE products ADD COLUMN tax_exempt INTEGER DEFAULT 0")
            except sqlite3.DatabaseError as e:
                print(f"Error migrando tabla products: {e}")

            try:
                cur.execute("PRAGMA table_info(invoices)")
                inv_cols = [c[1] for c in cur.fetchall()]
                for col_name, col_def in [
                    ('due_date', 'TEXT'),
                    ('is_credit', 'INTEGER DEFAULT 0'),
                    ('balance', 'REAL DEFAULT 0'),
                    ('cancel_method', 'TEXT'),
                    ('cancel_note', 'TEXT'),
                    ('client_id', 'INTEGER'),
                    ('client_name', 'TEXT'),
                    ('exchange_rate', 'REAL DEFAULT NULL')
                ]:
                    if col_name not in inv_cols:
                        print(f"DEBUG: Añadiendo columna {col_name} a tabla invoices...")
                        cur.execute(f"ALTER TABLE invoices ADD COLUMN {col_name} {col_def}")
                        conn.commit()
            except sqlite3.DatabaseError as e:
                print(f"Error migrando tabla invoices: {e}")

            try:
                cur.execute("PRAGMA table_info(invoice_items)")
                ii_cols = [c[1] for c in cur.fetchall()]
                if 'tax_exempt' not in ii_cols:
                    cur.execute("ALTER TABLE invoice_items ADD COLUMN tax_exempt INTEGER DEFAULT 0")
                    conn.commit()
                if 'product_id' not in ii_cols:
                    print("DEBUG: Añadiendo columna product_id a tabla invoice_items...")
                    cur.execute("ALTER TABLE invoice_items ADD COLUMN product_id INTEGER")
                    conn.commit()
                if 'product_name' not in ii_cols:
                    print("DEBUG: Añadiendo columna product_name a tabla invoice_items...")
                    cur.execute("ALTER TABLE invoice_items ADD COLUMN product_name TEXT")
                    conn.commit()
            except sqlite3.DatabaseError as e:
                print(f"Error migrando tabla invoice_items: {e}")

            conn.commit()
    except sqlite3.DatabaseError as e:
        print(f"CRITICAL ERROR initializing database: {e}")
        raise


def save_state(products: List[Dict[str, Any]], clients: List[Dict[str, Any]],
               invoices: List[Dict[str, Any]], invoice_counter: int,
               iva_rate: float = config.AppConfig.IVA_RATE,
               exchange_rate: float = config.AppConfig.EXCHANGE_RATE,
               include_pending_in_dashboard: bool = config.AppConfig.INCLUDE_PENDING_IN_DASHBOARD,
               auto_update_rate: bool = config.AppConfig.AUTO_UPDATE_RATE,
               rate_source: str = config.AppConfig.RATE_SOURCE,
               store_name: str = config.AppConfig.COMPANY_NAME,
               store_rif: str = "", store_address: str = "",
               store_phone: str = "",
               db_path: str = config.AppConfig.DB_PATH) -> None:
    """Persiste el estado de forma incremental.

    Solo escribe las filas nuevas o modificadas (UPSERT selectivo), elimina las
    que ya no existen y confirma por lotes para no reconstruir toda la base.
    """
    import time
    max_retries = 5
    batch_size = config.AppConfig.SAVE_BATCH_SIZE

    for attempt in range(max_retries):
        try:
            with _PersistentContext(db_path) as conn:
                cur = conn.cursor()
                cur.execute("BEGIN TRANSACTION")

                cache = _STATE_CACHE.setdefault(db_path, {})
                client_ids = {c.get("name"): c.get("id") for c in clients}
                product_ids = {p.get("name"): p.get("id") for p in products}
                pending = 0

                def flush(force: bool = False) -> None:
                    nonlocal pending
                    if force or pending >= batch_size:
                        conn.commit()
                        pending = 0

                # ---------------------- Productos ----------------------
                prev = cache.get("products", {})
                current: Dict[Any, Any] = {}
                product_rows = []
                for p in products:
                    pid = p.get("id")
                    sig = _product_signature(p)
                    row = (
                        pid, p.get("code"), p.get("name"), p.get("category"),
                        _as_float(p.get("purchase_price", 0)), _as_float(p.get("price", 0)),
                        _as_int(p.get("stock", 0)), _as_int(p.get("min_stock", 5)),
                        p.get("location"), p.get("supplier"), p.get("notes", ""),
                        int(bool(p.get("tax_exempt", 0))),
                    )
                    if pid is None:
                        product_rows.append(row)
                        continue
                    current[pid] = sig
                    if prev.get(pid) != sig:
                        product_rows.append(row)
                if product_rows:
                    cur.executemany(
                        "INSERT OR REPLACE INTO products (id, code, name, category, purchase_price, price, stock, min_stock, location, supplier, notes, tax_exempt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        product_rows,
                    )
                    pending += len(product_rows)
                stale_products = (set(prev) - set(current)) if prev else (
                    {row[0] for row in cur.execute("SELECT id FROM products")} - set(current)
                )
                stale_products.discard(None)
                if stale_products:
                    cur.executemany("DELETE FROM products WHERE id = ?", [(i,) for i in stale_products])
                    pending += len(stale_products)
                cache["products"] = current
                flush()

                # ---------------------- Clientes ----------------------
                prev = cache.get("clients", {})
                current = {}
                client_rows = []
                for c in clients:
                    cid = c.get("id")
                    sig = _client_signature(c)
                    row = (
                        cid, c.get("name"), c.get("rif_ci"), c.get("type"),
                        c.get("phone"), c.get("email"), c.get("address", ""),
                        c.get("city"), c.get("state"), c.get("postal_code"),
                        c.get("notes", ""), _as_int(c.get("credit_days", 0)),
                        _as_float(c.get("balance", 0.0)), c.get("credit_start_date"),
                    )
                    if cid is None:
                        client_rows.append(row)
                        continue
                    current[cid] = sig
                    if prev.get(cid) != sig:
                        client_rows.append(row)
                if client_rows:
                    cur.executemany(
                        "INSERT OR REPLACE INTO clients (id, name, rif_ci, type, phone, email, address, city, state, postal_code, notes, credit_days, balance, credit_start_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        client_rows,
                    )
                    pending += len(client_rows)
                stale_clients = (set(prev) - set(current)) if prev else (
                    {row[0] for row in cur.execute("SELECT id FROM clients")} - set(current)
                )
                stale_clients.discard(None)
                if stale_clients:
                    cur.executemany("DELETE FROM clients WHERE id = ?", [(i,) for i in stale_clients])
                    pending += len(stale_clients)
                cache["clients"] = current
                flush()

                # ---------------------- Facturas ----------------------
                prev = cache.get("invoices", {})
                current = {}
                for inv in invoices:
                    number = inv.get("number")
                    client_id = client_ids.get(inv.get("client"))
                    sig = _invoice_signature(inv, client_id)
                    if number is None:
                        condition = True
                    else:
                        current[number] = sig
                        condition = prev.get(number) != sig
                    if not condition:
                        continue
                    cur.execute(
                        "INSERT OR REPLACE INTO invoices (number, date, client_id, client_name, subtotal, tax, total, payment_method, status, due_date, is_credit, balance, cancel_method, cancel_note, exchange_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            number, inv.get("date"), client_id, inv.get("client"),
                            _as_float(inv.get("subtotal", 0)), _as_float(inv.get("tax", 0)),
                            _as_float(inv.get("total", 0)), inv.get("payment_method", ""),
                            inv.get("status", ""), inv.get("due_date"),
                            int(bool(inv.get("is_credit", 0))), _as_float(inv.get("balance", 0.0)),
                            inv.get("cancel_method"), inv.get("cancel_note"), inv.get("exchange_rate"),
                        ),
                    )
                    # Reescribir únicamente las filas hijas de esta factura
                    cur.execute("DELETE FROM invoice_items WHERE invoice_number = ?", (number,))
                    cur.execute("DELETE FROM payments WHERE invoice_number = ?", (number,))
                    cur.execute("DELETE FROM documents WHERE invoice_number = ?", (number,))

                    item_rows = [
                        (
                            number, product_ids.get(item.get("product")), item.get("product"),
                            _as_int(item.get("quantity", 0)), _as_float(item.get("price", 0)),
                            _as_float(item.get("total", 0)), int(bool(item.get("tax_exempt", False))),
                        )
                        for item in inv.get("items", [])
                    ]
                    if item_rows:
                        cur.executemany(
                            "INSERT INTO invoice_items (invoice_number, product_id, product_name, quantity, price, total, tax_exempt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            item_rows,
                        )
                    payment_rows = [
                        (number, pay.get("date"), _as_float(pay.get("amount", 0)), pay.get("method"), pay.get("note"))
                        for pay in inv.get("payments", [])
                    ]
                    if payment_rows:
                        cur.executemany(
                            "INSERT INTO payments (invoice_number, date, amount, method, note) VALUES (?, ?, ?, ?, ?)",
                            payment_rows,
                        )
                    document_rows = [
                        (doc.get("type"), number, doc.get("date"), _as_float(doc.get("amount", 0)), doc.get("reason"))
                        for doc in inv.get("documents", [])
                    ]
                    if document_rows:
                        cur.executemany(
                            "INSERT INTO documents (type, invoice_number, date, amount, reason) VALUES (?, ?, ?, ?, ?)",
                            document_rows,
                        )
                    pending += 1 + len(item_rows) + len(payment_rows) + len(document_rows)
                    flush()

                stale_invoices = (set(prev) - set(current)) if prev else (
                    {row[0] for row in cur.execute("SELECT number FROM invoices")} - set(current)
                )
                stale_invoices.discard(None)
                if stale_invoices:
                    for number in stale_invoices:
                        cur.execute("DELETE FROM invoice_items WHERE invoice_number = ?", (number,))
                        cur.execute("DELETE FROM payments WHERE invoice_number = ?", (number,))
                        cur.execute("DELETE FROM documents WHERE invoice_number = ?", (number,))
                        cur.execute("DELETE FROM invoices WHERE number = ?", (number,))
                    pending += len(stale_invoices)
                cache["invoices"] = current
                flush()

                # ---------------------- Metadatos y config ----------------------
                meta_rows = [
                    ("invoice_counter", str(invoice_counter)),
                    ("iva_rate", str(iva_rate)),
                    ("exchange_rate", str(exchange_rate)),
                    ("include_pending_in_dashboard", str(int(include_pending_in_dashboard))),
                    ("auto_update_rate", str(int(auto_update_rate))),
                    ("rate_source", str(rate_source)),
                ]
                cur.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", meta_rows)
                store_rows = [
                    ("rif", store_rif), ("fiscal_domicile", store_address),
                    ("store_name", store_name), ("phone", store_phone),
                ]
                cur.executemany("INSERT OR REPLACE INTO store_config (key, value) VALUES (?, ?)", store_rows)

                conn.commit()
                return
        except sqlite3.OperationalError as e:
            _STATE_CACHE.pop(db_path, None)
            _rollback(db_path)
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            print(f"Operational error saving state: {e}")
            raise
        except sqlite3.DatabaseError as e:
            _STATE_CACHE.pop(db_path, None)
            _rollback(db_path)
            print(f"Database error saving state: {e}")
            raise


def load_state(db_path: str = config.AppConfig.DB_PATH) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], int, float, float, bool, bool, str, str, str, str, str]:
    try:
        init_db(db_path)
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, code, name, category, purchase_price, price, stock, min_stock, location, supplier, notes, tax_exempt FROM products")
            products = [
                {
                    "id": row[0], "code": row[1], "name": row[2], "category": row[3],
                    "purchase_price": row[4], "price": row[5], "stock": row[6],
                    "min_stock": row[7], "location": row[8], "supplier": row[9],
                    "notes": row[10], "tax_exempt": bool(row[11])
                }
                for row in cur.fetchall()
            ]

            cur.execute("SELECT id, name, rif_ci, type, phone, email, address, city, state, postal_code, notes, credit_days, balance, credit_start_date FROM clients")
            clients = [
                {
                    "id": row[0], "name": row[1], "rif_ci": row[2], "type": row[3],
                    "phone": row[4], "email": row[5], "address": row[6],
                    "city": row[7], "state": row[8], "postal_code": row[9],
                    "notes": row[10], "credit_days": int(row[11]) if row[11] is not None else 0,
                    "balance": float(row[12]) if row[12] is not None else 0.0,
                    "credit_start_date": row[13]
                }
                for row in cur.fetchall()
            ]

            cur.execute("SELECT number, date, client_name, subtotal, tax, total, payment_method, status, due_date, is_credit, balance, cancel_method, cancel_note, client_id, exchange_rate FROM invoices ORDER BY number")
            invoice_rows = cur.fetchall()
            invoices = []
            for row in invoice_rows:
                number = row[0]
                cur.execute("SELECT product_name, quantity, price, total, tax_exempt, product_id FROM invoice_items WHERE invoice_number = ?", (number,))
                items = [{"product": it[0], "quantity": it[1], "price": it[2], "total": it[3], "tax_exempt": bool(it[4]), "product_id": it[5]} for it in cur.fetchall()]
                
                cur.execute("SELECT date, amount, method, note FROM payments WHERE invoice_number = ?", (number,))
                payments = [{"date": p[0], "amount": p[1], "method": p[2], "note": p[3]} for p in cur.fetchall()]

                cur.execute("SELECT type, date, amount, reason FROM documents WHERE invoice_number = ?", (number,))
                documents = [{"type": d[0], "date": d[1], "amount": d[2], "reason": d[3]} for d in cur.fetchall()]

                try:
                    inv_exchange_rate = float(row[14]) if row[14] is not None else None
                except (ValueError, TypeError):
                    inv_exchange_rate = None

                invoices.append({
                    "number": row[0], "date": row[1], "client": row[2], "subtotal": row[3],
                    "tax": row[4], "total": row[5], "payment_method": row[6], "status": row[7],
                    "due_date": row[8], "is_credit": bool(row[9]), "balance": float(row[10]) if row[10] is not None else 0.0,
                    "cancel_method": row[11], "cancel_note": row[12], "items": items, "payments": payments, "documents": documents, "client_id": row[13], "exchange_rate": inv_exchange_rate
                })

            cur.execute("SELECT value FROM meta WHERE key = ?", ("invoice_counter",))
            r = cur.fetchone()
            invoice_counter = int(r[0]) if r else config.AppConfig.INVOICE_COUNTER_START

            cur.execute("SELECT value FROM meta WHERE key = ?", ("iva_rate",))
            r = cur.fetchone()
            iva_rate = float(r[0]) if r else config.AppConfig.IVA_RATE

            cur.execute("SELECT value FROM meta WHERE key = ?", ("exchange_rate",))
            r = cur.fetchone()
            exchange_rate = float(r[0]) if r else config.AppConfig.EXCHANGE_RATE

            cur.execute("SELECT value FROM meta WHERE key = ?", ("include_pending_in_dashboard",))
            r = cur.fetchone()
            include_pending_in_dashboard = bool(int(r[0])) if r else config.AppConfig.INCLUDE_PENDING_IN_DASHBOARD

            cur.execute("SELECT value FROM meta WHERE key = ?", ("auto_update_rate",))
            r = cur.fetchone()
            auto_update_rate = bool(int(r[0])) if r else config.AppConfig.AUTO_UPDATE_RATE

            cur.execute("SELECT value FROM meta WHERE key = ?", ("rate_source",))
            r = cur.fetchone()
            rate_source = r[0] if r else config.AppConfig.RATE_SOURCE

            # Cargar configuración de tienda
            cur.execute("SELECT value FROM store_config WHERE key = ?", ("store_name",))
            r = cur.fetchone()
            store_name = r[0] if r else config.AppConfig.COMPANY_NAME

            cur.execute("SELECT value FROM store_config WHERE key = ?", ("rif",))
            r = cur.fetchone()
            company_rif = r[0] if r else config.AppConfig.COMPANY_RIF

            cur.execute("SELECT value FROM store_config WHERE key = ?", ("fiscal_domicile",))
            r = cur.fetchone()
            company_address = r[0] if r else config.AppConfig.COMPANY_ADDRESS

            cur.execute("SELECT value FROM store_config WHERE key = ?", ("phone",))
            r = cur.fetchone()
            company_phone = r[0] if r else config.AppConfig.COMPANY_PHONE

            return products, clients, invoices, invoice_counter, iva_rate, exchange_rate, include_pending_in_dashboard, auto_update_rate, rate_source, store_name, company_rif, company_address, company_phone
    except sqlite3.DatabaseError as e:
        print(f"Error loading state from database: {e}")
        return [], [], [], config.AppConfig.INVOICE_COUNTER_START, config.AppConfig.IVA_RATE, config.AppConfig.EXCHANGE_RATE, config.AppConfig.INCLUDE_PENDING_IN_DASHBOARD, config.AppConfig.AUTO_UPDATE_RATE, config.AppConfig.RATE_SOURCE, config.AppConfig.COMPANY_NAME, "", "", ""


def create_user(username: str, password: str, role: str = "empleado", 
                full_name: str = "", email: str = "", institution: str = "", area: str = "", 
                db_path: str = config.AppConfig.DB_PATH) -> bool:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash, role, full_name, email, institution, area) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (username, hash_password(password), role, full_name, email, institution, area))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.DatabaseError as e:
        print(f"Error creating user: {e}")
        return False

def authenticate_user(username: str, password: str, db_path: str = config.AppConfig.DB_PATH) -> Tuple[bool, str]:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?",
                        (username, hash_password(password)))
            result = cur.fetchone()
            if result:
                return True, result[0]
            return False, ""
    except sqlite3.DatabaseError as e:
        print(f"Error authenticating user: {e}")
        return False, ""

def get_users(db_path: str = config.AppConfig.DB_PATH) -> List[Dict[str, Any]]:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, username, role, full_name, email, institution, area FROM users")
            return [{"id": row[0], "username": row[1], "role": row[2], 
                     "full_name": row[3], "email": row[4], 
                     "institution": row[5], "area": row[6]} for row in cur.fetchall()]
    except sqlite3.DatabaseError as e:
        print(f"Error getting users: {e}")
        return []

def get_user_by_username(username: str, db_path: str = config.AppConfig.DB_PATH) -> Dict[str, Any]:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, username, role, full_name, email, institution, area FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if row:
                return {"id": row[0], "username": row[1], "role": row[2], 
                         "full_name": row[3], "email": row[4], 
                         "institution": row[5], "area": row[6]}
            return {}
    except sqlite3.DatabaseError as e:
        print(f"Error getting user by username: {e}")
        return {}

def update_user(username: str, password: Optional[str] = None, role: Optional[str] = None, 
                full_name: Optional[str] = None, email: Optional[str] = None, 
                institution: Optional[str] = None, 
                area: Optional[str] = None, db_path: str = config.AppConfig.DB_PATH) -> bool:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            
            update_fields = []
            params = []
            
            if password:
                update_fields.append("password_hash = ?")
                params.append(hash_password(password))
            
            if role:
                update_fields.append("role = ?")
                params.append(role)
                
            if full_name:
                update_fields.append("full_name = ?")
                params.append(full_name)
                
            if email:
                update_fields.append("email = ?")
                params.append(email)
                
            if institution:
                update_fields.append("institution = ?")
                params.append(institution)
                
            if area:
                update_fields.append("area = ?")
                params.append(area)
            
            if not update_fields:
                return True
                
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE username = ?"
            params.append(username)
            
            cur.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.DatabaseError as e:
        print(f"Error updating user: {e}")
        return False

def delete_user(username: str, db_path: str = config.AppConfig.DB_PATH) -> bool:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.DatabaseError as e:
        print(f"Error deleting user: {e}")
        return False


# ---------------------------------------------------------------------------
# Configuración genérica (tabla store_config)
# ---------------------------------------------------------------------------

def get_config(key: str, default: str = "", db_path: str = config.AppConfig.DB_PATH) -> str:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM store_config WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row is not None else default
    except sqlite3.DatabaseError:
        return default


def set_config(key: str, value: str, db_path: str = config.AppConfig.DB_PATH) -> bool:
    try:
        with _PersistentContext(db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO store_config (key, value) VALUES (?, ?)",
                        (key, str(value)))
            conn.commit()
            return True
    except sqlite3.DatabaseError as e:
        print(f"Error setting config {key}: {e}")
        return False
