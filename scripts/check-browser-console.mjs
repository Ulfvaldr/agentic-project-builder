import { createHash, randomBytes } from 'node:crypto';
import { mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import http from 'node:http';
import net from 'node:net';

async function main() {
  const url = process.env.URL ?? 'http://127.0.0.1:4173/';
  const chromePath = process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const port = Number(process.env.CDP_PORT ?? 9333);
  const userDataDir = join(tmpdir(), `etf-console-check-${process.pid}`);
  await mkdir(userDataDir, { recursive: true });

  const chrome = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    'about:blank'
  ], { stdio: ['ignore', 'pipe', 'pipe'] });

  try {
    await waitForCdp(port);
    const target = await requestJson({ method: 'PUT', path: `/json/new?${encodeURIComponent('about:blank')}`, port });
    const cdp = await CdpClient.connect(target.webSocketDebuggerUrl);
    const failures = [];

    cdp.onEvent = (event) => {
      if (event.method === 'Log.entryAdded' && ['error', 'warning'].includes(event.params?.entry?.level)) {
        failures.push(`Log.${event.params.entry.level}: ${event.params.entry.text}`);
      }
      if (event.method === 'Runtime.exceptionThrown') {
        failures.push(`Runtime.exceptionThrown: ${event.params?.exceptionDetails?.text ?? 'exception'}`);
      }
      if (event.method === 'Network.responseReceived' && event.params?.response?.status >= 400) {
        failures.push(`HTTP ${event.params.response.status}: ${event.params.response.url}`);
      }
      if (event.method === 'Network.loadingFailed') {
        failures.push(`Network.loadingFailed: ${event.params?.errorText ?? 'failed'} ${event.params?.requestId ?? ''}`);
      }
    };

    await cdp.send('Log.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Page.enable');
    await cdp.send('Network.enable');
    await navigateAndWait(cdp, url);
    await sleep(500);
    await navigateAndWait(cdp, url);
    await sleep(500);
    await cdp.close();

    if (failures.length) {
      console.error(failures.join('\n'));
      process.exitCode = 1;
    } else {
      console.log(`Clean browser console/log check passed for initial load and reload: ${url}`);
    }
  } finally {
    chrome.kill();
    if (chrome.exitCode === null) await Promise.race([new Promise((resolve) => chrome.once('exit', resolve)), sleep(1000)]);
    await rm(userDataDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  }
}

async function navigateAndWait(cdp, targetUrl) {
  const loaded = cdp.waitFor('Page.loadEventFired', 5000);
  await cdp.send('Page.navigate', { url: targetUrl });
  await loaded;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForCdp(port) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try {
      await requestJson({ method: 'GET', path: '/json/version', port });
      return;
    } catch {
      await sleep(100);
    }
  }
  throw new Error(`Chrome CDP did not start on port ${port}`);
}

function requestJson({ method, path, port }) {
  return new Promise((resolve, reject) => {
    const req = http.request({ method, hostname: '127.0.0.1', port, path }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) reject(new Error(`${method} ${path} returned ${res.statusCode}: ${body}`));
        else resolve(JSON.parse(body));
      });
    });
    req.on('error', reject);
    req.end();
  });
}

class CdpClient {
  static async connect(wsUrl) {
    const parsed = new URL(wsUrl);
    const socket = net.createConnection({ host: parsed.hostname, port: Number(parsed.port) });
    await new Promise((resolve, reject) => {
      socket.once('connect', resolve);
      socket.once('error', reject);
    });
    const key = randomBytes(16).toString('base64');
    socket.write([
      `GET ${parsed.pathname}${parsed.search} HTTP/1.1`,
      `Host: ${parsed.host}`,
      'Upgrade: websocket',
      'Connection: Upgrade',
      `Sec-WebSocket-Key: ${key}`,
      'Sec-WebSocket-Version: 13',
      '',
      ''
    ].join('\r\n'));
    const client = new CdpClient(socket);
    await client.handshake(key);
    socket.on('data', (chunk) => client.read(chunk));
    return client;
  }

  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.waiters = new Map();
    this.buffer = Buffer.alloc(0);
    this.onEvent = () => {};
  }

  handshake(key) {
    return new Promise((resolve, reject) => {
      let header = Buffer.alloc(0);
      const onData = (chunk) => {
        header = Buffer.concat([header, chunk]);
        const marker = header.indexOf('\r\n\r\n');
        if (marker === -1) return;
        this.socket.off('data', onData);
        const text = header.subarray(0, marker).toString('utf8');
        const accept = createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
        if (!text.includes(' 101 ') || !text.toLowerCase().includes(`sec-websocket-accept: ${accept}`.toLowerCase())) reject(new Error(`Bad websocket handshake: ${text}`));
        else {
          const rest = header.subarray(marker + 4);
          if (rest.length) this.read(rest);
          resolve();
        }
      };
      this.socket.on('data', onData);
      this.socket.once('error', reject);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    this.socket.write(encodeFrame(payload));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  waitFor(method, timeoutMs) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`Timed out waiting for ${method}`)), timeoutMs);
      const list = this.waiters.get(method) ?? [];
      list.push((event) => {
        clearTimeout(timeout);
        resolve(event);
      });
      this.waiters.set(method, list);
    });
  }

  read(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (this.buffer.length >= 2) {
      const second = this.buffer[1];
      let length = second & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (this.buffer.length < 4) return;
        length = this.buffer.readUInt16BE(2);
        offset = 4;
      } else if (length === 127) {
        if (this.buffer.length < 10) return;
        length = Number(this.buffer.readBigUInt64BE(2));
        offset = 10;
      }
      const masked = Boolean(second & 0x80);
      const maskBytes = masked ? 4 : 0;
      if (this.buffer.length < offset + maskBytes + length) return;
      let payload = this.buffer.subarray(offset + maskBytes, offset + maskBytes + length);
      if (masked) {
        const mask = this.buffer.subarray(offset, offset + 4);
        payload = Buffer.from(payload.map((byte, index) => byte ^ mask[index % 4]));
      }
      this.buffer = this.buffer.subarray(offset + maskBytes + length);
      const message = JSON.parse(payload.toString('utf8'));
      this.handle(message);
    }
  }

  handle(message) {
    if (message.id && this.pending.has(message.id)) {
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
      return;
    }
    if (message.method) {
      this.onEvent(message);
      const waiters = this.waiters.get(message.method);
      if (waiters?.length) waiters.shift()(message);
    }
  }

  close() {
    this.socket.end();
  }
}

function encodeFrame(text) {
  const payload = Buffer.from(text);
  const header = [];
  header.push(0x81);
  if (payload.length < 126) header.push(0x80 | payload.length);
  else if (payload.length < 65536) header.push(0x80 | 126, (payload.length >> 8) & 0xff, payload.length & 0xff);
  else throw new Error('Payload too large');
  const mask = randomBytes(4);
  const masked = Buffer.from(payload.map((byte, index) => byte ^ mask[index % 4]));
  return Buffer.concat([Buffer.from(header), mask, masked]);
}

await main();
