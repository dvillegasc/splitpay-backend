"""
Servicio de Enrutamiento de Pagos y Generación de Deep Links para SplitPay.

Genera enlaces profundos (deep links) hacia billeteras digitales externas
(Nequi, Daviplata, etc.) garantizando la regla legal de Cero Custodia.
"""

from decimal import Decimal
from typing import Optional, Union
import urllib.parse
from pydantic import BaseModel


class PaymentLinks(BaseModel):
    nequi_url: str
    daviplata_url: str
    bre_b_qr_data: str


def generate_nequi_deep_link(
    telefono: Optional[str],
    monto: Union[Decimal, float, str],
) -> Optional[str]:
    """
    Genera un deep link de Nequi para realizar transferencias hacia un número de teléfono.

    Aplica urllib.parse.quote() al teléfono y al monto antes de interpolarlos en la URL
    para evitar esquemas o parámetros malformados.

    :param telefono: Número de teléfono del destinatario/acreedor.
    :param monto: Monto a transferir.
    :return: URL del deep link de Nequi o None si el teléfono no está definido.
    """
    if not telefono:
        return None

    telefono_str = str(telefono).strip()
    monto_str = str(monto).strip()

    telefono_encoded = urllib.parse.quote(telefono_str)
    monto_encoded = urllib.parse.quote(monto_str)

    return f"nequi://pay?phone={telefono_encoded}&amount={monto_encoded}"


class PaymentRouter:
    """
    Factoría de URLs para Deep Linking. No gestiona transacciones, 
    solo formatea intents de pago hacia ecosistemas de terceros.
    """

    NEQUI_BASE_URL = "nequi://pay"
    DAVIPLATA_BASE_URL = "daviplata://transfer"

    @classmethod
    def generate_links(cls, phone_number: str, amount_str: str, concept: str = "SplitPay") -> PaymentLinks:
        # Sanitización estricta del input
        clean_phone = ''.join(filter(str.isdigit, phone_number))

        try:
            amount_dec = Decimal(amount_str).quantize(Decimal('0.01'))
        except Exception:
            amount_dec = Decimal('0.00')

        # Codificación de parámetros de URL para evitar inyecciones
        nequi_params = urllib.parse.urlencode({
            'phone': clean_phone,
            'amount': str(amount_dec),
            'concept': concept
        })

        daviplata_params = urllib.parse.urlencode({
            'to': clean_phone,
            'amount': str(amount_dec)
        })

        return PaymentLinks(
            nequi_url=f"{cls.NEQUI_BASE_URL}?{nequi_params}",
            daviplata_url=f"{cls.DAVIPLATA_BASE_URL}?{daviplata_params}",
            bre_b_qr_data=f"breb:transfer:{clean_phone}:{amount_dec}"
        )
