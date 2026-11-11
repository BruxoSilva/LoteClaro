from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from .domain import money,kg,brdate
from .payments import state

def build_payment_pdf(s,issued,single_page=False):
    stream=BytesIO();styles=getSampleStyleSheet()
    body=ParagraphStyle('payment_body',fontName='Helvetica',fontSize=9,leading=13,textColor=colors.HexColor('#172238'))
    heading=ParagraphStyle('payment_heading',fontName='Helvetica-Bold',fontSize=12,leading=16,spaceBefore=16,spaceAfter=8,keepWithNext=True)
    def p(value): return Paragraph(escape(str(value)),body)
    width=A4[0]-64
    def table(headers,rows,widths=None):
        rows=rows or [['Nenhum registro']+['-']*(len(headers)-1)]
        t=Table([[p(v) for v in row] for row in [headers]+rows],colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf0f6')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dfe3e8'))]))
        return t
    story=[Paragraph('RELATÓRIO DE COMPRA E PAGAMENTO DO LOTE',ParagraphStyle('payment_title',fontName='Helvetica-Bold',fontSize=18,leading=23)),Spacer(1,10)]
    def section(title,headers,rows,widths=None):
        story.extend([Paragraph(title,heading),table(headers,rows,widths)])
    section('1. IDENTIFICAÇÃO DO LOTE',['Identificação','Informação'],[
        ['Código',f"Lote {s['lot_id']:04d}"],['Granja / fornecedor',s['farm']],['Data de retirada',brdate(s['withdrawal'])],['Quantidade de cabeças',s['heads']]])
    section('2. APURAÇÃO DA COMPRA',['Indicador','Valor'],[['Peso original antes das perdas',kg(s['original_g'])],['Valor de compra por kg',money(s['price_cents'])],['Valor bruto',money(s['gross'])]])
    section('3. PERDAS E DESCONTOS',['Data','Descrição','Peso','Desconto'],[[brdate(x['date']),x['description'],kg(x['weight_g']),money(x['discount'])] for x in s['losses']],[64,width-254,90,100])
    story.append(p('Descontos por linha ajustados cumulativamente aos centavos do desconto total.'))
    section('4. PAGAMENTOS ANTERIORES',['Data','Dinheiro','Cheques','Total'],[[brdate(x['created_at']),money(x['cash_cents']),money(x['checks_cents']),money(x['total_cents'])] for x in s['previous']])
    section('5. PAGAMENTO ATUAL',['Data do pagamento','Dinheiro','Cheques','Total'],[[brdate(s['created_at']),money(s['cash']),money(s['checks_total']),money(s['total'])]])
    section('6. CHEQUES',['Compensação','Número / banco','Observação','Valor'],[[brdate(c['compensation_date']),f"{c['number'] or '-'} / {c['bank'] or '-'}",c['note'] or '-',money(c['value_cents'])] for c in s['checks']],[80,140,width-320,100])
    section('7. RESUMO FINANCEIRO',['Indicador','Valor'],[
        ['Valor bruto',money(s['gross'])],['Peso total das perdas',kg(s['loss_g'])],['Total dos descontos',money(s['discount'])],['Peso líquido para pagamento',kg(s['net_g'])],['Valor líquido do lote',money(s['net'])],['Total pago anteriormente',money(s['previous_total'])],['Total desta operação',money(s['total'])],['Total acumulado pago',money(s['previous_total']+s['total'])],['Saldo ainda devido' if s['balance']>=0 else 'Crédito/haver',money(abs(s['balance']))],['Situação',state(s['balance'])]])
    story.extend([Paragraph('8. OBSERVAÇÕES',heading),p(s['note'] or 'Sem observações.')])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#657186'))
        canvas.drawString(32,24,'Emitido em '+brdate(issued));canvas.drawRightString(A4[0]-32,24,f'Página {doc.page}')
    if single_page:
        from reportlab.pdfgen.canvas import Canvas
        measure=Canvas(BytesIO())
        sizes=[]
        for item in story:
            _,height=item.wrapOn(measure,width,10000000)
            sizes.append((item.getSpaceBefore(),height,item.getSpaceAfter()))
        page_height=32+sum(sum(size) for size in sizes)+48
        canvas=Canvas(stream,pagesize=(A4[0],page_height))
        canvas.setTitle('Relatório de compra e pagamento do lote')
        y=page_height-32
        for item,(before,height,after) in zip(story,sizes):
            y-=before+height
            item.drawOn(canvas,32,y)
            y-=after
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#657186'))
        canvas.drawString(32,24,'Emitido em '+brdate(issued))
        canvas.showPage();canvas.save()
    else:
        SimpleDocTemplate(stream,pagesize=A4,leftMargin=32,rightMargin=32,topMargin=32,bottomMargin=48,title='Relatório de compra e pagamento do lote').build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()

def build_payment_image(snapshot,issued):
    import fitz
    with fitz.open(stream=build_payment_pdf(snapshot,issued,single_page=True),filetype='pdf') as document:
        return document[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).tobytes('png')
