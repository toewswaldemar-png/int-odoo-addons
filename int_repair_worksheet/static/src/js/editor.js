/* Plain browser behavior; QWeb supplies all initial values and URLs. */
(() => {
  'use strict';
  const form = document.getElementById('worksheet-form');
  if (!form) return;
  const local = form.dataset.localPreview === '1';
  const status = form.querySelector('.save-status');
  const rows = form.querySelector('#material-rows');
  const countField = form.querySelector('#material-count');
  const storageKey = 'be01412-local-preview-v1';
  let dirty = false;
  let submitting = false;
  const setStatus = text => { status.textContent = text; };
  function progress() {
    const checks = [...form.querySelectorAll('.check-row')].filter(row => !row.classList.contains('line-na'));
    const done = checks.filter(row => row.querySelector('input[type=radio]:checked') ||
      row.querySelector('select')?.value || row.querySelector('input[type=checkbox]:checked')).length;
    form.querySelector('.progress').textContent = done + ' / ' + checks.length + ' Zeilen bearbeitet';
  }
  function applyVariant() {
    const atc = form.querySelector('[name=variant]:checked')?.value === 'atc';
    form.querySelectorAll('[data-br-only="1"]').forEach(row => {
      const select = row.querySelector('select');
      const performed = row.querySelector('input[type=checkbox]');
      const wasDisabled = select.disabled;
      row.classList.toggle('line-na', atc);
      if (atc) { select.value = 'na'; if (performed) performed.checked = false; }
      else if (wasDisabled) select.value = '';
      select.disabled = atc;
      if (performed) performed.disabled = atc || select.value === 'na';
    });
    form.querySelectorAll('.check-row:not(.line-na)').forEach(row => {
      const select = row.querySelector('select');
      const performed = row.querySelector('input[type=checkbox]');
      if (select && performed) {
        performed.disabled = select.value === 'na';
        if (performed.disabled) performed.checked = false;
      }
    });
    progress();
  }
  function addMaterial(markDirty = true) {
    const index = rows.children.length;
    if (index >= 200) { setStatus('Maximal 200 Materialzeilen sind möglich.'); return false; }
    const row = rows.firstElementChild.cloneNode(true);
    row.querySelectorAll('input, textarea').forEach(input => {
      input.name = input.name.replace(/_\d+$/, '_' + index);
      input.value = '';
      input.setAttribute('aria-label', input.getAttribute('aria-label').replace(/Zeile \d+$/, 'Zeile ' + (index + 1)));
    });
    row.querySelector('button').setAttribute('aria-label', 'Materialzeile ' + (index + 1) + ' leeren');
    rows.appendChild(row);
    countField.value = String(index + 1);
    if (markDirty) change();
    return true;
  }
  function change() { dirty = true; setStatus('Ungespeicherte Änderungen'); applyVariant(); }
  form.addEventListener('input', change);
  form.addEventListener('change', change);
  form.addEventListener('click', event => {
    const clear = event.target.closest('[data-clear]');
    if (clear) {
      const row = clear.closest('.check-row');
      row.querySelectorAll('input[type=radio]').forEach(input => { input.checked = false; });
      change();
    }
    const remove = event.target.closest('.remove-material');
    if (remove) { remove.closest('tr').querySelectorAll('input,textarea').forEach(input => { input.value = ''; }); change(); }
    if (event.target.closest('#add-material')) addMaterial();
    if (event.target.closest('[data-reload]') && dirty) {
      if (!window.confirm('Ungespeicherte Änderungen verwerfen und den gespeicherten Stand laden?')) event.preventDefault();
      else dirty = false;
    }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty && !submitting) { event.preventDefault(); event.returnValue = ''; }
  });
  form.addEventListener('submit', event => {
    if (local) {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      delete data.csrf_token; delete data.edit_token;
      try {
        localStorage.setItem(storageKey, JSON.stringify(data));
        dirty = false;
        setStatus('Lokal in diesem Browser gespeichert · ' + new Date().toLocaleTimeString('de-DE'));
        if (event.submitter?.dataset.pdfButton) window.print();
      } catch (error) { setStatus('Speichern fehlgeschlagen. Eingaben bleiben geöffnet; Browserspeicher ist nicht verfügbar.'); }
    } else {
      submitting = true;
      setStatus('Wird in Odoo gespeichert …');
    }
  });
  if (local) {
    form.querySelector('[data-pdf-button]').textContent = 'Speichern & Drucken';
    form.querySelector('[data-reload]').href = location.href.split('#')[0];
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const data = JSON.parse(raw);
        const wanted = Math.max(14, Math.min(200, Number(data.material_count) || 14));
        while (rows.children.length < wanted) addMaterial(false);
        for (const input of form.elements) {
          if (!input.name || ['csrf_token', 'edit_token', 'intent'].includes(input.name)) continue;
          const value = data[input.name] || '';
          if (['checkbox','radio'].includes(input.type)) input.checked = input.value === value;
          else input.value = value;
        }
        setStatus('Lokal gespeicherte Eingaben geladen.');
      } else setStatus('Lokaler Test · noch nicht gespeichert');
    } catch (error) { setStatus('Lokaler Speicher nicht verfügbar. Eingaben sind bis zum Schließen möglich.'); }
  }
  if (form.querySelector('.notice.error')) { dirty = true; setStatus('Nicht gespeichert – bitte Eingaben prüfen.'); }
  applyVariant();
})();
