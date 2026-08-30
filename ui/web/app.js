import { connectBackend } from './backend.js';

const state = {
  backend: null,
  catalog: null,
  doctor: null,
  harnesses: new Set(),
  tasks: new Set(),
  running: false,
  busy: false,
  cancelling: false,
};

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

function toggleSet(set, value, enabled) {
  enabled ? set.add(value) : set.delete(value);
}

function setRunState(value) {
  state.running = Boolean(value.running);
  state.busy = Boolean(value.busy ?? value.running);
  state.cancelling = Boolean(value.cancelling);
  $('start').disabled = state.busy;
  $('cancel').disabled = !state.running || state.cancelling;
  $('refreshDoctor').disabled = state.busy;
  $('saveProfile').disabled = state.busy;
  $('runBadge').textContent = state.cancelling
    ? 'Annullamento…'
    : state.running
      ? 'In esecuzione'
      : state.busy
        ? 'Operazione in corso'
        : 'Pronto';
  $('runBadge').classList.toggle('running', state.busy);
  if (state.doctor?.report) renderDoctor();
}

function showView(name) {
  $('benchmarkView').classList.toggle('hidden', name !== 'benchmark');
  $('doctorView').classList.toggle('hidden', name !== 'doctor');
  document.querySelectorAll('[data-view]').forEach(button => {
    button.classList.toggle('selected', button.dataset.view === name);
  });
  if (name === 'doctor' && !state.busy) void loadDoctor();
}

function renderHarnesses() {
  if (!state.catalog) return;
  const readiness = new Map(
    (state.doctor?.report?.harnesses || []).map(item => [item.name, item.installed]),
  );
  $('harnesses').innerHTML = state.catalog.harnesses.map(h => `
    <div class="toggle ${state.harnesses.has(h.id) ? 'selected' : ''}" tabindex="0"
         role="checkbox" aria-checked="${state.harnesses.has(h.id)}" data-harness="${esc(h.id)}">
      <span class="dot"></span>
      <span>${esc(h.name)}${readiness.has(h.id) && !readiness.get(h.id) ? ' · setup richiesto' : ''}</span>
    </div>`).join('');
}

function renderTasks() {
  if (!state.catalog) return;
  const groups = {};
  state.catalog.tasks.forEach(task => (groups[task.category] ||= []).push(task));
  $('tasks').innerHTML = Object.entries(groups).map(([category, tasks]) => `
    <section>
      <div class="group-title">${esc(category)}</div>
      <div class="group-items">${tasks.map(task => `
        <div class="task ${state.tasks.has(task.id) ? 'selected' : ''}" tabindex="0"
             role="checkbox" aria-checked="${state.tasks.has(task.id)}" data-task="${esc(task.id)}">
          <span class="dot"></span>
          <div><strong>${esc(task.id)}</strong>
            <div class="task-meta">T${task.tier} · ${esc(task.mode)}${task.depends_on.length ? ` · richiede ${esc(task.depends_on.join(', '))}` : ''}</div>
          </div>
        </div>`).join('')}</div>
    </section>`).join('');
  $('taskSummary').textContent = `${state.tasks.size} / ${state.catalog.tasks.length} selezionati`;
}

function renderDoctor() {
  if (!state.doctor?.report) return;
  const report = state.doctor.report;
  const system = report.system;
  $('systemStatus').textContent = `${system.platform} ${system.release} · Python ${system.python} · Node ${system.node ? 'OK' : 'mancante'} · npm ${system.npm ? 'OK' : 'mancante'} · bwrap ${system.bubblewrap ? 'OK' : 'mancante'}`;
  $('doctorHarnesses').innerHTML = report.harnesses.map(item => {
    const install = item.install || {};
    const manual = !item.installed && !install.automatic;
    return `<article class="doctor-item ${item.installed ? 'ready' : ''}">
      <span class="dot"></span>
      <div class="details">
        <strong>${esc(item.display_name)}</strong>
        <div class="status">${item.installed ? 'Pronto' : 'Setup richiesto'}</div>
        <div class="task-meta">${esc(item.version || item.path || item.config_hint)}</div>
        ${manual && install.manual_command ? `<code>${esc(install.manual_command)}</code>` : ''}
        ${install.note ? `<div class="task-meta">${esc(install.note)}</div>` : ''}
      </div>
      <div class="doctor-actions">
        ${!item.installed && install.automatic ? `<button data-install="${esc(item.name)}" ${state.busy ? 'disabled' : ''}>Installa</button>` : ''}
        <a class="button-link" href="${esc(install.docs || item.docs)}">Istruzioni</a>
      </div>
    </article>`;
  }).join('');
  const profile = state.doctor.profile || {};
  $('profileModel').value = profile.model || '';
  $('openaiUrl').value = profile.openai_url || '';
  $('anthropicUrl').value = profile.anthropic_url || '';
  if (!$('model').value && profile.model) $('model').value = profile.model;
  $('refreshDoctor').disabled = state.busy;
  $('saveProfile').disabled = state.busy;
  renderHarnesses();
}

