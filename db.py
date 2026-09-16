import sqlite3
from typing import List, Dict, Tuple, Any
import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db(db_path: str = "billing.db"):
    try:
        with sqlite3.connect(db_path) as conn:
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
            except Exception as e:
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
            except Exception as e:
                print(f"Error migrando tabla clients: {e}")

            try:
                cur.execute("PRAGMA table_info(products)")
                prod_cols = [c[1] for c in cur.fetchall()]
                if 'tax_exempt' not in prod_cols:
                    cur.execute("ALTER TABLE products ADD COLUMN tax_exempt INTEGER DEFAULT 0")
            except Exception as e:
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
                    ('client_name', 'TEXT')
                ]:
                    if col_name not in inv_cols:
                        print(f"DEBUG: Añadiendo columna {col_name} a tabla invoices...")
                        cur.execute(f"ALTER TABLE invoices ADD COLUMN {col_name} {col_def}")
                        conn.commit()
            except Exception as e:
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
            except Exception as e:
                print(f"Error migrando tabla invoice_items: {e}")

            conn.commit()
    except Exception as e:
        print(f"CRITICAL ERROR initializing database: {e}")
        raise


def save_state(products: List[Dict[str, Any]], clients: List[Dict[str, Any]],
               invoices: List[Dict[str, Any]], invoice_counter: int,
               iva_rate: float = 0.16, exchange_rate: float = 350.0,
               include_pending_in_dashboard: bool = True,
               auto_update_rate: bool = False, rate_source: str = "oficial",
               db_path: str = "billing.db") -> None:
    import time
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with sqlite3.connect(db_path, timeout=10.0) as conn:
                cur = conn.cursor()
                
                # Iniciar transacción manual para mayor seguridad
                cur.execute("BEGIN TRANSACTION")

                # Limpiar tablas antes de re-insertar
                cur.execute("DELETE FROM invoice_items")
                cur.execute("DELETE FROM products")
                cur.execute("DELETE FROM clients")
                cur.execute("DELETE FROM invoices")
                cur.execute("DELETE FROM payments")
                cur.execute("DELETE FROM documents")

                for p in products:
                    try:
                        purchase_price = float(p.get("purchase_price", 0))
                    except (ValueError, TypeError):
                        purchase_price = 0.0
                    try:
                        price = float(p.get("price", 0))
                    except (ValueError, TypeError):
                        price = 0.0
                    try:
                        stock = int(p.get("stock", 0))
                    except (ValueError, TypeError):
                        stock = 0
                    try:
                        min_stock = int(p.get("min_stock", 5))
                    except (ValueError, TypeError):
                        min_stock = 5
                    
                    cur.execute(
                        "INSERT OR REPLACE INTO products (id, code, name, category, purchase_price, price, stock, min_stock, location, supplier, notes, tax_exempt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            p.get("id"), p.get("code"), p.get("name"), p.get("category"),
                            purchase_price, price, stock, min_stock, p.get("location"), p.get("supplier"), p.get("notes", ""), int(bool(p.get("tax_exempt", 0)))
                        )
                    )

                for c in clients:
                    cur.execute(
                        "INSERT OR REPLACE INTO clients (id, name, rif_ci, type, phone, email, address, city, state, postal_code, notes, credit_days, balance, credit_start_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            c.get("id"), c.get("name"), c.get("rif_ci"), c.get("type"), c.get("phone"),
                            c.get("email"), c.get("address", ""), c.get("city"), c.get("state"), c.get("postal_code"), c.get("notes", ""), int(c.get("credit_days", 0)), float(c.get("balance", 0.0)), c.get("credit_start_date")
                        )
                    )

                for inv in invoices:
                    try:
                        subtotal = float(inv.get("subtotal", 0))
                    except (ValueError, TypeError):
                        subtotal = 0.0
                    try:
                        tax = float(inv.get("tax", 0))
                    except (ValueError, TypeError):
                        tax = 0.0
                    try:
                        total = float(inv.get("total", 0))
                    except (ValueError, TypeError):
                        total = 0.0
                    
                    client_name = inv.get("client")
                    client_id = None
                    # Intentar buscar el ID del cliente por nombre
                    for c in clients:
                        if c.get("name") == client_name:
                            client_id = c.get("id")
                            break
                    
                    cur.execute(
                        "INSERT OR REPLACE INTO invoices (number, date, client_id, client_name, subtotal, tax, total, payment_method, status, due_date, is_credit, balance, cancel_method, cancel_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            inv.get("number"), inv.get("date"), client_id, client_name, subtotal, tax, total, inv.get("payment_method", ""), inv.get("status", ""), inv.get("due_date"), int(bool(inv.get("is_credit", 0))), float(inv.get("balance", 0.0)), inv.get("cancel_method"), inv.get("cancel_note")
                        )
                    )

                    for item in inv.get("items", []):
                        try:
                            quantity = int(item.get("quantity", 0))
                        except (ValueError, TypeError):
                            quantity = 0
                        try:
                            price = float(item.get("price", 0))
                        except (ValueError, TypeError):
                            price = 0.0
                        try:
                            total_item = float(item.get("total", 0))
                        except (ValueError, TypeError):
                            total_item = 0.0
                        
                        product_name = item.get("product")
                        product_id = None
                        for p in products:
                            if p.get("name") == product_name:
                                product_id = p.get("id")
                                break
                        
                        cur.execute(
                            "INSERT INTO invoice_items (invoice_number, product_id, product_name, quantity, price, total, tax_exempt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (inv.get("number"), product_id, product_name, quantity, price, total_item, int(bool(item.get("tax_exempt", False))))
                        )

                    for pay in inv.get("payments", []):
                        try:
                            pay_amount = float(pay.get("amount", 0))
                        except (ValueError, TypeError):
                            pay_amount = 0.0
                        cur.execute(
                            "INSERT INTO payments (invoice_number, date, amount, method, note) VALUES (?, ?, ?, ?, ?)",
                            (inv.get("number"), pay.get("date"), pay_amount, pay.get("method"), pay.get("note"))
                        )

                    for doc in inv.get("documents", []):
                        try:
                            doc_amount = float(doc.get("amount", 0))
                        except (ValueError, TypeError):
                            doc_amount = 0.0
                        cur.execute(
                            "INSERT INTO documents (type, invoice_number, date, amount, reason) VALUES (?, ?, ?, ?, ?)",
                            (doc.get("type"), inv.get("number"), doc.get("date"), doc_amount, doc.get("reason"))
                        )

                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("invoice_counter", str(invoice_counter)))
                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("iva_rate", str(iva_rate)))
                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("exchange_rate", str(exchange_rate)))
                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("include_pending_in_dashboard", str(int(include_pending_in_dashboard))))
                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("auto_update_rate", str(int(auto_update_rate))))
                cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("rate_source", str(rate_source)))

                conn.commit()
                return 
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            else:
                print(f"Operational error saving state: {e}")
                raise
        except Exception as e:
            print(f"General error saving state: {e}")
            raise


