'use strict';
document.querySelector('#go-back')?.addEventListener('click', () => history.back());
const filter = document.querySelector('#filter');
filter?.addEventListener('input', () => {
  let visible = 0;
  document.querySelectorAll('[data-filter] tbody tr').forEach(row => {
    row.hidden = !row.textContent.toLocaleLowerCase('pt-BR').includes(filter.value.toLocaleLowerCase('pt-BR'));
    if (!row.hidden) visible++;
  });
  const noMatch = document.querySelector('#no-match');
  if (noMatch) noMatch.hidden = visible > 0;
});
const sale = document.querySelector('#sale-form');
if (sale) {
  const scaled = (value, digits) => {
    const clean = value.trim().replace(',', '.');
    if (!/^\d+(\.\d+)?$/.test(clean)) return null;
    const [whole, fraction = ''] = clean.split('.');
    if (fraction.length > digits) return null;
    return BigInt(whole + fraction.padEnd(digits, '0'));
  };
  const update = () => {
    const weight = scaled(sale.elements.weight.value, 3);
    const price = scaled(sale.elements.price.value, 2);
    const out = document.querySelector('#sale-total');
    if (weight === null || price === null) {out.textContent = 'Preencha peso e valor por kg'; return;}
    const cents = (weight * price + 500n) / 1000n;
    out.textContent = 'R$ ' + (cents / 100n).toLocaleString('pt-BR') + ',' + (cents % 100n).toString().padStart(2, '0');
  };
  sale.addEventListener('input', update);
  update();
}
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {
  if (form.hasAttribute('data-local-form')) return;
  if (form.checkValidity()) form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
}));
window.addEventListener('pageshow', () => document.querySelectorAll('button[disabled]').forEach(button => {button.disabled = false;}));
