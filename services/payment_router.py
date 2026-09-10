import urllib.parse
from pydantic import BaseModel
from decimal import Decimal

class PaymentLinks(BaseModel):
    nequi_url: str
    daviplata_url: str
    bre_b_qr_data: str

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
