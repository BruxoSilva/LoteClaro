(function (root) {
  'use strict';
  const abs = n => n < 0n ? -n : n;
  function rational(n, d = 1n) {
    if (!d) throw Error('Não é possível dividir por zero.');
    if (d < 0n) {n = -n; d = -d;}
    let a = abs(n), b = d;
    while (b) [a,b] = [b,a%b];
    n /= a; d /= a;
    if (n.toString().length > 1200 || d.toString().length > 1200) throw Error('Valor muito grande. Simplifique o cálculo.');
    return {n,d};
  }
  const mul = (a,b) => rational(a.n*b.n,a.d*b.d);
  function evaluate(expression) {
    if (typeof expression !== 'string' || expression.length > 2048) throw Error('Expressão muito longa.');
    const source=expression.replace(/×/g,'*').replace(/÷/g,'/').replace(/−/g,'-').replace(/,/g,'.');
    const tokens=[];
    let pos=0;
    while (pos<source.length) {
      if (/\s/.test(source[pos])) {pos++; continue;}
      const m=/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/.exec(source.slice(pos));
      if (m) {tokens.push(m[0]);pos+=m[0].length;}
      else if ('+-*/()%'.includes(source[pos])) tokens.push(source[pos++]);
      else throw Error('Expressão inválida. Use números e operadores matemáticos.');
      if (tokens.length>512) throw Error('Expressão muito longa.');
    }
    let index=0,depth=0;
    function atom() {
      if (++depth>64) throw Error('Parênteses ou sinais em excesso.');
      let result;
      const token=tokens[index++];
      if (token==='+' || token==='-') result={kind:'unary',op:token,value:atom()};
      else if (token==='(') {
        result=sum();
        if (tokens[index++]!==')') throw Error('Feche os parênteses da expressão.');
      } else if (token && /^\d|^\./.test(token)) {
        const [mantissa,exp='0']=token.toLowerCase().split('e');
        if (mantissa.length>300 || Math.abs(Number(exp))>300) throw Error('Número fora do limite da calculadora.');
        const [whole,fraction='']=mantissa.split('.');
        let n=BigInt((whole||'0')+fraction), d=10n**BigInt(fraction.length);
        const e=Number(exp);
        if (e>=0) n*=10n**BigInt(e); else d*=10n**BigInt(-e);
        result={kind:'number',value:rational(n,d)};
      } else throw Error('Expressão incompleta ou inválida. Confira os números e operadores.');
      while (tokens[index]==='%') {index++;result={kind:'percent',value:result};}
      depth--;
      return result;
    }
    function product() {
      let left=atom();
      while (['*','/'].includes(tokens[index])) {const op=tokens[index++];left={kind:'binary',op,left,right:atom()};}
      return left;
    }
    function sum() {
      let left=product();
      while (['+','-'].includes(tokens[index])) {const op=tokens[index++];left={kind:'binary',op,left,right:product()};}
      return left;
    }
    function run(node) {
      if (node.kind==='number') return {...node.value,percent:false};
      if (node.kind==='unary') {const v=run(node.value);return {...v,n:node.op==='-'?-v.n:v.n};}
      if (node.kind==='percent') return {...mul(run(node.value),rational(1n,100n)),percent:true};
      const a=run(node.left);let b=run(node.right);
      if ((node.op==='+'||node.op==='-') && b.percent) b=mul(a,b);
      if (node.op==='+') return rational(a.n*b.d+b.n*a.d,a.d*b.d);
      if (node.op==='-') return rational(a.n*b.d-b.n*a.d,a.d*b.d);
      if (node.op==='*') return mul(a,b);
      return rational(a.n*b.d,a.d*b.n);
    }
    const tree=sum();
    if (index!==tokens.length) throw Error('Expressão inválida. Confira os operadores e parênteses.');
    return format(run(tree));
  }
  function format({n,d}) {
    if (!n) return {raw:'0',display:'0'};
    const negative=n<0n;n=abs(n);
    let exponent=n.toString().length-d.toString().length;
    if (exponent>=0 ? n<d*10n**BigInt(exponent) : n*10n**BigInt(-exponent)<d) exponent--;
    const scale=15-exponent;
    const numerator=scale>=0?n*10n**BigInt(scale):n;
    const denominator=scale>=0?d:d*10n**BigInt(-scale);
    const rounded=(numerator*2n+denominator)/(2n*denominator);
    let digits=rounded.toString(), raw;
    if (scale<=0) raw=digits+'0'.repeat(-scale);
    else {digits=digits.padStart(scale+1,'0');raw=digits.slice(0,-scale)+'.'+digits.slice(-scale);raw=raw.replace(/0+$/,'').replace(/\.$/,'');}
    if (negative) raw='-'+raw;
    const unsigned=raw.replace('-','');
    const [whole,fraction='']=unsigned.split('.');
    let display;
    if (whole.length>16 || (whole==='0' && /^0{8}/.test(fraction))) {
      const significant=unsigned.replace('.','').replace(/^0+/,'').replace(/0+$/,'');
      const power=whole==='0'?-(fraction.search(/[1-9]/)+1):whole.length-1;
      display=significant[0]+(significant.length>1?','+significant.slice(1):'')+'e'+power;
    } else display=whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')+(fraction?','+fraction:'');
    return {raw:raw.replace('.',','),display:(negative?'-':'')+display};
  }
  const api={evaluate};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  else root.SafeMath=api;
})(typeof globalThis!=='undefined'?globalThis:this);
