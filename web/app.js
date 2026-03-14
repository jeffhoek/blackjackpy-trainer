const term = new Terminal({
  cursorBlink: true,
  fontFamily: 'Menlo, Monaco, "Courier New", monospace',
  fontSize: 16,
  theme: {
    background: '#000000',
    foreground: '#ffffff',
    cursor: '#ffffff',
  },
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.open(document.getElementById('terminal'));
term.focus();

const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${proto}//${location.host}/ws`);

function sendSize() {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send('\x01' + term.cols + ',' + term.rows);
  }
}

ws.addEventListener('open', () => {
  // Send terminal input to server
  term.onData((data) => { ws.send(data); });
  // Render server output in terminal
  ws.addEventListener('message', (ev) => { term.write(ev.data); });
  resizeToViewport();
  sendSize();
  term.focus();
});

ws.addEventListener('close', () => {
  term.writeln('\r\n\r\n[Connection closed. Refresh to start a new session.]');
});

ws.addEventListener('error', () => {
  term.writeln('\r\n[WebSocket error — is the server running?]');
});

function resizeToViewport() {
  if (window.visualViewport) {
    const vv = window.visualViewport;
    const el = document.getElementById('terminal');
    el.style.width  = vv.width  + 'px';
    el.style.height = vv.height + 'px';
    el.style.top    = vv.offsetTop  + 'px';
    el.style.left   = vv.offsetLeft + 'px';
  }
  fitAddon.fit();
  sendSize();
}

if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', resizeToViewport);
  window.visualViewport.addEventListener('scroll', resizeToViewport);
}
window.addEventListener('resize', resizeToViewport);
