<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="img/logo.png" alt="AS Facturation Logo" width="140" style="border-radius: 20px;">
</p>

<h1 align="center">🧾 AS Facturation</h1>

<p align="center">
  <strong>Sistema de facturación de escritorio para pequeñas y medianas empresas</strong><br>
  Ventas, inventario, clientes, facturación y reportes en una sola herramienta, <em>sin conexión a internet</em>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Versi%C3%B3n-3.5-4F46E5?style=for-the-badge" alt="Versión 3.5">
  <img src="https://img.shields.io/badge/Estado-En%20desarrollo-FF9800?style=for-the-badge" alt="Estado: En desarrollo">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/UI-CustomTkinter-1F8A4C?style=for-the-badge" alt="CustomTkinter">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Excel-217346?style=for-the-badge&logo=microsoft-excel&logoColor=white" alt="Exportación a Excel">
  <img src="https://img.shields.io/badge/PDF-EC1C24?style=for-the-badge&logo=adobe-acrobat-reader&logoColor=white" alt="Exportación a PDF">
  <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux">
  <img src="https://img.shields.io/badge/Licencia-MIT-22863A?style=for-the-badge" alt="Licencia MIT">
</p>

---

## 📖 Descripción

**AS Facturation** es una aplicación de escritorio diseñada para centralizar la facturación, el control de stock, la base de clientes y la generación de reportes en una herramienta amigable y **100 % funcional sin conexión a internet**.

Los datos se almacenan localmente en SQLite con respaldo automático en JSON, lo que garantiza la persistencia y la recuperación de información incluso ante bases de datos vacías o migraciones de esquema.

### 🧠 ¿Por qué elegir AS Facturation?

- ✅ **Sin suscripciones** – Una sola instalación, datos locales y bajo tu control.
- ✅ **Interfaz moderna** – Construida con `CustomTkinter`, con tema claro/oscuro.
- ✅ **Persistencia segura** – SQLite con respaldo automático en JSON y recuperación ante bases dañadas.
- ✅ **Roles integrados** – `admin` (control total) y `empleado` (solo ventas y consultas).
- ✅ **Exportación real** – Reportes en Excel, facturas en PDF y notas de entrega imprimibles.
- ✅ **Reportes visuales** – Gráficos de ventas, productos más vendidos y evolución mensual.

---

## ✨ Módulos y funcionalidades

| Módulo | Funcionalidades |
|--------|----------------|
| 🏪 **Punto de venta** | Búsqueda rápida de productos, carrito intuitivo, cálculo automático de impuestos y totales. |
| 📦 **Inventario** | Alta, edición, eliminación, notas por producto, control de stock mínimo y alertas. |
| 👥 **Clientes** | Registro ampliado (teléfono, email, dirección), notas y control de crédito disponible. |
| 📄 **Facturas** | Creación, edición, anulación con nota de cancelación, seguimiento de estado (pagada/crédito) y **exportación a PDF**. |
| 📦 **Notas de entrega** | Generación de comprobantes informales de entrega (sin validez fiscal) en PDF. |
| 🏷️ **Etiquetas QR** | Exportación de etiquetas de productos con código QR en PDF. |
| 💰 **Pagos y créditos** | Registro de abonos, control de saldo pendiente y recordatorios. |
| 📊 **Reportes** | Ventas por período, productos más vendidos, clientes frecuentes y **exportación a Excel**. |
| 👥 **Usuarios** | Gestión de usuarios con contraseñas cifradas y roles (`admin` / `empleado`). |
| 🔐 **Seguridad** | Login con roles, contraseñas con hash y permisos restringidos por rol. |

---

## 🗺️ Fase actual del desarrollo

> Proyecto **estable** (v3.5). Núcleo funcional completo; en **pruebas/QA final** antes del primer lanzamiento:

- ✅ Punto de venta, inventario, clientes y facturación (creación, edición y anulación).
- ✅ Exportación a **Excel**, **PDF** (facturas profesionales), **Notas de Entrega** y **Etiquetas QR**.
- ✅ Sistema de usuarios, roles y contraseñas cifradas.
- ✅ Reportes con gráficos (ventas, productos más vendidos, clientes frecuentes, flujo de caja, etc.).
- ✅ Respaldo automático en JSON, migraciones de esquema y recuperación ante bases vacías.
- 🚧 Correcciones de cálculos, UX y estabilidad en pruebas finales (QA).

