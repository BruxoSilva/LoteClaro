(function(root){
 'use strict';
 const historyKey='lote-claro:calculos:v1',draftKey='lote-claro:rascunho:v1';
 function validate(data){
  if(!data||data.format!=='lote-claro-transfer-1'||!Array.isArray(data.history)||!data.draft||!Array.isArray(data.draft.entries)||typeof data.draft.notes!=='string'||data.draft.notes.length>5000)throw Error('Arquivo de transferência inválido.');
  if(!data.history.every(e=>e&&typeof e.expression==='string'&&e.expression.length<=2048&&typeof e.raw==='string'&&/^-?\d+(?:,\d+)?$/.test(e.raw)&&e.raw.length<=1200&&typeof e.display==='string'&&e.display.length<=1200))throw Error('Histórico inválido.');
  if(!data.draft.entries.every(e=>e&&typeof e.client==='string'&&e.client.trim().length>0&&e.client.length<=160&&typeof e.cents==='string'&&/^\d{1,13}$/.test(e.cents)&&BigInt(e.cents)>0n&&BigInt(e.cents)<=1000000000000n&&typeof e.date==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(e.date)&&['cheque','dinheiro'].includes(e.method)))throw Error('Recebimentos inválidos.');
  return data;
 }
 function mergeList(current,incoming,fields){
  const identify=item=>JSON.stringify(fields.map(f=>item[f]));
  const counts=new Map();current.forEach(e=>counts.set(identify(e),(counts.get(identify(e))||0)+1));
  const extra=[];incoming.forEach(e=>{const k=identify(e),n=counts.get(k)||0;if(n)counts.set(k,n-1);else extra.push(e);});return [...extra,...current];
 }
 function merge(current,incoming){
  validate(current);validate(incoming);
  const notes=current.draft.notes===incoming.draft.notes?current.draft.notes:[current.draft.notes,incoming.draft.notes].filter(Boolean).join('\n\n');
  if(notes.length>5000)throw Error('As anotações juntas ultrapassam 5.000 caracteres. Nada foi importado. Guarde o arquivo e reduza as anotações antes de tentar novamente.');
  return {format:current.format,history:mergeList(current.history,incoming.history,['expression','raw','display']),draft:{entries:mergeList(current.draft.entries,incoming.draft.entries,['client','cents','date','method']),notes}};
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={validate,merge};return;}
 const status=document.getElementById('transfer-status');
 function message(text){status.textContent=text;status.className='notice';}
 function current(){return validate({format:'lote-claro-transfer-1',history:JSON.parse(localStorage.getItem(historyKey)||'[]'),draft:JSON.parse(sessionStorage.getItem(draftKey)||'{"entries":[],"notes":""}')});}
 document.getElementById('transfer-export').addEventListener('click',()=>{
  try{const data=current(),blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='LoteClaro_Calculadora_'+new Date().toISOString().slice(0,10)+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);message('Arquivo exportado. Os dados originais foram preservados.');}catch(e){message(e.message);}
 });
 document.getElementById('transfer-import').addEventListener('click',async()=>{
  const file=document.getElementById('transfer-file').files[0];
  try{
   if(!file||file.size>20*1024*1024)throw Error('Selecione um arquivo JSON de até 20 MB.');
   const incoming=validate(JSON.parse(await file.text())),before=current(),result=merge(before,incoming);
   if(!confirm(`Acrescentar os dados do arquivo? O histórico atual será preservado.`))return;
   const backupKey='lote-claro:antes-transferencia:'+Date.now();
   localStorage.setItem(backupKey,JSON.stringify(before));
   const oldHistory=localStorage.getItem(historyKey),oldDraft=sessionStorage.getItem(draftKey);
   try{localStorage.setItem(historyKey,JSON.stringify(result.history));sessionStorage.setItem(draftKey,JSON.stringify(result.draft));}
   catch(e){if(oldHistory===null)localStorage.removeItem(historyKey);else localStorage.setItem(historyKey,oldHistory);if(oldDraft===null)sessionStorage.removeItem(draftKey);else sessionStorage.setItem(draftKey,oldDraft);throw e;}
   message('Importação concluída. Abra a calculadora para conferir. Uma cópia anterior foi preservada neste navegador.');
  }catch(e){message('Não foi possível importar: '+e.message);}
 });
})(globalThis);
