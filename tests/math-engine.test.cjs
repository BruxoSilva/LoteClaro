const test=require('node:test');
const assert=require('node:assert/strict');
const {evaluate}=require('../static/math-engine.js');
const cases=[['2+3','5'],['8-10','-2'],['6*7','42'],['9/4','2,25'],['2+3*4','14'],['(2+3)*4','20'],['-5*-2','10'],['2--3','5'],['2+-3','-1'],['0,1+0,2','0,3'],['0.1+0.2','0,3'],['200*10%','20'],['200/10%','2000'],['200+10%','220'],['200-10%','180'],['10%','0,1'],['200+10%+10%','242'],['200+(10%)','220'],['-(2+3)','-5'],['1/3','0,3333333333333333'],['1e-20+1e-20','0,00000000000000000002'],['1e30*2','2000000000000000000000000000000'],['0*5','0'],['-0','0'],['.5+.25','0,75'],['200×10%','20'],['200÷10%','2000']];
for(const [expression,result] of cases)test(expression,()=>assert.equal(evaluate(expression).raw,result));
for(const expression of ['1/0','0/0','1/(2-2)','','2+','2**3','(2+3','2+3)','2(3)','1 2','hello','1;alert(1)','1,2,3','1e999','('.repeat(70)+'1'+')'.repeat(70)])test('reject '+expression.slice(0,30),()=>assert.throws(()=>evaluate(expression)));
test('Brazilian display',()=>assert.equal(evaluate('200/10%').display,'2.000'));
test('scientific displays',()=>{assert.equal(evaluate('1e30').display,'1e30');assert.equal(evaluate('1e-20').display,'1e-20');});
test('continue with prior result',()=>assert.equal(evaluate(evaluate('2+3').raw+'*4').raw,'20'));
