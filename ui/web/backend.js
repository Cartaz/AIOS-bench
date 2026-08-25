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
    const connect = (signal, handler) => {
      if (typeof handler === 'function') signal.connect(handler);
    };
    connect(backend.errorOccurred, handlers.errorOccurred);
    connect(backend.doctorChanged, raw => handlers.doctorChanged?.(parseObject(raw)));
    connect(backend.runStateChanged, raw => handlers.runStateChanged?.(parseObject(raw)));
    connect(backend.progressChanged, raw => handlers.progressChanged?.(parseObject(raw)));
    connect(backend.runFinished, raw => handlers.runFinished?.(parseObject(raw)));
  }

  async getCatalog(suite) {
    const raw = await callWithResult(done => this.backend.getCatalog(suite, done));
    return parseObject(raw);
  }

  async getDoctor() {
    const raw = await callWithResult(done => this.backend.getDoctor(done));
    return parseObject(raw);
  }

  saveDoctorProfile(profile) {
    return callWithResult(done => this.backend.saveDoctorProfile(JSON.stringify(profile), done));
  }

  installHarness(name) {
    return callWithResult(done => this.backend.installHarness(name, done));
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
