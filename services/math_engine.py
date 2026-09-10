"""
Motor de Cálculo Proporcional y Matemático para SplitPay.

Provee la función `calculate_proportional_split` para calcular la división
proporcional de gastos compartidos entre los miembros de un hogar según
sus ingresos mensuales declarados.
"""

import decimal
from typing import List, Dict, Any
from decimal import Decimal, InvalidOperation

# Configuración global del contexto matemático para SplitPay
decimal.getcontext().rounding = decimal.ROUND_HALF_UP
decimal.getcontext().prec = 12

class MathEngine:
    @staticmethod
    def calculate_equal_split(total_amount: str, num_users: int) -> List[Decimal]:
        """
        Divide equitativamente un gasto, manejando el residuo (centavo perdido)
        asignándolo al primer usuario para evitar fugas de balance.
        """
        if num_users <= 0:
            raise ValueError("El número de usuarios debe ser mayor a 0")
        
        try:
            total_dec = Decimal(total_amount)
        except InvalidOperation:
            raise ValueError(f"Monto inválido proveído: {total_amount}")

        if total_dec < Decimal('0'):
            raise ValueError("El monto no puede ser negativo")

        base_share = (total_dec / Decimal(num_users)).quantize(Decimal('0.01'))
        splits = [base_share for _ in range(num_users)]
        
        # Verificación de integridad: Suma de divisiones vs Total original
        total_calculated = sum(splits)
        difference = total_dec - total_calculated
        
        if difference != Decimal('0.00'):
            # Ajuste de centavo en el primer usuario
            splits[0] += difference
            
        return splits

    @staticmethod
    def simplify_debts(debts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Algoritmo base de flujo para minimizar transacciones.
        (Plantilla a expandir por el agente para consolidar nodos).
        """
        balances: Dict[str, Decimal] = {}
        for debt in debts:
            amount = Decimal(str(debt['amount']))
            balances[debt['debtor_id']] = balances.get(debt['debtor_id'], Decimal('0')) - amount
            balances[debt['creditor_id']] = balances.get(debt['creditor_id'], Decimal('0')) + amount

        # Separar en deudores y acreedores
        debtors = {k: v for k, v in balances.items() if v < Decimal('0')}
        creditors = {k: v for k, v in balances.items() if v > Decimal('0')}
        
        return [] # El agente debe implementar la reducción algorítmica aquí
