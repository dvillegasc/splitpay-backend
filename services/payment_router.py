"""
Servicio de Enrutamiento de Pagos para SplitPay.

Genera deep links para billeteras digitales (como Nequi) a partir de los datos
del usuario acreedor y el monto de la transferencia.
"""

from decimal import Decimal
from typing import Optional, Union


def generate_nequi_deep_link(
    telefono: Optional[str],
    monto: Union[Decimal, float, int, str],
) -> Optional[str]:
    """
    Genera un deep link para iniciar un pago en Nequi con el formato:
    `nequi://pay?phone={telefono}&amount={monto}`.

    :param telefono: Número de teléfono registrado del acreedor.
    :param monto: Monto de la transferencia a realizar.
    :return: Cadena con el deep link de Nequi o None si el acreedor no tiene teléfono registrado.
    """
    if not telefono or not str(telefono).strip():
        return None

    telefono_limpio = str(telefono).strip()
    return f"nequi://pay?phone={telefono_limpio}&amount={monto}"
