(function () {
  const form = document.getElementById('FiltersForm');
  if (!form) return;

  const periodSel = document.getElementById('f_period');
  const nextNWrap = document.getElementById('f_next_n_wrap');

  function toggleNextN() {
    nextNWrap.style.display = (periodSel.value === 'NEXT_N') ? '' : 'none';
  }
  periodSel?.addEventListener('change', toggleNextN);
  toggleNextN();

  document.querySelector('.js-apply-filters')?.addEventListener('click', () => {
    const payload = {
      q: form.querySelector('[name="q"]')?.value || '',
      invitations: form.querySelector('#f_inv')?.checked ? 1 : 0,
      organiser: form.querySelector('#f_org')?.checked ? 1 : 0,
      participant: form.querySelector('#f_part')?.checked ? 1 : 0,
      declined: form.querySelector('#f_decl')?.checked ? 1 : 0,
      period: form.querySelector('#f_period')?.value || 'THIS_MONTH',
      next_n_days: form.querySelector('[name="next_n_days"]')?.value || ''
    };
    document.dispatchEvent(new CustomEvent('calendar:filters-applied', { detail: payload }));
  });
})();