async function loadCatalog() {
  const catalog = await state.backend.getCatalog($('suite').value);
  if (!catalog.tasks) return;
  state.catalog = catalog;
  state.harnesses = new Set(catalog.harnesses.map(h => h.id));
  state.tasks = new Set(catalog.tasks.map(t => t.id));
  const supportsSkills = catalog.suite === 'frontier_v4' && (catalog.skill_modes || []).length > 0;
  $('skillMode').disabled = !supportsSkills;
  $('skillAblation').disabled = !supportsSkills;
  if (!supportsSkills) {
    $('skillMode').value = 'no_skill';
    $('skillAblation').checked = false;
  }
  renderHarnesses();
  renderTasks();
}

async function loadDoctor() {
  const value = await state.backend.getDoctor();
  if (!value.report) return;
  state.doctor = value;
  renderDoctor();
}

function activateSelector(selector, attr, set, render, event) {
  const item = event.target.closest(selector);
  if (!item) return;
  const value = item.dataset[attr];
  toggleSet(set, value, !set.has(value));
  render();
}

function progressIdentity(event) {
  return event.skill_mode
    ? `${event.harness} · ${event.skill_mode} · ${event.task_id}`
    : `${event.harness} · ${event.task_id}`;
}

function handleProgress(event) {
  const done = event.completed_units || 0;
  const total = event.total_units || 0;
  $('counter').textContent = `${done} / ${total}`;
  $('progressBar').style.width = total ? `${Math.min(100, done / total * 100)}%` : '0%';
  if (event.type === 'task_started') $('current').textContent = progressIdentity(event);
  if (event.type === 'task_finished') {
    const line = document.createElement('div');
    line.textContent = `${progressIdentity(event)} · ${event.status || (event.success ? 'PASS' : 'FAIL')}`;
    $('events').prepend(line);
  }
  if (event.type === 'run_cancelled') $('current').textContent = 'Run annullata.';
}

function bindUiEvents() {
  document.addEventListener('click', event => {
    const view = event.target.dataset?.view;
    if (view) showView(view);
    if (state.catalog) {
      activateSelector('[data-harness]', 'harness', state.harnesses, renderHarnesses, event);
      activateSelector('[data-task]', 'task', state.tasks, renderTasks, event);
    }
    const hAction = event.target.dataset?.harnessAction;
    if (hAction && state.catalog) {
      state.harnesses = new Set(hAction === 'all' ? state.catalog.harnesses.map(h => h.id) : []);
      renderHarnesses();
    }
    const tAction = event.target.dataset?.taskAction;
    if (tAction && state.catalog) {
      state.tasks = new Set(tAction === 'all' ? state.catalog.tasks.map(t => t.id) : []);
      renderTasks();
    }
    const install = event.target.dataset?.install;
    if (install && !state.busy) {
      $('doctorError').textContent = '';
      void state.backend.installHarness(install).then(value => {
        if (value.report) {
          state.doctor = value;
          renderDoctor();
        }
      });
    }
  });

  document.addEventListener('keydown', event => {
    if (!['Enter', ' '].includes(event.key)) return;
    const item = event.target.closest('[data-harness],[data-task]');
    if (item) {
      event.preventDefault();
      item.click();
    }
  });

  $('suite').addEventListener('change', () => void loadCatalog());
  $('refreshDoctor').addEventListener('click', () => {
    if (!state.busy) void loadDoctor();
  });
  $('saveProfile').addEventListener('click', () => {
    if (state.busy) return;
    $('doctorError').textContent = '';
    const payload = {
      model: $('profileModel').value,
      openai_url: $('openaiUrl').value,
      anthropic_url: $('anthropicUrl').value,
    };
    void state.backend.saveDoctorProfile(payload).then(value => {
      if (value.report) {
        state.doctor = value;
        $('model').value = payload.model.trim();
        renderDoctor();
      }
    });
  });
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
      total_timeout: totalTimeout ? Number(totalTimeout) : null,
      skill_mode: $('skillMode').value,
      skill_ablation: $('skillAblation').checked,
    };
    void state.backend.startRun(payload).then(ok => {
      if (ok) setRunState({ running: true, busy: true });
    });
  });
  $('cancel').addEventListener('click', () => {
    if (!state.running || state.cancelling) return;
    void state.backend.cancelRun().then(ok => {
      if (ok) setRunState({ running: true, busy: true, cancelling: true });
    });
  });
}

async function initialize() {
  bindUiEvents();
  try {
    state.backend = await connectBackend({
      errorOccurred: message => {
        const target = $('doctorView').classList.contains('hidden') ? $('error') : $('doctorError');
        target.textContent = message;
      },
      doctorChanged: value => {
        if (value.report) {
          state.doctor = value;
          renderDoctor();
        }
      },
      runStateChanged: setRunState,
      progressChanged: handleProgress,
      runFinished: result => {
        $('current').textContent = result.cancelled ? 'Run annullata.' : 'Run completata.';
      },
    });
    await Promise.all([loadCatalog(), loadDoctor()]);
    document.documentElement.dataset.appReady = 'true';
  } catch (error) {
    $('error').textContent = error instanceof Error ? error.message : String(error);
    document.documentElement.dataset.appReady = 'false';
  }
}

void initialize();