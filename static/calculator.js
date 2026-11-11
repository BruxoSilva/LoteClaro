/* Independent scratchpad. No requests, database writes or generated files. */
(() => {
  'use strict';
  const key = 'lote-claro:rascunho:v1';
  const $ = id => document.getElementById(id);
  const form = $('draft-form');
  let entries = [], editing = null, storageAvailable = true;
  const money = cents => 'R$ ' + (cents / 100n).toLocaleString('pt-BR') + ',' + (cents % 100n).toString().padStart(2, '0');
  const dateLabel = date => date.split('-').reverse().join('/');
  const methodLabel = method => method === 'cheque' ? 'Cheque' : 'Dinheiro';
  const validDate = date => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
    const [y,m,d] = date.split('-').map(Number);
    const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
    return y > 0 && m >= 1 && m <= 12 && d >= 1 && d <= [31,leap?29:28,31,30,31,30,31,31,30,31,30,31][m-1];
  };
  function status(message) {
    $('draft-status').textContent = message;
    $('draft-status').className = message ? 'notice' : '';
  }
  function save() {
    $('draft-report').hidden = true;
    try {
      sessionStorage.setItem(key, JSON.stringify({entries,notes:$('draft-notes').value}));
    } catch (_) {
      storageAvailable = false;
      status('O navegador não permitiu guardar o rascunho nesta sessão. Ele ficará apenas nesta página e será perdido ao sair ou atualizar.');
    }
  }
  function cell(row, text) {
    const td = document.createElement('td');
    td.textContent = text;
    row.append(td);
    return td;
  }
  function entryRow(entry) {
    const row = document.createElement('tr');
    [dateLabel(entry.date),entry.client,methodLabel(entry.method),money(BigInt(entry.cents))].forEach(value => cell(row,value));
    return row;
  }
  function render() {
    $('draft-rows').replaceChildren();
    entries.forEach((entry,index) => {
      const row = entryRow(entry), actions = cell(row,'');
      actions.className='draft-row-actions';
      for (const [label,action] of [['Editar','edit'],['Excluir','delete']]) {
        const button = document.createElement('button');
        button.type='button'; button.className='secondary'; button.textContent=label;
        button.dataset.action=action; button.dataset.index=String(index);
        button.setAttribute('aria-label',`${label} recebimento ${index+1} de ${entry.client}`);
        actions.append(button);
      }
      $('draft-rows').append(row);
    });
    $('draft-count').textContent=String(entries.length);
    $('draft-empty').hidden=entries.length>0;
    $('draft-table').hidden=entries.length===0;
  }
  function resetForm() {
    editing=null; form.reset();
    $('draft-form-title').textContent='Adicionar recebimento';
    $('draft-save').textContent='Adicionar ao rascunho';
    $('draft-cancel').hidden=true;
    form.querySelectorAll('input').forEach(input=>input.setCustomValidity(''));
  }
  try {
    const raw=sessionStorage.getItem(key);
    if (raw) {
      const draft=JSON.parse(raw);
      if (!Array.isArray(draft.entries) || typeof draft.notes!=='string' || draft.notes.length>5000 || !draft.entries.every(e =>
        e && typeof e.client==='string' && e.client.trim().length>0 && e.client.length<=160 &&
        typeof e.cents==='string' && /^\d{1,13}$/.test(e.cents) && BigInt(e.cents)>0n && BigInt(e.cents)<=1000000000000n &&
        typeof e.date==='string' && validDate(e.date) && ['cheque','dinheiro'].includes(e.method))) throw Error('invalid draft');
      entries=draft.entries; $('draft-notes').value=draft.notes;
    }
  } catch (_) {
    status('Não foi possível recuperar o rascunho anterior. Você pode começar um novo rascunho nesta página.');
  }
  form.addEventListener('input',event=>event.target.setCustomValidity?.(''));
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const raw=$('draft-amount').value.trim().replace(',','.');
    const match=/^(\d{1,11})(?:\.(\d{1,2}))?$/.exec(raw);
    const cents=match ? BigInt(match[1]+(match[2]||'').padEnd(2,'0')) : 0n;
    if (!match || cents<=0n || cents>1000000000000n) {
      $('draft-amount').setCustomValidity('Informe um valor maior que zero, com até duas casas decimais, sem separador de milhares.');
    }
    const client=$('draft-client').value.trim();
    if (!client) $('draft-client').setCustomValidity('Informe o nome do cliente.');
    if (!validDate($('draft-date').value)) $('draft-date').setCustomValidity('Selecione uma data válida.');
    if (!form.reportValidity()) return;
    const entry={client,cents:String(cents),date:$('draft-date').value,method:$('draft-method').value};
    if (editing===null) entries.push(entry); else entries[editing]=entry;
    resetForm(); status('Recebimento salvo no rascunho. Gere o relatório para conferir os totais.'); save(); render();
    $('draft-amount').focus();
  });
  $('draft-rows').addEventListener('click',event=>{
    const button=event.target.closest('button[data-action]');
    if (!button) return;
    const index=Number(button.dataset.index),entry=entries[index];
    if (!entry) return;
    if (button.dataset.action==='delete') {
      if (!confirm(`Excluir do rascunho o recebimento de ${entry.client}, no valor de ${money(BigInt(entry.cents))}?`)) return;
      entries.splice(index,1); resetForm(); status('Recebimento excluído do rascunho.'); save(); render(); return;
    }
    editing=index;
    $('draft-amount').value=(BigInt(entry.cents)/100n)+','+(BigInt(entry.cents)%100n).toString().padStart(2,'0');
    $('draft-client').value=entry.client; $('draft-date').value=entry.date; $('draft-method').value=entry.method;
    $('draft-form-title').textContent='Editar recebimento'; $('draft-save').textContent='Salvar alteração'; $('draft-cancel').hidden=false;
    form.querySelectorAll('input').forEach(input=>input.setCustomValidity(''));
    $('draft-report').hidden=true; $('draft-amount').focus();
  });
  $('draft-cancel').addEventListener('click',resetForm);
  $('draft-notes').addEventListener('input',save);
  $('draft-clear').addEventListener('click',()=>{
    if (!confirm('Limpar todos os recebimentos e anotações deste rascunho?')) return;
    entries=[]; $('draft-notes').value=''; resetForm(); save(); render(); status('Rascunho limpo.');
  });
  $('draft-generate').addEventListener('click',()=>{
    if (editing!==null) {status('Salve ou cancele a edição antes de gerar o relatório.'); return;}
    if (!entries.length) {status('Adicione pelo menos um recebimento para gerar o relatório.'); $('draft-amount').focus(); return;}
    let cheque=0n,cash=0n;
    const clients=new Map();
    $('draft-report-rows').replaceChildren(); $('draft-clients').replaceChildren();
    entries.forEach(entry=>{
      const cents=BigInt(entry.cents);
      if (entry.method==='cheque') cheque+=cents; else cash+=cents;
      const group=clients.get(entry.client)||{cheque:0n,dinheiro:0n}; group[entry.method]+=cents; clients.set(entry.client,group);
      $('draft-report-rows').append(entryRow(entry));
    });
    clients.forEach((group,name)=>{
      const row=document.createElement('tr');
      [name,money(group.cheque),money(group.dinheiro),money(group.cheque+group.dinheiro)].forEach(value=>cell(row,value));
      $('draft-clients').append(row);
    });
    $('draft-cheque').textContent=money(cheque); $('draft-cash').textContent=money(cash); $('draft-total').textContent=money(cheque+cash);
    $('draft-equation').textContent=`Cheques ${money(cheque)} + dinheiro ${money(cash)} = ${money(cheque+cash)}.`;
    $('draft-report-count').textContent=`${entries.length} recebimento(s) · ${clients.size} cliente(s).`;
    $('draft-report-notes').textContent=$('draft-notes').value.trim()||'Nenhuma anotação.';
    status(storageAvailable?'Relatório atualizado somente nesta tela.':'Relatório atualizado. O rascunho está apenas na memória desta página.');
    $('draft-report').hidden=false; $('draft-report').focus();
  });
  window.addEventListener('beforeunload',event=>{
    if (!storageAvailable && (entries.length||$('draft-notes').value)) {event.preventDefault(); event.returnValue='';}
  });
  render();
})();
