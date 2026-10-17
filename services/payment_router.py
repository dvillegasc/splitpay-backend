"""
Servicio de Enrutamiento de Pagos para SplitPay.

Genera enlaces de pago y deep links hacia billeteras digitales externas (Nequi, Daviplata, etc.)
operando estrictamente bajo la regla de Cero Custodia.
"""

import urllib.parse
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel


class PaymentLinks(BaseModel):
    nequi_url: str
    daviplata_url: str
    bre_b_qr_data: str


def generate_nequi_deep_link(
    phone: Optional[str],
    amount: Union[Decimal, float, str, int],
) -> Optional[str]:
    """
    Genera un deep link para pagos vía Nequi.

    Aplica urllib.parse.quote() al teléfono y al monto antes de interpolarlos
    en el enlace profundo (deep link), evitando URLs malformadas.

    :param phone: Número de teléfono del destinatario del pago.
    :param amount: Monto a transferir.
    :return: Enlace profundo (deep link) nequi://pay?... o None si el teléfono no es válido.
    """
    if not phone:
        return None

    clean_phone = "".join(filter(str.isdigit, str(phone)))
    if not clean_phone:
        return None

    if isinstance(amount, Decimal):
        amount_str = str(amount.quantize(Decimal("0.01")))
    else:
        try:
            amount_str = str(Decimal(str(amount)).quantize(Decimal("0.01")))
        except Exception:
            amount_str = str(amount)

    quoted_phone = urllib.parse.quote(clean_phone, safe="")
    quoted_amount = urllib.parse.quote(amount_str, safe="")

    return f"nequi://pay?phone={quoted_phone}&amount={quoted_amount}"


class PaymentRouter:
    """
    Factoría de URLs para Deep Linking. No gestiona transacciones,
    solo formatea intents de pago hacia ecosistemas de terceros.
    """

    NEQUI_BASE_URL = "nequi://pay"
    DAVIPLATA_BASE_URL = "daviplata://transfer"

    @classmethod
    def generate_links(
        cls, phone_number: str, amount_str: str, concept: str = "SplitPay"
    ) -> PaymentLinks:
        # Sanitización estricta del input
        clean_phone = "".join(filter(str.isdigit, phone_number))

        try:
            amount_dec = Decimal(amount_str).quantize(Decimal("0.01"))
        except Exception:
            amount_dec = Decimal("0.00")

        amount_formatted = str(amount_dec)

        # Codificación de parámetros de URL para evitar inyecciones o enlaces malformados
        quoted_phone = urllib.parse.quote(clean_phone, safe="")
        quoted_amount = urllib.parse.quote(amount_formatted, safe="")
        quoted_concept = urllib.parse.quote(concept, safe="")

        nequi_url = f"{cls.NEQUI_BASE_URL}?phone={quoted_phone}&amount={quoted_amount}&concept={quoted_concept}"
        daviplata_url = f"{cls.DAVIPLATA_BASE_URL}?to={quoted_phone}&amount={quoted_amount}"

        return PaymentLinks(
            nequi_url=nequi_url,
            daviplata_url=daviplata_url,
            bre_b_qr_data=f"breb:transfer:{quoted_phone}:{quoted_amount}",
        )
