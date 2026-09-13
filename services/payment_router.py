import urllib.parse
from decimal import Decimal
from typing import Optional, Union
from pydantic import BaseModel


class PaymentLinks(BaseModel):
    nequi_url: str
    daviplata_url: str
    bre_b_qr_data: str


def generate_nequi_deep_link(phone_number: Optional[str], amount: Union[Decimal, str, float, int]) -> Optional[str]:
    """
    Genera un enlace profundo (deep link) para pagos a través de Nequi.

    Aplica urllib.parse.quote() al teléfono y al monto antes de interpolarlos en el deep link.
    """
    if not phone_number:
        return None

    clean_phone = "".join(filter(str.isdigit, str(phone_number)))
    if not clean_phone:
        return None

    if isinstance(amount, Decimal):
        amount_dec = amount.quantize(Decimal("0.01"))
    else:
        try:
            amount_dec = Decimal(str(amount)).quantize(Decimal("0.01"))
        except Exception:
            amount_dec = Decimal("0.00")

    quoted_phone = urllib.parse.quote(clean_phone)
    quoted_amount = urllib.parse.quote(str(amount_dec))

    return f"nequi://pay?phone={quoted_phone}&amount={quoted_amount}"


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
        clean_phone = ''.join(filter(str.isdigit, str(phone_number)))
        
        try:
            amount_dec = Decimal(amount_str).quantize(Decimal('0.01'))
        except Exception:
            amount_dec = Decimal('0.00')

        quoted_phone = urllib.parse.quote(clean_phone)
        quoted_amount = urllib.parse.quote(str(amount_dec))
        quoted_concept = urllib.parse.quote(concept)

        nequi_url = f"{cls.NEQUI_BASE_URL}?phone={quoted_phone}&amount={quoted_amount}&concept={quoted_concept}"
        daviplata_url = f"{cls.DAVIPLATA_BASE_URL}?to={quoted_phone}&amount={quoted_amount}"
        bre_b_qr_data = f"breb:transfer:{quoted_phone}:{quoted_amount}"

        return PaymentLinks(
            nequi_url=nequi_url,
            daviplata_url=daviplata_url,
            bre_b_qr_data=bre_b_qr_data
        )
