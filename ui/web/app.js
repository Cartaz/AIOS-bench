(() => {
  const state = { backend: null, catalog: null, doctor: null, harnesses: new Set(), tasks: new Set(), running: false, cancelling: false };
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function toggleSet(set, value, enabled) { enabled ? set.add(value) : set.delete(value); }
  function setRunState(value) {
    state.running = Boolean(value.running);
    state.cancelling = Boolean(value.cancelling);
    $('start').disabled = state.running;
    $('cancel').disabled = !state.running || state.cancelling;
    $('runBadge').textContent = state.cancelling ? 'Annullamento…' : (state.running ? 'In esecuzione' : 'Pronto');
    $('runBadge').classList.toggle('running', state.running);
  }
  function showView(name) { $('benchmarkView').classList.toggle('hidden', name !== 'benchmark'); $('doctorView').classList.toggle('hidden', name !== 'doctor'); document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('selected', button.dataset.view === name)); if (name === 'doctor') loadDoctor(); }

  function renderHarnesses() {
    const readiness = new Map((state.doctor?.report?.harnesses || []).map(item => [item.name, item.installed]));
    $('harnesses').innerHTML = state.catalog.harnesses.map(h => `
      <div class="toggle ${state.harnesses.has(h.id) ? 'selected' : ''}" tabindex="0" role="checkbox" aria-checked="${state.harnesses.has(h.id)}" data-harness="${esc(h.id)}">
        <span class="dot"></span><span>${esc(h.name)}${readiness.has(h.id) && !readiness.get(h.id) ? ' · setup richiesto' : ''}</span>
      </div>`).join('');
  }

  function renderTasks() {
    const groups = {};
    state.catalog.tasks.forEach(task => (groups[task.category] ||= []).push(task));
    $('tasks').innerHTML = Object.entries(groups).map(([category, tasks]) => `<section><div class="group-title">${esc(category)}</div><div class="group-items">${tasks.map(task => `<div class="task ${state.tasks.has(task.id) ? 'selected' : ''}" tabindex="0" role="checkbox" aria-checked="${state.tasks.has(task.id)}" data-task="${esc(task.id)}"><span class="dot"></span><div><strong>${esc(task.id)}</strong><div class="task-meta">T${task.tier} · ${esc(task.mode)}${task.depends_on.length ? ` · richiede ${esc(task.depends_on.join(', '))}` : ''}</div></div></div>`).join('')}</div></section>`).join('');
    $('taskSummary').textContent = `${state.tasks.size} / ${state.catalog.tasks.length} selezionati`;
  }

  function renderDoctor() {
    if (!state.doctor?.report) return;
    const report = state.doctor.report, system = report.system;
    $('systemStatus').textContent = `${system.platform} ${system.release} · Python ${system.python} · Node ${system.node ? 'OK' : 'mancante'} · npm ${system.npm ? 'OK' : 'mancante'} · bwrap ${system.bubblewrap ? 'OK' : 'mancante'}`;
    $('doctorHarnesses').innerHTML = report.harnesses.map(item => {
      const install = item.install || {}, manual = !item.installed && !install.automatic;
      return `<article class="doctor-item ${item.installed ? 'ready' : ''}"><span class="dot"></span><div class="details"><strong>${esc(item.display_name)}</strong><div class="status">${item.installed ? 'Pronto' : 'Setup richiesto'}</div><div class="task-meta">${esc(item.version || item.path || item.config_hint)}</div>${manual && install.manual_command ? `<code>${esc(install.manual_command)}</code>` : ''}${install.note ? `<div class="task-meta">${esc(install.note)}</div>` : ''}</div><div class="doctor-actions">${!item.installed && install.automatic ? `<button data-install="${esc(item.name)}">Installa</button>` : ''}<button data-docs="${esc(install.docs || item.docs)}">Istruzioni</button></div></article>`;
    }).join('');
    const profile = state.doctor.profile || {};
    $('profileModel').value = profile.model || '';
    $('openaiUrl').value = profile.openai_url || '';
    $('anthropicUrl').value = profile.anthropic_url || '';
    if (!$('model').value && profile.model) $('model').value = profile.model;
    renderHarnesses();
  }

  function loadCatalog() { state.backend.getCatalog($('suite').value, raw => { const catalog = JSON.parse(raw || '{}'); if (!catalog.tasks) return; state.catalog = catalog; state.harnesses = new Set(catalog.harnesses.map(h => h.id)); state.tasks = new Set(catalog.tasks.map(t => t.id)); renderHarnesses(); renderTasks(); }); }
  function loadDoctor() { state.backend.getDoctor(raw => { const value = JSON.parse(raw || '{}'); if (!value.report) return; state.doctor = value; renderDoctor(); }); }
  function activateSelector(selector, attr, set, render, event) { const item = event.target.closest(selector); if (!item) return; const value = item.dataset[attr]; toggleSet(set, value, !set.has(value)); render(); }

  document.addEventListener('click', event => {
    const view = event.target.dataset?.view; if (view) showView(view);
    if (state.catalog) { activateSelector('[data-harness]', 'harness', state.harnesses, renderHarnesses, event); activateSelector('[data-task]', 'task', state.tasks, renderTasks, event); }
    const hAction = event.target.dataset?.harnessAction; if (hAction && state.catalog) { state.harnesses = new Set(hAction === 'all' ? state.catalog.harnesses.map(h => h.id) : []); renderHarnesses(); }
    const tAction = event.target.dataset?.taskAction; if (tAction && state.catalog) { state.tasks = new Set(tAction === 'all' ? state.catalog.tasks.map(t => t.id) : []); renderTasks(); }
    const install = event.target.dataset?.install; if (install) { $('doctorError').textContent = ''; state.backend.installHarness(install, ok => { if (ok) loadDoctor(); }); }
    const docs = event.target.dataset?.docs; if (docs) window.open(docs, '_blank', 'noopener');
  });
  document.addEventListener('keydown', event => { if (!['Enter', ' '].includes(event.key)) return; const item = event.target.closest('[data-harness],[data-task]'); if (item) { event.preventDefault(); item.click(); } });

  $('suite').addEventListener('change', loadCatalog);
  $('refreshDoctor').addEventListener('click', loadDoctor);
  $('saveProfile').addEventListener('click', () => { $('doctorError').textContent = ''; const payload = { model: $('profileModel').value, openai_url: $('openaiUrl').value, anthropic_url: $('anthropicUrl').value }; state.backend.saveDoctorProfile(JSON.stringify(payload), ok => { if (ok) { $('model').value = payload.model.trim(); loadDoctor(); } }); });
  $('start').addEventListener('click', () => { $('error').textContent = ''; const totalTimeout = $('totalTimeout').value.trim(); const payload = { suite: $('suite').value, harnesses: [...state.harnesses], task_ids: [...state.tasks], model: $('model').value.trim() || 'unknown', repeats: Number($('repeats').value), seed: Number($('seed').value), task_timeout: Number($('timeout').value), total_timeout: totalTimeout ? Number(totalTimeout) : null }; state.backend.startRun(JSON.stringify(payload), ok => { if (ok) setRunState({running: true}); }); });
  $('cancel').addEventListener('click', () => { if (!state.running || state.cancelling) return; state.backend.cancelRun(ok => { if (ok) setRunState({running: true, cancelling: true}); }); });

  new QWebChannel(qt.webChannelTransport, channel => {
    state.backend = channel.objects.backend;
    state.backend.errorOccurred.connect(message => { const target = $('doctorView').classList.contains('hidden') ? $('error') : $('doctorError'); target.textContent = message; });
    state.backend.doctorChanged.connect(raw => { const value = JSON.parse(raw || '{}'); if (value.report) { state.doctor = value; renderDoctor(); } });
    state.backend.runStateChanged.connect(raw => setRunState(JSON.parse(raw)));
    state.backend.progressChanged.connect(raw => { const event = JSON.parse(raw); const done = event.completed_units || 0, total = event.total_units || 0; $('counter').textContent = `${done} / ${total}`; $('progressBar').style.width = total ? `${Math.min(100, done / total * 100)}%` : '0%'; if (event.type === 'task_started') $('current').textContent = `${event.harness} · ${event.task_id}`; if (event.type === 'task_finished') { const line = document.createElement('div'); line.textContent = `${event.harness} · ${event.task_id} · ${event.status || (event.success ? 'PASS' : 'FAIL')}`; $('events').prepend(line); } if (event.type === 'run_cancelled') $('current').textContent = 'Run annullata.'; });
    state.backend.runFinished.connect(raw => { const result = JSON.parse(raw || '{}'); $('current').textContent = result.cancelled ? 'Run annullata.' : 'Run completata.'; });
    loadCatalog(); loadDoctor();
  });
})();
