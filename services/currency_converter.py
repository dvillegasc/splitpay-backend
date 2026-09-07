"""
Servicio de Conversión de Monedas para SplitPay.

Integra una API pública de tasas de cambio en tiempo real (ej. open.er-api.com / exchangerate.host)
con un sistema de caché en memoria con TTL (Time To Live) configurable para optimizar
las peticiones HTTP y no exceder los límites de la API externa.
"""

import json
import os
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from typing import Dict, Union

# TTL por defecto para la caché en memoria (en segundos): 3600 segundos = 1 hora
CACHE_TTL_SECONDS = int(os.environ.get("CURRENCY_CACHE_TTL_SECONDS", "3600"))
API_URL_TEMPLATE = os.environ.get(
    "CURRENCY_API_URL_TEMPLATE",
    "https://open.er-api.com/v6/latest/{base}",
)

# Estructura en memoria para almacenar las tasas cacheadas:
# {
#     "USD": {
#         "rates": {"COP": Decimal("3900.50"), "EUR": Decimal("0.92"), ...},
#         "timestamp": 1700000000.0
#     }
# }
_CACHE: Dict[str, dict] = {}
_CACHE_LOCK = Lock()


def _fetch_rates_from_api(base_currency: str) -> Dict[str, Decimal]:
    """
    Realiza una petición HTTP a la API externa de tasas de cambio para una moneda base.

    :param base_currency: Código ISO de la moneda base (ej. COP, USD, EUR).
    :return: Diccionario con los códigos de moneda destino y sus tasas en Decimal.
    :raises ValueError: Si la API retorna un error o una respuesta no válida.
    """
    url = API_URL_TEMPLATE.format(base=base_currency)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SplitPay-CurrencyConverter/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise ValueError(f"Respuesta inesperada de la API de divisas: HTTP {response.status}")
            data = json.loads(response.read().decode("utf-8"))

        raw_rates = data.get("rates", {})
        if not raw_rates:
            raise ValueError(f"No se encontraron tasas de cambio para la moneda base '{base_currency}'.")

        return {curr: Decimal(str(rate)) for curr, rate in raw_rates.items()}
    except Exception as e:
        raise ValueError(f"Error al consultar la API de tasas de cambio para '{base_currency}': {e}") from e


def _get_rates_for_base(base_currency: str) -> Dict[str, Decimal]:
    """
    Obtiene las tasas de cambio para la moneda base indicada, utilizando la caché
    en memoria si los datos son recientes (dentro del TTL) o consultando la API en caso contrario.

    :param base_currency: Código de moneda base (normalizado en mayúsculas).
    :return: Diccionario de tasas de cambio.
    """
    now = time.time()

    with _CACHE_LOCK:
        cached_data = _CACHE.get(base_currency)
        if cached_data:
            age = now - cached_data["timestamp"]
            if age < CACHE_TTL_SECONDS:
                return cached_data["rates"]

    # Si no está en caché o expiró el TTL, consultar API externa fuera del lock para no bloquear hilos
    try:
        fresh_rates = _fetch_rates_from_api(base_currency)
        with _CACHE_LOCK:
            _CACHE[base_currency] = {
                "rates": fresh_rates,
                "timestamp": now,
            }
        return fresh_rates
    except ValueError:
        # Si la llamada a la API falla pero existe un dato previo en caché (incluso expirado), usarlo como fallback
        with _CACHE_LOCK:
            if base_currency in _CACHE:
                return _CACHE[base_currency]["rates"]
        raise


def convert_amount(
    amount: Union[Decimal, float, int, str],
    from_currency: str,
    to_currency: str,
) -> Decimal:
    """
    Convierte un monto determinado desde una moneda de origen hacia una moneda de destino
    utilizando tasas de cambio en tiempo real con caché en memoria.

    :param amount: Monto de dinero a convertir.
    :param from_currency: Código ISO de 3 letras de la moneda de origen (ej. 'USD', 'COP').
    :param to_currency: Código ISO de 3 letras de la moneda de destino (ej. 'COP', 'EUR').
    :return: Monto convertido representado como Decimal con precisión de 2 decimales.
    :raises ValueError: Si la moneda es inválida o la conversión no pudo realizarse.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    from_curr = from_currency.strip().upper()
    to_curr = to_currency.strip().upper()

    if len(from_curr) != 3 or len(to_curr) != 3:
        raise ValueError("Los códigos de moneda deben tener exactamente 3 caracteres (ej. USD, COP).")

    # Si la moneda de origen y destino son iguales, retornar el monto original cuantizado
    if from_curr == to_curr:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    rates = _get_rates_for_base(from_curr)

    if to_curr not in rates:
        raise ValueError(f"No se encontró la tasa de cambio de '{from_curr}' a '{to_curr}'.")

    rate = rates[to_curr]
    converted = amount * rate

    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def clear_cache() -> None:
    """Limpia el contenido de la caché de tasas de cambio en memoria."""
    with _CACHE_LOCK:
        _CACHE.clear()
