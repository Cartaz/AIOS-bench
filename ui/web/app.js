(() => {
  const state = { backend: null, catalog: null, harnesses: new Set(), tasks: new Set(), running: false };
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function toggleSet(set, value, enabled) { enabled ? set.add(value) : set.delete(value); }
  function setRunning(running) {
    state.running = running;
    $('start').disabled = running;
    $('runBadge').textContent = running ? 'In esecuzione' : 'Pronto';
    $('runBadge').classList.toggle('running', running);
  }

  function renderHarnesses() {
    $('harnesses').innerHTML = state.catalog.harnesses.map(h => `
      <div class="toggle ${state.harnesses.has(h.id) ? 'selected' : ''}" tabindex="0" role="checkbox" aria-checked="${state.harnesses.has(h.id)}" data-harness="${esc(h.id)}">
        <span class="dot"></span><span>${esc(h.name)}</span>
      </div>`).join('');
  }

  function renderTasks() {
    const groups = {};
    state.catalog.tasks.forEach(task => (groups[task.category] ||= []).push(task));
    $('tasks').innerHTML = Object.entries(groups).map(([category, tasks]) => `
      <section><div class="group-title">${esc(category)}</div><div class="group-items">
      ${tasks.map(task => `<div class="task ${state.tasks.has(task.id) ? 'selected' : ''}" tabindex="0" role="checkbox" aria-checked="${state.tasks.has(task.id)}" data-task="${esc(task.id)}"><span class="dot"></span><div><strong>${esc(task.id)}</strong><div class="task-meta">T${task.tier} · ${esc(task.mode)}${task.depends_on.length ? ` · richiede ${esc(task.depends_on.join(', '))}` : ''}</div></div></div>`).join('')}
      </div></section>`).join('');
    $('taskSummary').textContent = `${state.tasks.size} / ${state.catalog.tasks.length} selezionati`;
  }

  function loadCatalog() {
    state.backend.getCatalog($('suite').value, raw => {
      const catalog = JSON.parse(raw || '{}');
      if (!catalog.tasks) return;
      state.catalog = catalog;
      state.harnesses = new Set(catalog.harnesses.map(h => h.id));
      state.tasks = new Set(catalog.tasks.map(t => t.id));
      renderHarnesses(); renderTasks();
    });
  }

  function activateSelector(selector, attr, set, render, event) {
    const item = event.target.closest(selector);
    if (!item) return;
    const value = item.dataset[attr];
    toggleSet(set, value, !set.has(value)); render();
  }

  document.addEventListener('click', event => {
    if (state.catalog) {
      activateSelector('[data-harness]', 'harness', state.harnesses, renderHarnesses, event);
      activateSelector('[data-task]', 'task', state.tasks, renderTasks, event);
    }
    const hAction = event.target.dataset?.harnessAction;
    if (hAction && state.catalog) { state.harnesses = new Set(hAction === 'all' ? state.catalog.harnesses.map(h => h.id) : []); renderHarnesses(); }
    const tAction = event.target.dataset?.taskAction;
    if (tAction && state.catalog) { state.tasks = new Set(tAction === 'all' ? state.catalog.tasks.map(t => t.id) : []); renderTasks(); }
  });

  document.addEventListener('keydown', event => {
    if (!['Enter', ' '].includes(event.key)) return;
    const item = event.target.closest('[data-harness],[data-task]');
    if (item) { event.preventDefault(); item.click(); }
  });

  $('suite').addEventListener('change', loadCatalog);
  $('start').addEventListener('click', () => {
    $('error').textContent = '';
    const totalTimeout = $('totalTimeout').value.trim();
    const payload = {
      suite: $('suite').value,
      harnesses: [...state.harnesses],
      task_ids: [...state.tasks],
      model: $('model').value.trim() || 'unknown',
      repeats: Number($('repeats').value),
      seed: Number($('seed').value),
      task_timeout: Number($('timeout').value),
      total_timeout: totalTimeout ? Number(totalTimeout) : null
    };
    state.backend.startRun(JSON.stringify(payload), ok => { if (ok) setRunning(true); });
  });

  new QWebChannel(qt.webChannelTransport, channel => {
    state.backend = channel.objects.backend;
    state.backend.errorOccurred.connect(message => { $('error').textContent = message; });
    state.backend.runStateChanged.connect(raw => setRunning(Boolean(JSON.parse(raw).running)));
    state.backend.progressChanged.connect(raw => {
      const event = JSON.parse(raw);
      const done = event.completed_units || 0, total = event.total_units || 0;
      $('counter').textContent = `${done} / ${total}`;
      $('progressBar').style.width = total ? `${Math.min(100, done / total * 100)}%` : '0%';
      if (event.type === 'task_started') $('current').textContent = `${event.harness} · ${event.task_id}`;
      if (event.type === 'task_finished') {
        const line = document.createElement('div');
        line.textContent = `${event.harness} · ${event.task_id} · ${event.status || (event.success ? 'PASS' : 'FAIL')}`;
        $('events').prepend(line);
      }
    });
    state.backend.runFinished.connect(() => { $('current').textContent = 'Run completata.'; });
    loadCatalog();
  });
})();
