from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from .domain import money, kg, brdate, metrics, cost

def build_pdf(lot, sales, expenses, calc, generated):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyLocal', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#172238')))
    styles.add(ParagraphStyle('RightLocal', parent=styles['BodyLocal'], alignment=TA_RIGHT))
    styles.add(ParagraphStyle('SectionLocal', fontName='Helvetica-Bold', fontSize=12, leading=16, spaceBefore=16, spaceAfter=9, keepWithNext=True))
    def p(text, right=False):
        return Paragraph(escape(str(text)), styles['RightLocal' if right else 'BodyLocal'])
    def table(headers, rows, widths, highlights=None):
        rows = rows or [['Nenhum lançamento'] + ['-']*(len(headers)-1)]
        data = [[p(h) for h in headers]] + [[p(v, i == len(row)-1) for i,v in enumerate(row)] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        commands = [('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf0f6')), ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#cbd2dc')),
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
            ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dfe3e8'))]
        if highlights:
            for idx, tone in highlights:
                if tone:
                    color = '#a61c2b' if tone == 'negative' else '#087a50'
                    data[idx+1][-1] = Paragraph(escape(str(rows[idx][-1])), ParagraphStyle('value', parent=styles['RightLocal'], textColor=colors.HexColor(color)))
            t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle(commands))
        return t
    width = A4[0]-64
    story = [Paragraph('DEMONSTRATIVO DE FECHAMENTO', ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#0b1530'))),
        p('Relatório de Conferência de Mercadorias e Resultados'), Spacer(1,10),
        p(f"Lote {lot['id']:04d} | Status: {lot['status'].upper()} | Moeda: BRL (R$)"), Spacer(1,12)]
    note = Table([[p('Nota de Conferência: o custo principal utiliza o peso pago líquido (peso pago original menos PERCAS). A quebra segue a conciliação entre entrada e vendas; o excedente não é somado novamente ao lucro.')]], colWidths=[width])
    note.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eef8fc')),('LINEBEFORE',(0,0),(0,0),2,colors.HexColor('#1488b6')),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story += [note, Paragraph('1. DETALHAMENTO DO LOTE', styles['SectionLocal']), table(['Descrição do item','Informação'], [
        ['Granja',lot['farm']], ['Data de retirada',brdate(lot['withdrawal'])],['Quantidade de cabeças',lot['heads']],
        ['Criação',brdate(lot['created_at'])],['Finalização',brdate(lot['closed_at'])]], [width*.50,width*.50]),
        Paragraph('2. DETALHAMENTO DAS VENDAS', styles['SectionLocal']),
        table(['Data','Cliente / Observação','Peso vendido','Preço / kg','Valor total'],
            [[brdate(s['date']),s['client_name'] + (f" / {s['note']}" if s['note'] else ''),kg(s['weight_g']),money(s['price_cents']),money(cost(s['weight_g'],s['price_cents']))] for s in sales], [62,width-62-90-79-93,90,79,93]),
        table(['TOTAL DAS VENDAS','Peso total','Receita bruta'],[['',kg(calc['sold_g']),money(calc['revenue'])]], [width*.45,width*.25,width*.30]),
        Paragraph('3. DESPESAS DO LOTE', styles['SectionLocal']),
        table(['Data','Descrição','Valor'], [[brdate(e['date']),e['description'],money(e['value_cents'])] for e in expenses], [68,width-171,103]),
        table(['TOTAL DE DESPESAS','Valor'],[['',money(calc['expenses'])]],[width-140,140]),
        Paragraph('4. PERCAS - DESCONTO NO PESO PAGO', styles['SectionLocal']),
        table(['Data','O que foi perdido','Peso descontado'],
            [[brdate(p['date']),p['note'],kg(p['weight_g'])] for p in (lot.get('percas',[]) if isinstance(lot,dict) else [])], [68,width-178,110]),
        table(['TOTAL DE PERCAS','Peso'],[['',kg(calc['percas_g'])]],[width-140,140],[(0,'negative')] if calc['percas_g'] else []),
        Paragraph('5. RESUMO FINANCEIRO E CONCILIAÇÃO', styles['SectionLocal'])]
    values = metrics(lot, calc)
    story.append(table(['Indicador','Resultado'], [[a,b] for a,b,c in values], [width*.64,width*.36],[(i,v[2]) for i,v in enumerate(values)]))
    state = 'Estoque conciliado - diferença de peso: 0 kg' if calc['difference_g']==0 else ('Quebra reconhecida no fechamento' if calc['loss_g'] else ('Peso excedente vendido' if calc['excess_g'] else 'Estoque restante - resultado parcial'))
    story += [Spacer(1,12),p(state)]
    cards=[]
    for label,value,tone in [('CUSTO: PESO PAGO LÍQUIDO',calc['paid_cost'],'neutral'),('RECEITA BRUTA',calc['revenue'],'positive'),('LUCRO LÍQUIDO',calc['net'],'positive' if calc['net']>=0 else 'negative')]:
        color = '#a61c2b' if tone=='negative' else '#087a50' if tone=='positive' else '#172238'
        cards.append([p(label), Paragraph(escape(money(value)), ParagraphStyle('card',fontName='Helvetica-Bold',fontSize=14,leading=20,textColor=colors.HexColor(color)))])
    # Each inner card stacks its label over its amount.
    ct=Table([[Table([[x[0]],[x[1]]], colWidths=[width/3-16]) for x in cards]],colWidths=[width/3]*3)
    ct.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f0f5f7')),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#d3dce5')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [Spacer(1,14),KeepTogether([ct,Spacer(1,8),p('Lucro líquido = receita - custo do peso pago líquido - despesas - quebra.')])]
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#bdc8d4'))
        canvas.line(32,35,A4[0]-32,35)
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#657186'))
        canvas.drawString(32,23,f'Gerado em {brdate(generated)} | Lote {lot["id"]:04d}')
        canvas.drawRightString(A4[0]-32,23,f'Página {doc.page}')
        canvas.restoreState()
    SimpleDocTemplate(buffer,pagesize=A4,rightMargin=32,leftMargin=32,topMargin=32,bottomMargin=48,title=f'Lote {lot["id"]:04d} - Demonstrativo',author='Controle de Lotes').build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