---

## 🖥️ Capturas de pantalla

<p align="center">
  <img src="img/screenshot_login.png" width="45%">
  &nbsp;&nbsp;&nbsp;
  <img src="img/screenshot_factura.png" width="45%">
</p>
<p align="center"><i>Pantalla de login y ventana principal de facturación.</i></p>

---

## 🏗️ Estructura del proyecto

| Archivo / carpeta | Descripción |
|-------------------|-------------|
| `Main.py` | Punto de entrada; arranca la app, splash y login. |
| `db.py` | Base de datos: esquema SQLite, respaldos, usuarios y autenticación. |
| `requirements.txt` | Dependencias del proyecto. |
| `billing.db` | Base de datos local (SQLite). |
| `billing_data.json` | Respaldo de datos generado automáticamente. |
| `Facturas/` | Facturas exportadas en **PDF**. |
| `NotasDeEntrega/` | Notas de entrega exportadas en **PDF**. |
| `Excel/` | Reportes exportados en **Excel**. |
| `img/` | Recursos, logos e imágenes de la interfaz. |
| `test_create_user.py`, `test_login_ui.py`, `scratch_verify.py` | Pruebas de creación de usuario, UI de login y verificación. |

---

## ⚙️ Requisitos

- **Python 3.10+** (recomendado)
- **Windows** (entorno verificado) o **Linux** (Ubuntu/Debian y derivados)

> En Ubuntu/Debian, el paquete `tkinter` no se instala con Python por defecto.
> Instálalo antes de continuar:

```bash
sudo apt install python3-tk
```

Dependencias principales:
- `customtkinter` — interfaz gráfica moderna.
- `matplotlib` — gráficos y reportes visuales.
- `Pillow` — manejo de imágenes.
- `openpyxl` — exportación de reportes a Excel.
- `reportlab` — generación de facturas PDF y notas de entrega.

---

## 💻 Instalación

1. Abre una terminal en la carpeta del proyecto.
2. Crea un entorno virtual (recomendado):

```bash
python -m venv .venv
```

3. Activa el entorno virtual:

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**

```bat
.venv\Scripts\activate.bat
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

4. Instala las dependencias:

```bash
pip install -r requirements.txt
```

---

## ▶️ Ejecución

```bash
python Main.py
```

Se mostrará una pantalla de *splash* y de *login*; después se cargará el sistema de facturación completo.

---

## 🔐 Credenciales iniciales

La base de datos inicial crea un usuario administrador por defecto:

- **Usuario:** `admin`
- **Contraseña:** `admin`

> ⚠️ Se recomienda cambiar estas credenciales en el primer inicio.

---

## 📝 Notas importantes

- Los datos se almacenan en `billing.db` y se respaldan de forma automática en `billing_data.json`.
- Si la aplicación detecta una base de datos vacía, intenta restaurarla desde el respaldo JSON.
- El proyecto incluye migraciones de esquema para mantener compatibilidad entre versiones.
- El rol `empleado` tiene acceso restringido a acciones de edición y eliminación.
- **Compatibilidad multiplataforma:** la app detecta el sistema operativo y usa las fuentes
  y herramientas del sistema adecuadas (`Segoe UI`/`Cascadia Code` en Windows,
  `Noto Sans`/`DejaVu Sans Mono` en Linux, `Helvetica Neue` en macOS). Abrir carpetas y PDFs
  usa `xdg-open` en Linux.

---

## 🧰 Mejores prácticas

- Realiza respaldos periódicos de `billing.db` y `billing_data.json`.
- Usa `Excel/`, `Facturas/` y `NotasDeEntrega/` para conservar las exportaciones organizadas.
- Coloca logos o iconos personalizados dentro de `img/`.

---

## 🚀 Extensiones posibles

- Impresión directa de tickets / facturas.
- Cotización de moneda en tiempo real (tipo de cambio).
- Control de usuarios y permisos más granular.
- Vista previa gráfica de facturas antes de exportar.

---

## 📚 Referencias rápidas

- Archivo principal: `Main.py`
- Lógica de datos: `db.py`
- Respaldo JSON: `billing_data.json`
- Dependencias: `requirements.txt`

---

## 📄 Licencia

Distribuido bajo la **Licencia MIT**. Consulta el archivo de licencia del repositorio para más detalles.