/**
 * chat.js – AI Chat interface for SOC Insight
 */

const Chat = (() => {
  const BASE = '';

  function _addMessage(role, content, expr = null) {
    const container = document.getElementById('chat-messages');
    const wrapper = document.createElement('div');
    wrapper.className = `chat-msg ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'chat-avatar';
    avatar.textContent = role === 'user' ? '🧑' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    if (typeof content === 'string') {
      bubble.innerHTML = content;
    } else {
      // It's a result object
      bubble.appendChild(_renderResult(content, expr));
    }

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
    return bubble;
  }

  function _thinking() {
    const container = document.getElementById('chat-messages');
    const wrapper = document.createElement('div');
    wrapper.className = 'chat-msg bot';
    wrapper.id = 'thinking-msg';
    wrapper.innerHTML = `
      <div class="chat-avatar">🤖</div>
      <div class="chat-bubble">
        <div class="thinking">
          <span></span><span></span><span></span>
        </div>
      </div>`;
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
  }

  function _removeThinking() {
    const el = document.getElementById('thinking-msg');
    if (el) el.remove();
  }

  function _renderResult(result, expr) {
    const div = document.createElement('div');

    if (!result) {
      div.innerHTML = '<em style="color:var(--text-muted)">No data returned.</em>';
      return div;
    }

    if (result.type === 'scalar') {
      const isNum = typeof result.value === 'number';
      div.innerHTML = `<strong>Result:</strong> <span style="color:var(--cyan);font-size:18px;font-weight:700">${
        isNum ? result.value.toLocaleString() : result.value
      }</span>`;
    }

    else if (result.type === 'series') {
      let html = '<table><thead><tr>';
      result.columns.forEach(c => { html += `<th>${c}</th>`; });
      html += '</tr></thead><tbody>';
      result.rows.slice(0, 20).forEach(row => {
        html += '<tr>' + row.map(v => `<td>${v}</td>`).join('') + '</tr>';
      });
      html += '</tbody></table>';
      if (result.rows.length > 20) {
        html += `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">… showing top 20 of ${result.rows.length}</div>`;
      }
      div.innerHTML = html;
    }

    else if (result.type === 'dataframe') {
      const totalBadge = `<div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">${result.total} rows matched</div>`;
      let html = totalBadge + '<table><thead><tr>';
      result.columns.forEach(c => { html += `<th>${c}</th>`; });
      html += '</tr></thead><tbody>';
      result.rows.slice(0, 30).forEach(row => {
        html += '<tr>' + result.columns.map(c => {
          let v = row[c] || '';
          if (c === 'Severity') v = `<span class="badge badge-${v.toLowerCase()}">${v}</span>`;
          return `<td>${v}</td>`;
        }).join('') + '</tr>';
      });
      html += '</tbody></table>';
      if (result.total > 30) {
        html += `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">… showing 30 of ${result.total} rows</div>`;
      }
      div.innerHTML = html;
    }

    // Show the pandas expression used
    if (expr) {
      const code = document.createElement('div');
      code.className = 'expr-code';
      code.textContent = '🔍 ' + expr;
      div.appendChild(code);
    }

    return div;
  }

  async function send(question, token) {
    if (!question.trim()) return;

    _addMessage('user', question);
    _thinking();

    try {
      const resp = await fetch(`${BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, token }),
      });

      _removeThinking();

      const data = await resp.json();

      if (!data.success) {
        _addMessage('bot',
          `<span style="color:var(--red)">⚠ ${data.error}</span><br>
           <span style="font-size:12px;color:var(--text-muted)">Make sure Ollama is running: <code>ollama serve</code></span>`
        );
        return;
      }

      _addMessage('bot', data.result, data.pandas_expr);
    } catch (e) {
      _removeThinking();
      _addMessage('bot', `<span style="color:var(--red)">⚠ Network error: ${e.message}</span>`);
    }
  }

  function init(getToken) {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');

    function doSend() {
      const q = input.value.trim();
      if (!q) return;
      const token = getToken();
      if (!token) {
        App.toast('Please upload an Excel file first', 'error');
        return;
      }
      input.value = '';
      send(q, token);
    }

    sendBtn.addEventListener('click', doSend);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });

    // Suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        input.value = chip.dataset.q;
        doSend();
      });
    });
  }

  return { init };
})();
