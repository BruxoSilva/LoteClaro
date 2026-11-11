(() => {
  const dialog=document.getElementById('payment-dialog');if(!dialog)return;
  const form=document.getElementById('payment-form'),checks=document.getElementById('payment-checks');let next=0;
  const money=c=>{const neg=c<0n;if(neg)c=-c;return (neg?'-':'')+'R$ '+(c/100n).toLocaleString('pt-BR')+','+(c%100n).toString().padStart(2,'0');};
  const parse=v=>{const m=/^(\d{1,11})(?:[.,](\d{1,2}))?$/.exec(v.trim());return m?BigInt(m[1]+(m[2]||'').padEnd(2,'0')):null;};
  function update(){
    let total=0n,valid=true;
    for(const input of form.querySelectorAll('[name=cash],[name=check_value]')){
      const value=parse(input.value);const ok=value!==null&&value<=1000000000000n&&(input.name==='cash'||value>0n);
      input.setCustomValidity(ok?'':'Informe um valor válido com até duas casas decimais; cheques devem ser maiores que zero.');
      if(!ok)valid=false;else total+=value;
    }
    const balance=BigInt(form.dataset.balance)-total;
    document.getElementById('payment-total').textContent=valid?money(total):'Confira os valores';
    document.getElementById('payment-balance').textContent=valid?money(balance<0n?-balance:balance):'—';
    document.getElementById('payment-balance-label').textContent=balance<0n?'Crédito/haver':balance===0n?'Pagamento quitado':'Ainda devido ao fornecedor';
    const credit=document.getElementById('payment-credit');credit.hidden=!valid||balance>=0n;
    credit.querySelector('input').required=valid&&balance<0n;
  }
  document.getElementById('payment-open').addEventListener('click',()=>{update();dialog.showModal();});
  document.getElementById('payment-cancel').addEventListener('click',()=>dialog.close());
  document.getElementById('payment-add-check').addEventListener('click',()=>{
    if(checks.children.length>=100)return;
    const block=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent='Cheque';block.append(legend);const index=next++;
    for(const [name,label,type,limit] of [['check_value','Valor (R$) *','text',20],['check_date','Data de compensação *','date',10],['check_number','Número (opcional)','text',80],['check_bank','Banco (opcional)','text',120],['check_note','Observação (opcional)','text',300]]){
      const wrap=document.createElement('div'),l=document.createElement('label'),input=document.createElement('input');wrap.className='field';input.name=name;input.id=name+'-'+index;input.type=type;input.maxLength=limit;l.htmlFor=input.id;l.textContent=label;
      if(name==='check_value'){input.inputMode='decimal';input.required=true;}if(type==='date'){input.required=true;input.min='0001-01-01';input.max='9999-12-31';}
      wrap.append(l,input);block.append(wrap);
    }
    const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='Remover cheque';remove.addEventListener('click',()=>{block.remove();form.elements.confirm_credit.checked=false;update();});block.append(remove);checks.append(block);block.querySelector('input').focus();update();
  });
  form.addEventListener('input',event=>{if(event.target.name!=='confirm_credit'&&event.target.name!=='confirm')form.elements.confirm_credit.checked=false;update();});
  form.addEventListener('submit',()=>update());
})();
