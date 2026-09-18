"""Configuración centralizada de AS Facturation.

Concentra los valores que antes estaban dispersos por el código (tasa de IVA,
tasa de cambio, inicio del contador de facturas, datos por defecto de la tienda
y parámetros de persistencia). Cambiar un valor aquí lo cambia en toda la app.
"""
from __future__ import annotations


class AppConfig:
    """Constantes de negocio y valores por defecto de la aplicación."""

    # --- Identidad de la aplicación ---
    APP_NAME: str = "SISTEMA DE FACTURACIÓN AS"
    APP_VERSION: str = "3.5"

    # --- Parámetros fiscales y monetarios ---
    IVA_RATE: float = 0.16
    EXCHANGE_RATE: float = 350.0
    INVOICE_COUNTER_START: int = 1000
    RATE_SOURCE: str = "oficial"

    # --- Datos por defecto de la tienda ---
    COMPANY_NAME: str = APP_NAME
    COMPANY_RIF: str = "RIF: N/A"
    COMPANY_ADDRESS: str = "Domicilio fiscal: N/A"
    COMPANY_PHONE: str = "Teléfono: N/A"
    STORE_URL: str = "https://www.tu-tienda.com"
    QR_LINK: str = STORE_URL

    # --- Preferencias del panel ---
    INCLUDE_PENDING_IN_DASHBOARD: bool = True
    AUTO_UPDATE_RATE: bool = False

    # --- Persistencia ---
    DB_PATH: str = "billing.db"
    JSON_BACKUP_PATH: str = "billing_data.json"
    SAVE_BATCH_SIZE: int = 500

    # --- Límites de validación ---
    MIN_IVA_RATE: float = 0.0
    MAX_IVA_RATE: float = 1.0
    MIN_EXCHANGE_RATE: float = 0.01
    MIN_INVOICE_COUNTER: int = 1

    # --- Rendimiento ---
    TOAST_DURATION_MS: int = 6000
    CHART_DPI: int = 100
    LABELS_PER_ROW: int = 3
    LABELS_PER_COL: int = 3

    # --- Exportaciones ---
    EXPORT_DIR: str = "Facturas"
    LABELS_DIR: str = "Etiquetas"
    EXCEL_DIR: str = "Excel"
