function callWithResult(invoker) {
  return new Promise(resolve => invoker(resolve));
}

function parseObject(raw) {
  try {
    const value = JSON.parse(raw || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

export class BackendClient {
  constructor(backend, handlers = {}) {
    this.backend = backend;
    this.doctorWaiters = [];
    this.modelWaiters = [];
    const connect = (signal, handler) => {
      if (typeof handler === 'function') signal.connect(handler);
    };
    connect(backend.errorOccurred, handlers.errorOccurred);
    backend.doctorChanged.connect(raw => {
      const value = parseObject(raw);
      handlers.doctorChanged?.(value);
      const waiters = this.doctorWaiters.splice(0);
      waiters.forEach(resolve => resolve(value));
    });
    backend.modelsDiscovered.connect(raw => {
      const value = parseObject(raw);
      handlers.modelsDiscovered?.(value);
      const waiters = this.modelWaiters.splice(0);
      waiters.forEach(resolve => resolve(value));
    });
    connect(backend.runStateChanged, raw => handlers.runStateChanged?.(parseObject(raw)));
    connect(backend.progressChanged, raw => handlers.progressChanged?.(parseObject(raw)));
    connect(backend.runFinished, raw => handlers.runFinished?.(parseObject(raw)));
  }

  async getCatalog(suite) {
    const raw = await callWithResult(done => this.backend.getCatalog(suite, done));
    return parseObject(raw);
  }

  _signalAction(waiters, invoker) {
    return new Promise(resolve => {
      const waiter = value => resolve(value);
      waiters.push(waiter);
      invoker(ok => {
        if (ok) return;
        const index = waiters.indexOf(waiter);
        if (index >= 0) waiters.splice(index, 1);
        resolve({});
      });
    });
  }

  _doctorAction(invoker) {
    return this._signalAction(this.doctorWaiters, invoker);
  }

  getDoctor() {
    return this._doctorAction(done => this.backend.getDoctor(done));
  }

  discoverModels(openaiUrl) {
    return this._signalAction(
      this.modelWaiters,
      done => this.backend.discoverModels(openaiUrl, done),
    );
  }

  testAndConfigure(profile) {
    return this._doctorAction(
      done => this.backend.testAndConfigure(JSON.stringify(profile), done),
    );
  }

  saveDoctorProfile(profile) {
    return this._doctorAction(done => this.backend.saveDoctorProfile(JSON.stringify(profile), done));
  }

  installHarness(name) {
    return this._doctorAction(done => this.backend.installHarness(name, done));
  }

  startRun(request) {
    return callWithResult(done => this.backend.startRun(JSON.stringify(request), done));
  }

  cancelRun() {
    return callWithResult(done => this.backend.cancelRun(done));
  }
}

export function connectBackend(handlers = {}) {
  return new Promise((resolve, reject) => {
    if (!globalThis.qt?.webChannelTransport || typeof globalThis.QWebChannel !== 'function') {
      reject(new Error('QWebChannel transport unavailable'));
      return;
    }
    new globalThis.QWebChannel(globalThis.qt.webChannelTransport, channel => {
      const backend = channel.objects.backend;
      if (!backend) {
        reject(new Error('QWebChannel backend object unavailable'));
        return;
      }
      resolve(new BackendClient(backend, handlers));
    });
  });
}
