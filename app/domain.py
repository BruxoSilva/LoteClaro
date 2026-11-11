"""All calculations use integers (grams/cents) and Decimal rounding."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
import re

def amount(value, scale=100, label='Valor', positive=False):
    raw = str(value).strip()
    if not re.fullmatch(r'\d+(?:[.,]\d+)?', raw):
        raise ValueError(f'{label}: informe um número positivo sem separador de milhares.')
    try:
        d = Decimal(raw.replace(',', '.')) * scale
        if d != d.to_integral_value() or d > 10**12 or (positive and d <= 0):
            raise ValueError()
        return int(d)
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label}: valor fora do limite ou com mais de {3 if scale == 1000 else 2} casas decimais.')

def required(value, label, limit=160):
    value = str(value or '').strip()
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label}: preencha de 1 a {limit} caracteres, sem quebras de linha.')
    return value

def date_value(value):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except (ValueError, TypeError):
            pass
    raise ValueError('Data inválida. Selecione uma data válida no calendário.')

def cost(grams, cents):
    return int((Decimal(grams) * cents / 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def calculate(lot, sales, expenses, closing=False):
    sold = sum(s['weight_g'] for s in sales)
    revenue = sum(cost(s['weight_g'], s['price_cents']) for s in sales)
    difference = lot['entry_g'] - sold
    loss = max(difference, 0) if closing or lot['status'] == 'finalizado' else 0
    excess = max(-difference, 0)
    percas = lot.get('percas', []) if isinstance(lot, dict) else []
    percas_g = sum(p['weight_g'] for p in percas)
    paid_net_g = lot['paid_g'] - percas_g
    if paid_net_g < 0:
        raise ValueError('O total de PERCAS não pode ultrapassar o peso pago original.')
    paid_cost = cost(paid_net_g, lot['cost_cents'])
    expense = sum(e['value_cents'] for e in expenses)
    loss_value = cost(loss, lot['cost_cents'])
    net = revenue - paid_cost - expense - loss_value
    return dict(percas_g=percas_g, paid_net_g=paid_net_g,
                percas_credit=cost(lot['paid_g'], lot['cost_cents'])-paid_cost,
                sold_g=sold, remaining_g=max(difference, 0) if not loss else 0,
                difference_g=difference, loss_g=loss, excess_g=excess,
                loss_cents=loss_value, excess_cents=cost(excess, lot['cost_cents']),
                entry_cost=cost(lot['entry_g'], lot['cost_cents']), paid_cost=paid_cost,
                revenue=revenue, expenses=expense, gross=revenue-paid_cost, net=net,
                margin=(Decimal(net)*100/Decimal(revenue)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if revenue else Decimal('0'))

def number(value, places=2):
    return f'{Decimal(value):,.{places}f}'.replace(',', '_').replace('.', ',').replace('_', '.')

def money(cents):
    return 'R$ ' + number(Decimal(cents)/100)

def kg(grams):
    return number(Decimal(grams)/1000, 3) + ' kg'

def brdate(value):
    if not value:
        return '-'
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime('%d/%m/%Y %H:%M:%S') if 'T' in value else dt.strftime('%d/%m/%Y')
    except ValueError:
        return value

def metrics(lot, c):
    return [
        ('Entrada', kg(lot['entry_g']), ''), ('Peso pago original', kg(lot['paid_g']), ''),
        ('PERCAS descontadas', kg(c['percas_g']), 'negative' if c['percas_g'] else ''),
        ('Peso pago líquido', kg(c['paid_net_g']), ''),
        ('Abatimento no custo por PERCAS', money(c['percas_credit']), ''),
        ('Peso vendido', kg(c['sold_g']), ''), ('Estoque restante', kg(c['remaining_g']), ''),
        ('Peso da quebra', kg(c['loss_g']), 'negative' if c['loss_g'] else ''),
        ('Valor da quebra', money(c['loss_cents']), 'negative' if c['loss_g'] else ''),
        ('Peso excedente', kg(c['excess_g']), 'positive' if c['excess_g'] else ''),
        ('Valor do excedente (indicador)', money(c['excess_cents']), 'positive' if c['excess_g'] else ''),
        ('Custo por kg', money(lot['cost_cents']), ''), ('Custo da entrada', money(c['entry_cost']), ''),
        ('Custo total (peso pago líquido)', money(c['paid_cost']), ''), ('Receita bruta', money(c['revenue']), ''),
        ('Total de despesas', money(c['expenses']), ''), ('Lucro bruto', money(c['gross']), 'positive' if c['gross'] >= 0 else 'negative'),
        ('Lucro líquido', money(c['net']), 'positive' if c['net'] >= 0 else 'negative'),
        ('Margem líquida', number(c['margin']) + '%', 'positive' if c['net'] >= 0 else 'negative')]
