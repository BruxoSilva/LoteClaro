(() => {
  'use strict';
  const $=id=>document.getElementById(id), input=$('math-expression');
  const key='lote-claro:calculos:v1';
  let history=[], completed=false, pendingPosition=null;
  const error=message=>{$('math-error').textContent=message;};
  function store() {
    try {localStorage.setItem(key,JSON.stringify(history));}
    catch (_) {error('Não foi possível salvar o histórico neste navegador. Libere o armazenamento para preservá-lo.');}
  }
  function validEntry(e) {
    return e && typeof e.expression==='string' && e.expression.length<=2048 && typeof e.raw==='string' && /^-?\d+(?:,\d+)?$/.test(e.raw) && e.raw.length<=1200 && typeof e.display==='string' && e.display.length<=1200;
  }
  try {const saved=JSON.parse(localStorage.getItem(key)||'[]');if(!Array.isArray(saved)||!saved.every(validEntry))throw Error();history=saved;}
  catch (_) {error('Não foi possível recuperar o histórico salvo.');}
  function render() {
    $('math-history-list').replaceChildren();
    $('math-history-empty').hidden=history.length>0;
    history.forEach((entry,index)=>{
      const li=document.createElement('li'), expression=document.createElement('p'), button=document.createElement('button');
      expression.textContent=entry.expression+' =';
      button.type='button';button.className='secondary';button.textContent=entry.display;button.dataset.historyIndex=String(index);
      button.setAttribute('aria-label','Inserir resultado '+entry.display);
      li.append(expression,button);$('math-history-list').append(li);
    });
  }
  function insert(text,position=null,replaceSelection=true) {
    const focused=document.activeElement===input;
    const start=position ?? (focused?input.selectionStart:input.value.length);
    const end=position!==null || !replaceSelection?start:(focused?input.selectionEnd:start);
    if (input.value.length-(end-start)+text.length>2048) {error('Expressão muito longa.');return;}
    input.value=input.value.slice(0,start)+text+input.value.slice(end);
    input.focus();input.setSelectionRange(start+text.length,start+text.length);
    completed=false;error('');
  }
  function calculate() {
    try {
      const expression=input.value.trim(), result=SafeMath.evaluate(expression);
      $('math-result').textContent=result.display;
      history.unshift({expression,raw:result.raw,display:result.display});render();error('');store();
      input.value=result.raw;input.focus();input.setSelectionRange(input.value.length,input.value.length);completed=true;
    } catch (e) {error(e.message);completed=false;}
  }
  function act(value) {
    if (value==='equals') {calculate();return;}
    if (value==='clear') {input.value='';$('math-result').textContent='0';error('');completed=false;input.focus();return;}
    if (value==='back') {
      const start=document.activeElement===input?input.selectionStart:input.value.length;
      const end=document.activeElement===input?input.selectionEnd:start;
      const from=start===end?Math.max(0,start-1):start;
      input.value=input.value.slice(0,from)+input.value.slice(end);input.focus();input.setSelectionRange(from,from);completed=false;error('');return;
    }
    if (value==='sign') {
      if (!input.value) {insert('-');return;}
      const start=input.selectionStart,end=input.selectionEnd;
      if (start!==end) {insert('-('+input.value.slice(start,end)+')');return;}
      input.value=input.value.startsWith('-(')&&input.value.endsWith(')')?input.value.slice(2,-1):'-('+input.value+')';
      input.focus();input.setSelectionRange(input.value.length,input.value.length);completed=false;error('');return;
    }
    if (completed && /[0-9,(.]/.test(value)) input.value='';
    insert(value==='.'?',':value);
  }
  document.querySelector('.math-keys').addEventListener('pointerdown',e=>{if(e.target.closest('button'))e.preventDefault();});
  document.querySelector('.math-keys').addEventListener('click',e=>{const b=e.target.closest('[data-math]');if(b)act(b.dataset.math);});
  input.addEventListener('input',()=>{completed=false;error('');});
  document.addEventListener('keydown',event=>{
    if(event.isComposing||event.ctrlKey||event.metaKey||event.altKey)return;
    const target=event.target;
    if(target!==input && (target.closest('input,textarea,select,[contenteditable=true]') || !target.closest('.math-panel')))return;
    if(target.tagName==='BUTTON' && ['Enter',' '].includes(event.key))return;
    if(event.key==='Enter'){event.preventDefault();act('equals');}
    else if(event.key==='Escape'){event.preventDefault();act('clear');}
    else if(event.key==='Backspace'){event.preventDefault();act('back');}
    else if(/^[0-9+\-*/%,.()]$/.test(event.key)){event.preventDefault();act(event.key);}
  });
  const toggle=$('math-history-toggle');
  toggle.addEventListener('pointerdown',e=>{if(document.activeElement===input)e.preventDefault();});
  toggle.addEventListener('click',()=>{
    const open=$('math-history').hidden;
    $('math-history').hidden=!open;toggle.setAttribute('aria-expanded',String(open));
    toggle.setAttribute('aria-label',open?'Fechar histórico de cálculos':'Abrir histórico de cálculos');
    document.querySelector('.math-layout').classList.toggle('with-history',open);
  });
  $('math-history-list').addEventListener('pointerdown',event=>{
    if(!event.target.closest('button'))return;
    pendingPosition=document.activeElement===input?input.selectionStart:input.value.length;
    event.preventDefault();
  });
  $('math-history-list').addEventListener('click',event=>{
    const button=event.target.closest('[data-history-index]');if(!button)return;
    const entry=history[Number(button.dataset.historyIndex)];
    const position=pendingPosition??(document.activeElement===input?input.selectionStart:input.value.length);
    pendingPosition=null;insert(entry.raw,position,false);
  });
  $('math-history-clear').addEventListener('click',()=>{
    if(!confirm('Apagar todo o histórico de cálculos deste navegador?'))return;
    history=[];error('');store();render();
  });
  render();
})();
