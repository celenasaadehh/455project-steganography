/* Member 4: Learn walkthroughs + History tab for Stego Mail. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { maximumFractionDigits: d });

  async function post(url, form) {
    try {
      const res = await fetch(url, { method: 'POST', body: form });
      return await res.json();
    } catch { return { ok: false, error: 'Cannot reach the server.' }; }
  }
  function setStatus(el, text, kind = 'error') { el.className = `status ${text ? kind : ''}`; el.textContent = text || ''; }
  function busy(btn, on) {
    if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Working…'; }
    else { btn.disabled = false; btn.innerHTML = btn.dataset.label; }
  }
  function toast(text) {
    const t = $('[data-toast]'); if (!t) return;
    t.textContent = text; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, 2400);
  }

  /* ---------- shared pieces ---------- */
  function bitsHtml(parts) {
    let out = '', n = 0;
    for (const p of parts) for (const b of p.bits) {
      out += `<span class="${p.cls}">${b}</span>`;
      if (++n % 8 === 0) out += '<span class="gap"></span>';
    }
    return `<div class="m4-bits">${out}</div>`;
  }
  function charTable(rows) {
    return `<div class="m4-table-wrap"><table class="m4-table"><thead><tr><th>Character</th><th>Unicode</th><th>Byte value(s)</th><th>Bits</th></tr></thead><tbody>${
      rows.map(r => `<tr><td style="font-size:16px">${r.char === ' ' ? '<span class="m4-muted">(space)</span>' : esc(r.char)}</td><td class="m4-mono">${r.code}</td><td class="m4-mono">${r.bytes.join(', ')}</td><td class="m4-mono">${r.bits.join(' ')}</td></tr>`).join('')
    }</tbody></table></div>`;
  }
  const stat = (v, k) => `<div class="m4-stat"><b>${v}</b><span>${k}</span></div>`;

  function stepper(root, steps) {
    let cur = 0; const seen = new Set();
    function draw() {
      seen.add(cur);
      root.innerHTML = `<div class="m4-dots">${steps.map((s, i) => `<button class="m4-dot ${i === cur ? 'active' : seen.has(i) ? 'done' : ''}" data-i="${i}">${i + 1}. ${esc(s.title)}</button>`).join('')}</div>
        <h3 class="m4-stephead">Step ${cur + 1} of ${steps.length}: ${esc(steps[cur].title)}</h3>
        <div class="m4-stepbody"></div>
        <div class="m4-nav"><button class="btn ghost" data-prev ${cur === 0 ? 'disabled' : ''}>← Back</button><button class="btn primary" data-next ${cur === steps.length - 1 ? 'disabled' : ''}>Next →</button></div>`;
      steps[cur].render($('.m4-stepbody', root));
      $$('.m4-dot', root).forEach(b => b.onclick = () => { cur = +b.dataset.i; draw(); });
      $('[data-prev]', root).onclick = () => { if (cur > 0) { cur--; draw(); } };
      $('[data-next]', root).onclick = () => { if (cur < steps.length - 1) { cur++; draw(); root.scrollIntoView({ behavior: 'smooth', block: 'start' }); } };
    }
    root.hidden = false; draw();
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ---------- tabs ---------- */
  $$('[data-m4-tab]').forEach(t => t.addEventListener('click', () => {
    $$('[data-m4-tab]').forEach(x => x.classList.toggle('active', x === t));
    $$('[data-m4-panel]').forEach(p => { p.hidden = p.dataset.m4Panel !== t.dataset.m4Tab; });
  }));
  $$('.m4-toc a').forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault(); $(a.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));

  /* ---------- picture picker (Member 2's gallery) ---------- */
  const picker = { gallery: null, file: null, loaded: false };
  async function loadPicker() {
    if (picker.loaded) return;
    const box = $('[data-m4-picker]'); if (!box) return;
    let data;
    try { data = await (await fetch('/api/gallery')).json(); } catch { data = null; }
    if (!data?.ok) { box.innerHTML = '<span class="m4-muted">Could not load the gallery. You can still upload a picture.</span>'; return; }
    picker.loaded = true;
    box.innerHTML = data.items.map(g => `<button type="button" class="m4-pick" data-id="${esc(g.id)}" title="${esc(g.name)}"><img src="${esc(g.thumb_url)}" alt="" loading="lazy">${esc(g.name)}</button>`).join('');
    $$('.m4-pick', box).forEach(b => b.onclick = () => choose(b.dataset.id));
    if (data.items.length) choose(data.items[0].id);
  }
  function choose(id) {
    picker.gallery = id; picker.file = null;
    const up = $('[data-m4-upload]'); if (up) up.value = '';
    $$('.m4-pick').forEach(b => b.classList.toggle('active', b.dataset.id === id));
  }
  $('[data-m4-upload]')?.addEventListener('change', (e) => {
    const f = e.target.files[0]; if (!f) return;
    picker.file = f; picker.gallery = null;
    $$('.m4-pick').forEach(b => b.classList.remove('active'));
  });

  /* ================= PICTURE WALKTHROUGH ================= */
  function groupCard(g, i) {
    const ones = g.values.map((v, k) => (v.before & 1) ? k + 1 : null).filter(Boolean);
    const rows = g.values.map((v, k) => {
      const pos = k + 1, flip = pos === g.flip;
      const b = v.before.toString(2).padStart(8, '0'), a = v.after.toString(2).padStart(8, '0');
      return `<tr><td>${pos}</td><td>${v.channel} (${v.x},${v.y})</td><td>${v.before} = ${b.slice(0, 7)}<span class="lsb">${b[7]}</span></td><td class="${flip ? 'flip' : ''}">${v.after} = ${a.slice(0, 7)}<span class="lsb">${a[7]}</span></td></tr>`;
    }).join('');
    const result = g.flip
      ? `They give <b>${g.syndrome_before}</b> but we need <b>${g.target}</b>. ${g.syndrome_before} XOR ${g.target} = ${g.flip.toString(2).padStart(3, '0')} = <b>${g.flip}</b>, so only value <b>#${g.flip}</b> changes by 1.`
      : `They already give <b>${g.target}</b>: <b>nothing changes</b>.`;
    return `<div class="m4-group">
      <div><span class="tag ${g.part}">${g.part === 'header' ? 'header' : 'message'}</span> Group ${i + 1} hides the bits <b class="m4-mono">${g.target}</b></div>
      <table><thead><tr><th>#</th><th>Colour (x,y)</th><th>Before</th><th>After</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="result m4-muted">Values whose last bit is 1: ${ones.length ? ones.map(p => '#' + p).join(', ') : 'none'} → XOR = <b>${g.syndrome_before}</b>.<br>${result}</p>
    </div>`;
  }

  function imageSteps(t) {
    const s = t.stats;
    const hdrBits = t.header.bits, bodyBits = t.body.bits;
    const psnr = s.psnr == null ? '∞ (identical)' : fmt(s.psnr, 1) + ' dB';
    return [
      { title: 'Message → bits', render: el => {
        el.innerHTML = `<p>Computers store text as numbers. Each character becomes one or more <b>bytes</b> (UTF-8), and each byte is <b>8 bits</b>.</p>${charTable(t.table)}
          <p>Your message is <b>${t.message_bytes} bytes = ${t.message_bytes * 8} bits</b>.</p>`;
      } },
      { title: 'Build what gets hidden', render: el => {
        el.innerHTML = `<p>The app hides more than your message. First comes a <b>${t.header.bytes}-byte header</b>, read out of this exact picture:</p>
          <div class="m4-table-wrap"><table class="m4-table"><thead><tr><th>Field</th><th>Size</th><th>Value in your picture</th><th>Why</th></tr></thead><tbody>
          ${t.header.fields.map(f => `<tr><td><b>${esc(f.name)}</b></td><td>${f.size} B</td><td class="m4-mono">${esc(f.value)}</td><td class="m4-muted">${esc(f.why)}</td></tr>`).join('')}</tbody></table></div>
          <p>Then the message itself (${t.body.bytes} bytes):</p>
          ${t.encrypted
            ? `<div class="m4-note warn"><b>Locked.</b> The message was encrypted with your password, so what gets hidden looks like random noise:<div class="m4-hex">${esc(t.body.hex)}…</div>That is ${t.message_bytes} bytes of message + 16 bytes of authentication tag.</div>`
            : `<div class="m4-note">Not locked: your message bytes are hidden as they are, followed by a 4-byte CRC check that detects damage. <b>Anyone with our app could reveal it.</b></div>`}
          <div class="m4-legend"><span><i style="background:#a21caf"></i>header bits</span><span><i style="background:${t.encrypted ? '#b45309' : '#15803d'}"></i>${t.encrypted ? 'encrypted message' : 'message + CRC'} bits</span></div>
          ${bitsHtml([{ bits: hdrBits, cls: 'h' }, { bits: bodyBits.slice(0, 160), cls: t.encrypted ? 'e' : 'm' }])}
          <p class="m4-muted">Total: ${fmt((t.header.bytes + t.body.bytes) * 8)} bits to hide${bodyBits.length > 160 ? ' (only part shown)' : ''}.</p>`;
      } },
      { title: 'Find the busy areas', render: el => {
        el.innerHTML = `<p>The picture (${t.width}×${t.height}) is cut into <b>${fmt(s.tiles_total)}</b> tiles of 8×8 pixels. Each tile is scored by how much neighbouring pixels differ. Only the <b>busier half (${fmt(s.tiles_used)} tiles)</b> may hold data; smooth areas are left completely alone.</p>
          <div class="m4-pics"><figure><img src="${t.images.cover}" alt=""><figcaption>Your picture</figcaption></figure>
          <figure><img class="px" src="${t.images.texture}" alt=""><figcaption><b style="color:#4682ff">Blue</b> = busy areas that can hold data</figcaption></figure></div>
          <p>Their colour values are split into <b>groups of 7</b>. This picture has ${fmt(s.groups_total)} groups, enough for <b>${fmt(s.capacity_bytes)} bytes</b> ${t.encrypted ? 'of locked message' : 'of message'}. Your message needs only <b>${fmt(s.groups_used)}</b> of them.</p>`;
      } },
      { title: 'Hide 3 bits in each group of 7', render: el => {
        el.innerHTML = `<p>Here are the <b>real groups</b> from your picture. Number the 7 values 1–7, take the numbers of the values whose last bit is <b>1</b>, and XOR them together. The 3-bit result is what the group "says". To make it say our bits, change <b>at most one</b> value by 1.</p>
          <div class="m4-groups">${t.groups.map(groupCard).join('')}</div>
          <p class="m4-muted">The header groups always come first, in a fixed public order. The message groups are picked in a random order from the salt${t.encrypted ? ' and your password' : ''}, which is why the positions jump around.</p>`;
      } },
      { title: 'Compare the pictures', render: el => {
        el.innerHTML = `<p>Can you see a difference? The map on the right marks every pixel that changed in <b style="color:#ff00c8">magenta</b>.</p>
          <div class="m4-pics"><figure><img src="${t.images.cover}" alt=""><figcaption>Before</figcaption></figure>
          <figure><img src="${t.images.stego}" alt=""><figcaption>After (message inside)</figcaption></figure>
          <figure><img class="px" src="${t.images.diff}" alt=""><figcaption>Changed pixels (dots made bigger so you can see them)</figcaption></figure></div>
          <div class="m4-note">The changes are <b>scattered</b> over the busy areas and not packed at the top, as they would be with plain LSB. That makes them much harder for detection tools to find.</div>`;
      } },
      { title: 'Measure the result', render: el => {
        const plain = Math.max(s.plain_lsb_changes, 1), ours = s.channels_changed;
        el.innerHTML = `<div class="m4-stats">
            ${stat(fmt(ours), 'colour values changed (each by exactly 1)')}
            ${stat(fmt(s.pixels_changed) + ' / ' + fmt(s.pixels_total), 'pixels touched')}
            ${stat(psnr, 'PSNR (picture quality)')}
            ${stat(fmt(s.capacity_bytes), 'bytes this picture could hold')}
          </div>
          <p><b>Fewer changes than plain LSB.</b> Hiding the same ${fmt(s.groups_used * 3)} bits with plain LSB would change about <b>${fmt(plain)}</b> values (half of them, on average). Matrix embedding changed <b>${fmt(ours)}</b>:</p>
          <div class="m4-compare-bars">
            <div>Plain LSB ≈ ${fmt(plain)}<div class="m4-bar"><i style="width:100%"></i></div></div>
            <div>Our app = ${fmt(ours)}<div class="m4-bar"><i style="width:${Math.max(2, ours / plain * 100)}%"></i></div></div>
          </div>
          <p><b>PSNR</b> (Peak Signal-to-Noise Ratio) measures how close the new picture is to the original. Above 40 dB the human eye can't see any difference. Ours: <b>${psnr}</b>.</p>
          <p class="m4-muted">A high PSNR means invisible to people, not invisible to detection software.</p>`;
      } },
      { title: 'Reveal the message', render: el => {
        el.innerHTML = `<p>The recipient's app reverses everything, using only the picture${t.encrypted ? ' and the password' : ''}:</p>
          <ol class="m4-ol"><li>Rebuild the busy-area map (it ignores last bits, so it's identical).</li>
          <li>Read the header groups in the public order, XOR each group → ${t.header.bytes} bytes. Check the tag <code>ILAB</code> and the CRC.</li>
          <li>Use the salt${t.encrypted ? ' + password' : ''} to find the message groups in the same random order and read them.</li>
          <li>${t.encrypted ? 'Decrypt with AES-256-GCM. A wrong password breaks the seal and is refused.' : 'Check the CRC to make sure nothing was damaged.'}</li></ol>
          <div class="m4-secret">${esc(t.recovered)}</div>
          ${t.ok ? '<div class="m4-note ok">✓ Recovered exactly, by Member 1\'s real <code>extract()</code>.</div>' : '<div class="status error">The recovered text does not match.</div>'}
          <div class="m4-row"><a class="btn secondary" download="stego-learn.png" href="data:image/png;base64,${t.png_base64}">Download this picture</a>
          <span class="m4-muted">Never resize, crop or convert it, or the message is lost.</span></div>`;
      } },
    ];
  }

  $('[data-m4-img-go]')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget, st = $('[data-m4-img-status]');
    setStatus(st, '');
    const msg = $('[data-m4-img-msg]').value;
    if (!msg.trim()) return setStatus(st, 'Type a secret message first.');
    if (!picker.gallery && !picker.file) return setStatus(st, 'Pick a picture first.');
    const f = new FormData();
    f.append('message', msg);
    const pw = $('[data-m4-img-pw]').value; if (pw) f.append('password', pw);
    if (picker.file) f.append('image', picker.file); else f.append('gallery', picker.gallery);
    busy(btn, true);
    const res = await post('/api/learn/image', f);
    busy(btn, false);
    if (!res.ok) return setStatus(st, res.error || 'Something went wrong.');
    stepper($('[data-m4-img-walk]'), imageSteps(res.trace));
  });

  /* ================= TEXT WALKTHROUGH ================= */
  const ZW = { '​': ['00', 'z0'], '‌': ['01', 'z1'], '‍': ['10', 'z2'], '⁠': ['11', 'z3'] };
  const reveal = (s) => [...s].map(c => ZW[c] ? `<span class="m4-zw ${ZW[c][1]}">${ZW[c][0]}</span>` : esc(c)).join('');
  function revealLimited(s, limit = 260) {
    const hidden = [...s].filter(c => ZW[c]).length;
    if (hidden <= limit) return reveal(s);
    let n = 0, out = '';
    for (const c of s) {
      if (ZW[c]) { if (n++ < limit) out += reveal(c); else if (n === limit + 1) out += `<span class="m4-muted"> … ${hidden - limit} more invisible characters … </span>`; }
      else out += esc(c);
    }
    return out;
  }

  function checkBox(el) {
    el.insertAdjacentHTML('beforeend', `<h3 style="margin-top:22px">Try it yourself</h3>
      <p class="m4-muted">Copy the text from step 4, paste it into a chat or a note, then copy it back here.</p>
      <label class="m4-label">Paste text<textarea data-m4-paste placeholder="Paste here…"></textarea></label>
      <label class="m4-label">Password (if it was locked)<input type="text" data-m4-paste-pw autocomplete="off"></label>
      <button class="btn secondary" data-m4-check>Look for a hidden message</button><div data-m4-check-out></div>`);
    $('[data-m4-check]', el).onclick = async () => {
      const f = new FormData(); f.append('text', $('[data-m4-paste]', el).value);
      const pw = $('[data-m4-paste-pw]', el).value; if (pw) f.append('password', pw);
      const res = await post('/api/learn/check-text', f), out = $('[data-m4-check-out]', el);
      if (!res.ok) { out.innerHTML = `<div class="status error">${esc(res.error)}</div>`; return; }
      const r = res.result;
      out.innerHTML = r.found
        ? `<p class="m4-muted" style="margin-top:10px">Found ${r.hidden_chars} invisible characters. Hidden message:</p><div class="m4-secret">${esc(r.message)}</div>`
        : `<div class="status error" style="margin-top:10px">${esc(r.reason)}${r.hidden_chars ? ` (${r.hidden_chars} invisible characters found)` : ''}</div>`;
    };
  }

  function textSteps(t) {
    const hidden = [...t.stego].filter(c => ZW[c]).join('');
    return [
      { title: 'Message → bits', render: el => {
        el.innerHTML = `<p>Just like with pictures, the secret is first turned into bytes and bits.</p>${charTable(t.table)}
          ${bitsHtml([{ bits: t.message_bits, cls: 'm' }])}`;
      } },
      { title: 'Build what gets hidden', render: el => {
        el.innerHTML = `<p>The app wraps your message in a small package of <b>${t.payload_bytes} bytes</b>. Each byte is cut into four 2-bit pairs:</p>
          <div class="m4-table-wrap"><table class="m4-table"><thead><tr><th>#</th><th>Part</th><th>Byte</th><th>Bits</th><th>Pairs</th></tr></thead><tbody>
          ${t.payload_rows.map(r => `<tr><td>${r.index}</td><td>${esc(r.field)}</td><td class="m4-mono">${r.value}</td><td class="m4-mono">${r.bits}</td><td class="m4-mono">${r.pairs.join(' ')}</td></tr>`).join('')}
          </tbody></table></div>${t.payload_bytes > t.payload_rows.length ? `<p class="m4-muted">Showing the first ${t.payload_rows.length} of ${t.payload_bytes} bytes.</p>` : ''}
          ${t.locked ? '<div class="m4-note warn"><b>Locked:</b> the salt, nonce and encrypted bytes look random, and the 16-byte tag at the end detects a wrong password or any edit.</div>'
                     : '<div class="m4-note">Not locked: after the 4-byte header (<code>ZW</code>, version, lock flag) come your message bytes and a 4-byte CRC check.</div>'}`;
      } },
      { title: 'Bits → invisible characters', render: el => {
        el.innerHTML = `<p>Each 2-bit pair becomes one invisible character:</p>
          <div class="m4-symbols">${t.symbol_table.map((s, i) => `<div><span class="m4-zw z${i}">${s.bits}</span> ${s.code} ${esc(s.name)}</div>`).join('')}</div>
          <p>Your ${t.payload_bytes} bytes become <b>${t.symbols} invisible characters</b> (shown here as coloured boxes; on a real screen you see nothing):</p>
          <div class="m4-textbox">${revealLimited(hidden)}</div>`;
      } },
      { title: 'Hide them in the sentence', render: el => {
        el.innerHTML = `<p>They are inserted right after the first word.</p>
          <div class="m4-two"><div><h3>What everyone sees</h3><div class="m4-textbox">${esc(t.stego)}</div></div>
          <div><h3>What is really there</h3><div class="m4-textbox">${revealLimited(t.stego)}</div></div></div>
          <div class="m4-stats">${stat(fmt(t.stats.cover_chars), 'characters you typed')}${stat(fmt(t.stats.stego_chars), 'characters actually sent')}${stat('0', 'visible difference')}</div>
          <div class="m4-note warn">Identical on screen, but <b>${fmt(t.stats.hidden_chars)} characters longer</b>. A character counter would notice.</div>
          <div class="m4-row"><button class="btn secondary" data-m4-copy>Copy the text with the hidden message</button></div>`;
        $('[data-m4-copy]', el).onclick = () => navigator.clipboard.writeText(t.stego).then(() => toast('Copied. The secret is inside.'), () => toast('Your browser blocked copying.'));
      } },
      { title: 'Reveal the message', render: el => {
        el.innerHTML = `<ol class="m4-ol"><li>Keep only the four invisible characters and turn each back into 2 bits.</li>
          <li>Join every 4 characters into a byte, check the <code>ZW</code> tag.</li>
          <li>${t.locked ? 'Decrypt with the password (AES-256-GCM).' : 'Check the CRC.'}</li></ol>
          <div class="m4-secret">${esc(t.recovered)}</div>
          ${t.ok ? '<div class="m4-note ok">✓ Recovered exactly, by Member 2\'s real <code>reveal()</code>.</div>' : ''}`;
        checkBox(el);
      } },
    ];
  }

  $('[data-m4-txt-go]')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget, st = $('[data-m4-txt-status]');
    setStatus(st, '');
    const f = new FormData();
    f.append('cover', $('[data-m4-txt-cover]').value);
    f.append('message', $('[data-m4-txt-msg]').value);
    const pw = $('[data-m4-txt-pw]').value; if (pw) f.append('password', pw);
    busy(btn, true);
    const res = await post('/api/learn/text', f);
    busy(btn, false);
    if (!res.ok) return setStatus(st, res.error || 'Something went wrong.');
    stepper($('[data-m4-txt-walk]'), textSteps(res.trace));
  });

  /* ================= HISTORY ================= */
  const hist = { items: [] };
  function utc(s) { return new Date(s.replace(' ', 'T') + 'Z'); }
  function drawHistory() {
    const f = Object.fromEntries($$('[data-m4-f]').map(s => [s.dataset.m4F, s.value]));
    const list = hist.items.filter(r => (!f.action || r.action === f.action) && (!f.carrier || r.carrier === f.carrier) &&
      (!f.success || String(+r.success) === f.success));
    const all = hist.items, hides = all.filter(r => r.action === 'hide').length, fails = all.filter(r => !r.success).length;
    $('[data-m4-hist-stats]').innerHTML = all.length ? [
      `<span class="m4-chip"><b>${all.length}</b> total</span>`, `<span class="m4-chip"><b>${hides}</b> hidden</span>`,
      `<span class="m4-chip"><b>${all.length - hides}</b> revealed</span>`, `<span class="m4-chip"><b>${fails}</b> failed</span>`,
      list.length !== all.length ? `<span class="m4-chip">showing <b>${list.length}</b></span>` : ''].join('') : '';
    $('[data-m4-hist-empty]').hidden = list.length > 0;
    $('.m4-hist').hidden = list.length === 0;
    $('[data-m4-clear]').disabled = all.length === 0;
    $('[data-m4-hist-rows]').innerHTML = list.map(r => {
      const d = utc(r.created);
      return `<tr>
        <td>${esc(d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }))}<small>${esc(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))}</small></td>
        <td><span class="m4-badge ${r.action}">${r.action === 'hide' ? 'Hide' : 'Reveal'}</span></td>
        <td>${r.carrier === 'image' ? 'Picture' : 'Text'}<small>${esc(r.method)}</small></td>
        <td>${r.action === 'hide' ? 'To ' : 'From '}${esc(r.other || '—')}</td>
        <td>${r.message_chars == null ? '—' : r.message_chars + ' chars'}</td>
        <td>${r.locked ? '🔒' : '—'}</td>
        <td><span class="m4-badge ${r.success ? 'ok' : 'fail'}">${r.success ? 'Success' : 'Failed'}</span>${r.error ? `<small>${esc(r.error)}</small>` : ''}</td>
        <td><button class="m4-x" data-m4-del="${r.id}" title="Delete entry" aria-label="Delete entry">×</button></td></tr>`;
    }).join('');
  }
  async function loadHistory() {
    let data;
    try { data = await (await fetch('/api/history')).json(); } catch { data = null; }
    if (!data?.ok) return;
    hist.items = data.items; drawHistory();
  }
  $$('[data-m4-f]').forEach(s => s.addEventListener('change', drawHistory));
  $('[data-m4-hist-rows]')?.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-m4-del]'); if (!b) return;
    await fetch(`/api/history/${b.dataset.m4Del}`, { method: 'DELETE' });
    hist.items = hist.items.filter(r => String(r.id) !== b.dataset.m4Del); drawHistory();
  });
  $('[data-m4-clear]')?.addEventListener('click', async () => {
    if (!confirm('Delete your whole history? This cannot be undone.')) return;
    await fetch('/api/history', { method: 'DELETE' });
    hist.items = []; drawHistory(); toast('History cleared.');
  });

  /* load data when the tabs are opened */
  document.addEventListener('click', (e) => {
    const nav = e.target.closest('[data-nav]'); if (!nav) return;
    if (nav.dataset.nav === 'tutorial') loadPicker();
    if (nav.dataset.nav === 'history') loadHistory();
  });
})();
