const test=require('node:test'),assert=require('node:assert/strict');
const {validate,merge}=require('../static/calculator-transfer.js');
const history={expression:'2+3',raw:'5',display:'5'};
const entry={client:'Cliente',cents:'100',date:'2026-11-03',method:'dinheiro'};
const packet=(h=[],e=[],notes='')=>({format:'lote-claro-transfer-1',history:h,draft:{entries:e,notes}});
test('keeps existing and imported repeated calculations',()=>{const result=merge(packet([history]),packet([history,history],[entry],'anotação'));assert.equal(result.history.length,2);assert.equal(result.draft.notes,'anotação');});
test('repeated import does not duplicate',()=>{const original=packet([history,history],[entry],'abc');assert.deepEqual(merge(original,original),original);});
test('preserves both note texts',()=>assert.equal(merge(packet([],[],'abc'),packet([],[],'def')).draft.notes,'abc\n\ndef'));
test('refuses invalid data and overlong combined notes',()=>{assert.throws(()=>validate({}));assert.throws(()=>merge(packet([],[],'a'.repeat(3000)),packet([],[],'b'.repeat(3000))));});