def load_state(db_path: str = "billing.db") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], int, float, float, bool, bool, str]:
    try:
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
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

            cur.execute("SELECT number, date, client_name, subtotal, tax, total, payment_method, status, due_date, is_credit, balance, cancel_method, cancel_note, client_id FROM invoices ORDER BY number")
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

                invoices.append({
                    "number": row[0], "date": row[1], "client": row[2], "subtotal": row[3],
                    "tax": row[4], "total": row[5], "payment_method": row[6], "status": row[7],
                    "due_date": row[8], "is_credit": bool(row[9]), "balance": float(row[10]) if row[10] is not None else 0.0,
                    "cancel_method": row[11], "cancel_note": row[12], "items": items, "payments": payments, "documents": documents, "client_id": row[13]
                })

            cur.execute("SELECT value FROM meta WHERE key = ?", ("invoice_counter",))
            r = cur.fetchone()
            invoice_counter = int(r[0]) if r else 1000

            cur.execute("SELECT value FROM meta WHERE key = ?", ("iva_rate",))
            r = cur.fetchone()
            iva_rate = float(r[0]) if r else 0.16

            cur.execute("SELECT value FROM meta WHERE key = ?", ("exchange_rate",))
            r = cur.fetchone()
            exchange_rate = float(r[0]) if r else 350.0

            cur.execute("SELECT value FROM meta WHERE key = ?", ("include_pending_in_dashboard",))
            r = cur.fetchone()
            include_pending_in_dashboard = bool(int(r[0])) if r else True

            cur.execute("SELECT value FROM meta WHERE key = ?", ("auto_update_rate",))
            r = cur.fetchone()
            auto_update_rate = bool(int(r[0])) if r else False

            cur.execute("SELECT value FROM meta WHERE key = ?", ("rate_source",))
            r = cur.fetchone()
            rate_source = r[0] if r else "oficial"

            return products, clients, invoices, invoice_counter, iva_rate, exchange_rate, include_pending_in_dashboard, auto_update_rate, rate_source
    except Exception as e:
        print(f"Error loading state from database: {e}")
        return [], [], [], 1000, 0.16, 350.0, True, False, "oficial"


def create_user(username: str, password: str, role: str = "empleado", 
                full_name: str = "", email: str = "", institution: str = "", area: str = "", 
                db_path: str = "billing.db") -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash, role, full_name, email, institution, area) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (username, hash_password(password), role, full_name, email, institution, area))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error creating user: {e}")
        return False

def authenticate_user(username: str, password: str, db_path: str = "billing.db") -> Tuple[bool, str]:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?",
                        (username, hash_password(password)))
            result = cur.fetchone()
            if result:
                return True, result[0]
            return False, ""
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return False, ""

def get_users(db_path: str = "billing.db") -> List[Dict[str, Any]]:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, username, role, full_name, email, institution, area FROM users")
            return [{"id": row[0], "username": row[1], "role": row[2], 
                     "full_name": row[3], "email": row[4], 
                     "institution": row[5], "area": row[6]} for row in cur.fetchall()]
    except Exception as e:
        print(f"Error getting users: {e}")
        return []

def get_user_by_username(username: str, db_path: str = "billing.db") -> Dict[str, Any]:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, username, role, full_name, email, institution, area FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            if row:
                return {"id": row[0], "username": row[1], "role": row[2], 
                         "full_name": row[3], "email": row[4], 
                         "institution": row[5], "area": row[6]}
            return {}
    except Exception as e:
        print(f"Error getting user by username: {e}")
        return {}

def update_user(username: str, password: str = None, role: str = None, 
                full_name: str = None, email: str = None, institution: str = None, 
                area: str = None, db_path: str = "billing.db") -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
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
    except Exception as e:
        print(f"Error updating user: {e}")
        return False

def delete_user(username: str, db_path: str = "billing.db") -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE username = ?", (username,))
            return cur.rowcount > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False
