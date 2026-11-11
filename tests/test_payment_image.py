import io
import os
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from app.payment_pdf import build_payment_pdf,build_payment_image

def sample(count=1):
    return dict(lot_id=1,farm='Granja de conferência',withdrawal='2026-11-03',heads=10,
        original_g=95000,price_cents=520,gross=49400,loss_g=5000,discount=2600,net_g=90000,net=46800,
        losses=[dict(date='2026-11-03',description='Perda no transporte',weight_g=5000,discount=2600)],
        previous=[],created_at='2026-11-03T12:00:00',cash=10000,checks_total=count*100,total=10000+count*100,
        previous_total=0,balance=36800-count*100,note='Conferência final. Todos os dados em uma única imagem.',
        checks=[dict(compensation_date='2027-01-10',number=str(i),bank='Banco',note=f'Cheque de conferência {i:03d}',value_cents=100) for i in range(count)])

def test_single_image_contains_all_sections_and_long_table():
    snapshot=sample(100)
    pdf=PdfReader(io.BytesIO(build_payment_pdf(snapshot,'2026-11-03T12:00:00',single_page=True)))
    assert len(pdf.pages)==1
    text=pdf.pages[0].extract_text()
    for i in range(100):assert f'Cheque de conferência {i:03d}' in text
    for section in ['IDENTIFICAÇÃO','APURAÇÃO','PERDAS','PAGAMENTOS ANTERIORES','PAGAMENTO ATUAL','CHEQUES','RESUMO FINANCEIRO','OBSERVAÇÕES']:
        assert section in text
    assert 'Conferência final.' in text
    image=Image.open(io.BytesIO(build_payment_image(snapshot,'2026-11-03T12:00:00')))
    assert image.format=='PNG' and image.n_frames==1
    assert image.height>image.width*3
    assert image.width>=1190

def test_height_adapts_to_content():
    small=Image.open(io.BytesIO(build_payment_image(sample(),'2026-11-03T12:00:00')))
    large=Image.open(io.BytesIO(build_payment_image(sample(10),'2026-11-03T12:00:00')))
    assert small.width==large.width and large.height>small.height
