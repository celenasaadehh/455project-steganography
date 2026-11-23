(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const enc = new TextEncoder();
  const bytes = (s) => enc.encode(s).length;

  const state = { me: null, view: 'inbox', items: [], selected: null, gallery: null, unread: 0, filter: 'all' };
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const authEl = $('#auth'), appEl = $('#app'), composeEl = $('#compose');

  // ------------------------------------------------------------ helpers
  async function api(url, { method = 'GET', body, json } = {}) {
    const opts = { method, headers: {} };
    if (json) { opts.body = JSON.stringify(json); opts.headers['Content-Type'] = 'application/json'; }
    else if (body) opts.body = body;
    let res;
    try { res = await fetch(url, opts); }
    catch { return { ok: false, error: 'Cannot reach the server.' }; }
    let data;
    try { data = await res.json(); }
    catch { data = { ok: false, error: res.status === 413 ? 'File too large (max 40 MB).' : 'Server error.' }; }
    if (res.status === 401 && data.code === 'auth' && state.me) { state.me = null; showAuth(); }
    return data;
  }

  function status(root, text, kind = 'error') {
    const el = root.matches?.('.status') ? root : $('.status', root);
    if (!el) return;
    el.className = `status ${text ? kind : ''}`;
    el.textContent = text || '';
  }

  function busy(btn, on, label) {
    if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span>${label || ''}`; }
    else { btn.disabled = false; btn.innerHTML = btn.dataset.label || btn.innerHTML; }
  }

  let toastTimer;
  function toast(text) {
    const t = $('[data-toast]');
    t.textContent = text; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 2400);
  }

  function setAvatar(el, user) {
    if (!el) return;
    if (user?.avatar) { el.style.backgroundImage = `url("${user.avatar}")`; el.textContent = ''; }
    else { el.style.backgroundImage = ''; el.textContent = user?.initials || '?'; }
  }

  function fmtTime(s) {
    const d = new Date(s.replace(' ', 'T') + 'Z');
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const sameYear = d.getFullYear() === now.getFullYear();
    return d.toLocaleDateString([], sameYear ? { month: 'short', day: 'numeric' } : { year: 'numeric', month: 'short', day: 'numeric' });
  }
  const fmtFull = (s) => new Date(s.replace(' ', 'T') + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });

  // ------------------------------------------------------------ auth
  function showAuthForm(name) {
    ['login', 'register', 'verify'].forEach(n => { $(`#${n}-form`).hidden = n !== name; });
    $(`#${name}-form input:not([type=hidden])`).focus();
  }
  function showAuth() {
    appEl.hidden = true; authEl.hidden = false; composeEl.hidden = true;
    showAuthForm('login');
  }
  $$('[data-auth]').forEach(b => b.addEventListener('click', () => showAuthForm(b.dataset.auth)));

  // Code screen: after creating an account, or when signing in to an unverified one.
  function startVerify(email, mailSent, note) {
    const f = $('#verify-form');
    f.reset(); f.handle.value = email;
    $('[data-verify-email]').textContent = email;
    showAuthForm('verify');
    status(f, mailSent ? (note || '') : 'E-mail is not set up on this server yet, so the code was printed in the server window.', mailSent ? 'ok' : 'error');
  }

  async function authSubmit(form, url) {
    const btn = $('button[type=submit]', form);
    const json = Object.fromEntries(new FormData(form).entries());
    if (!json.handle || !json.password) return status(form, 'Fill in every field.');
    status(form, '');
    busy(btn, true, url.endsWith('login') ? 'Signing in…' : 'Sending code…');
    const res = await api(url, { method: 'POST', json });
    busy(btn, false);
    if (res.code === 'unverified') { form.reset(); return startVerify(res.email, res.mail_sent, res.error); }
    if (!res.ok) return status(form, res.error);
    form.reset();
    if (res.verify) return startVerify(res.email, res.mail_sent);
    enter(res.user, 0);
  }
  $('#login-form').addEventListener('submit', (e) => { e.preventDefault(); authSubmit(e.target, '/api/auth/login'); });
  $('#register-form').addEventListener('submit', (e) => { e.preventDefault(); authSubmit(e.target, '/api/auth/register'); });

  $('#verify-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target, btn = $('button[type=submit]', f);
    const code = f.code.value.replace(/\D/g, '');
    if (code.length !== 6) { f.code.focus(); return status(f, 'Enter the 6-digit code.'); }
    status(f, '');
    busy(btn, true, 'Checking…');
    const res = await api('/api/auth/verify', { method: 'POST', json: { handle: f.handle.value, code } });
    busy(btn, false);
    if (!res.ok) { f.code.select(); return status(f, res.error); }
    f.reset();
    toast('Email verified');
    enter(res.user, 0);
  });
  $('[data-resend]').addEventListener('click', async () => {
    const f = $('#verify-form');
    status(f, '');
    const res = await api('/api/auth/resend', { method: 'POST', json: { handle: f.handle.value } });
    if (!res.ok) return status(f, res.error);
    status(f, res.mail_sent ? 'New code sent.' : 'New code printed in the server window.', 'ok');
    f.code.value = ''; f.code.focus();
  });
  $('#verify-form input[name=code]').addEventListener('input', (e) => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6); });

  $$('[data-logout]').forEach(b => b.addEventListener('click', async () => {
    await api('/api/auth/logout', { method: 'POST' });
    state.me = null; state.items = []; state.selected = null; state.unread = 0;
    document.title = 'Stego Mail';
    showAuth();
  }));

  // ------------------------------------------------------------ app shell
  function enter(user, unread) {
    state.me = user; state.unread = null;  // unknown until the first refresh, so sign-in never triggers a "new message" alert
    authEl.hidden = true; appEl.hidden = false;
    if (user.accent) applyAccent(user.accent, false);
    renderMe();
    resetCompose();
    showView('inbox');
  }

  function renderMe() {
    const u = state.me;
    setAvatar($('.me [data-avatar]'), u);
    setAvatar($('.settings [data-avatar]'), u);
    $('[data-me-name]').textContent = u.name;
    const badge = $('[data-unread]');
    badge.hidden = !state.unread; badge.textContent = state.unread;
    const pf = $('[data-profile-form]');
    pf.first_name.value = u.first_name; pf.last_name.value = u.last_name; pf.handle.value = u.handle;
    fillPrefs(); fillNotify(); fillAbout(null); updateTitle();
  }

  const TITLES = { inbox: 'Inbox', sent: 'Sent', gallery: 'Gallery', tutorial: 'Learn', history: 'History', settings: 'Settings' };
  function showView(name) {
    state.view = name;
    $$('[data-nav]').forEach(b => b.classList.toggle('active', b.dataset.nav === name && b.closest('.nav')));
    $('[data-title]').textContent = TITLES[name];
    const icon = $(`.nav [data-nav="${name}"] svg`);          // same icon as the menu item
    $('[data-title-icon]').replaceChildren(...(icon ? [icon.cloneNode(true)] : []));
    const isMail = name === 'inbox' || name === 'sent';
    $$('[data-view]').forEach(v => { v.hidden = v.dataset.view !== (isMail ? 'mail' : name); });
    $('[data-search-wrap]').hidden = !isMail;
    appEl.classList.remove('side-open');
    if (isMail) { closeDetail(); loadMail(); }
    if (name === 'gallery') loadGallery();
  }
  $$('[data-nav]').forEach(b => b.addEventListener('click', () => showView(b.dataset.nav)));
  $('[data-menu]').addEventListener('click', () => appEl.classList.toggle('side-open'));
  $('.main').addEventListener('click', (e) => { if (appEl.classList.contains('side-open') && !e.target.closest('.menu')) appEl.classList.remove('side-open'); });

  // ------------------------------------------------------------ mail list
  async function loadMail() {
    const box = state.view;
    const res = await api(`/api/messages?box=${box}`);
    if (!res.ok || state.view !== box) return;
    state.items = res.items;
    renderList();
    refreshUnread();
  }

  const FILTERS = {
    all: () => true,
    unread: (m) => m.direction === 'inbox' && !m.read,
    pinned: (m) => m.pinned,
    locked: (m) => m.locked,
    image: (m) => m.carrier === 'image',
    text: (m) => m.carrier === 'text',
  };

  // Date buckets for the group headers. Pinned messages always come first.
  function bucket(m) {
    if (m.pinned) return 'Pinned';
    const d = new Date(m.created.replace(' ', 'T') + 'Z'), now = new Date();
    const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day(now) - day(d)) / 864e5);
    if (diff <= 0) return 'Today';
    if (diff === 1) return 'Yesterday';
    if (diff < 7) return 'This week';
    if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) return 'This month';
    return 'Earlier';
  }

  function visibleItems() {
    const q = $('[data-search]').value.trim().toLowerCase();
    const f = FILTERS[state.filter] || FILTERS.all;
    return state.items
      .filter(m => f(m) && (!q || [m.with?.name, m.with?.handle, m.subject].join(' ').toLowerCase().includes(q)))
      .sort((a, b) => (b.pinned - a.pinned) || (a.created < b.created ? 1 : a.created > b.created ? -1 : b.id - a.id));
  }

  function renderList() {
    const list = $('[data-list]');
    $$('.row, .group-h', list).forEach(r => r.remove());
    const inbox = state.view === 'inbox';
    $('[data-filter="unread"]').hidden = !inbox;
    if (!inbox && state.filter === 'unread') state.filter = 'all';
    $$('[data-filter]').forEach(c => c.classList.toggle('active', c.dataset.filter === state.filter));
    const counts = { unread: state.items.filter(FILTERS.unread).length, pinned: state.items.filter(FILTERS.pinned).length };
    $$('[data-count]').forEach(b => { b.textContent = counts[b.dataset.count] || ''; });

    const items = visibleItems();
    const empty = $('[data-empty]');
    empty.hidden = items.length > 0;
    const q = $('[data-search]').value.trim();
    $('[data-empty-text]').textContent = q || state.filter !== 'all' ? 'No matches' : inbox ? 'No messages yet' : 'Nothing sent yet';
    const tpl = $('#tpl-row').content;
    let group = null;
    items.forEach((m, i) => {
      const g = bucket(m);
      if (g !== group) {
        group = g;
        const h = document.createElement('div');
        h.className = 'group-h'; h.textContent = g;
        list.insertBefore(h, empty);
      }
      const row = tpl.firstElementChild.cloneNode(true);
      row.dataset.id = m.id;
      row.style.setProperty('--i', Math.min(i, 12));
      row.classList.toggle('unread', inbox && !m.read);
      row.classList.toggle('pinned', !!m.pinned);
      row.classList.toggle('active', state.selected?.id === m.id);
      setAvatar($('.avatar', row), m.with);
      $('.row-name', row).textContent = (state.view === 'sent' ? 'To ' : '') + (m.with?.name || m.with?.handle || '?');
      $('.row-time', row).textContent = fmtTime(m.created);
      $('.row-kind', row).textContent = (m.locked ? '🔒 ' : '') + (m.carrier === 'image' ? m.format : 'Text');
      $('.row-subject', row).textContent = m.subject ? `· ${m.subject}` : '';
      const th = $('.row-thumb', row);
      if (m.thumb_url) { th.src = m.thumb_url; th.hidden = false; }
      $('[data-act="read"]', row).hidden = !inbox;
      $('[data-act="pin"]', row).title = m.pinned ? 'Unpin' : 'Pin';
      $('[data-act="read"]', row).title = m.read ? 'Mark unread' : 'Mark read';
      row.addEventListener('click', (e) => {
        const act = e.target.closest('[data-act]');
        if (!act) return openMessage(m);
        e.stopPropagation();
        if (act.dataset.act === 'pin') updateMessage(m, { pinned: !m.pinned });
        if (act.dataset.act === 'read') updateMessage(m, { read: !m.read });
        if (act.dataset.act === 'delete') deleteMessage(m);
      });
      row.addEventListener('keydown', (e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target === row) { e.preventDefault(); openMessage(m); } });
      list.insertBefore(row, empty);
    });
  }
  $$('[data-filter]').forEach(c => c.addEventListener('click', () => { state.filter = c.dataset.filter; renderList(); }));

  // Pin / unpin and read / unread, saved on the server for this side of the message only.
  async function updateMessage(m, patch) {
    const res = await api(`/api/messages/${m.id}`, { method: 'PATCH', json: { ...patch, box: state.view } });
    if (!res.ok) { toast(res.error); return false; }
    Object.assign(m, { pinned: res.message.pinned, read: res.message.read });
    renderList();
    if (state.selected?.id === m.id) syncTools(m);
    if ('read' in patch) refreshUnread();
    if ('pinned' in patch) toast(m.pinned ? 'Pinned' : 'Unpinned');
    return true;
  }

  async function deleteMessage(m) {
    if (!m || !confirm('Delete this message?')) return;
    const res = await api(`/api/messages/${m.id}`, { method: 'DELETE' });
    if (!res.ok) return toast(res.error);
    state.items = state.items.filter(x => x.id !== m.id);
    if (state.selected?.id === m.id) closeDetail();
    renderList(); refreshUnread(); toast('Deleted');
  }

  $('[data-search]').addEventListener('input', renderList);
  $('[data-search-wrap]').addEventListener('submit', (e) => { e.preventDefault(); renderList(); $('[data-search]').focus(); });

  // ------------------------------------------------------------ detail
  function closeDetail() {
    state.selected = null;
    $('[data-detail]').hidden = true;
    $('[data-detail-empty]').hidden = false;
    renderWelcome();
    $('.mail').classList.remove('showing-detail');
    $$('.row.active').forEach(r => r.classList.remove('active'));
  }
  $('[data-back]').addEventListener('click', closeDetail);

  async function openMessage(m) {
    state.selected = m;
    $$('.row').forEach(r => r.classList.toggle('active', Number(r.dataset.id) === m.id));
    const d = $('[data-detail]');
    d.hidden = false;
    $('[data-detail-empty]').hidden = true;
    $('.mail').classList.add('showing-detail');
    setAvatar($('[data-d-avatar]'), m.with);
    $('[data-d-name]').textContent = (m.direction === 'sent' ? 'To ' : '') + (m.with?.name || '?');
    $('[data-d-sub]').textContent = m.direction === 'sent' ? 'Sent' : 'Received';
    $('[data-d-time]').textContent = fmtFull(m.created);
    $('[data-d-subject]').textContent = m.subject || '';

    const im = $('[data-d-img]'), tx = $('[data-d-text]');
    $('[data-stage]').hidden = m.carrier !== 'image'; tx.hidden = m.carrier !== 'text';
    xrayOff();
    if (m.carrier === 'image') im.src = m.file_url; else tx.textContent = m.text;
    $('[data-xray]').hidden = m.carrier !== 'image';
    $('[data-show-hidden]').hidden = m.carrier !== 'text';
    $('[data-show-hidden]').classList.remove('on');
    $('[data-carrier-note]').textContent = '';
    syncTools(m);

    const dl = $('[data-download]');
    dl.hidden = m.carrier !== 'image';
    if (m.file_url) { dl.href = `${m.file_url}?dl=1`; dl.setAttribute('download', ''); }
    $('[data-copy-text]').hidden = m.carrier !== 'text';

    const unlock = $('[data-unlock]');
    unlock.hidden = !m.locked; unlock.reset();
    status($('[data-d-status]'), '');
    $('[data-secret]').hidden = true;
    if (!m.locked) reveal(m, null);
    else setTimeout(() => unlock.password.focus(), 50);
  }

  async function reveal(m, password) {
    const fd = new FormData();
    if (password) fd.append('password', password);
    const btn = $('[data-unlock] button');
    const stat = $('[data-d-status]');
    status(stat, '');
    if (m.locked) busy(btn, true, 'Revealing…');
    const res = await api(`/api/messages/${m.id}/reveal`, { method: 'POST', body: fd });
    if (m.locked) busy(btn, false);
    if (state.selected?.id !== m.id) return;
    if (!res.ok) return status(stat, res.error);
    const sec = $('[data-secret]');
    sec.hidden = false;
    decrypt(sec, res.message);
    if (m.carrier === 'image' && !reduceMotion) {
      const st = $('[data-stage]');
      st.classList.remove('scanning'); void st.offsetWidth; st.classList.add('scanning');
    }
    $('[data-unlock]').hidden = true;
    if (!m.read && m.direction === 'inbox') {
      m.read = true;
      renderList();
      refreshUnread();
    }
  }
  $('[data-unlock]').addEventListener('submit', (e) => {
    e.preventDefault();
    const pw = e.target.password.value;
    if (!pw) return status($('[data-d-status]'), 'Enter the password.');
    reveal(state.selected, pw);
  });

  $('[data-delete]').addEventListener('click', () => deleteMessage(state.selected));

  // ---------- reading-pane toolbar
  function syncTools(m) {
    const inbox = m.direction === 'inbox';
    $('[data-reply]').hidden = !inbox;
    $('[data-mark-unread]').hidden = !inbox;
    $('[data-pin]').classList.toggle('on', !!m.pinned);
    $('[data-pin-label]').textContent = m.pinned ? 'Pinned' : 'Pin';
  }
  $('[data-pin]').addEventListener('click', () => state.selected && updateMessage(state.selected, { pinned: !state.selected.pinned }));
  $('[data-mark-unread]').addEventListener('click', async () => {
    const m = state.selected;
    if (m && await updateMessage(m, { read: false })) { closeDetail(); toast('Marked unread'); }
  });
  $('[data-reply]').addEventListener('click', () => reply(state.selected));
  function reply(m) {
    if (!m || m.direction !== 'inbox' || !m.with) return;
    resetCompose();
    openCompose();
    form.to.value = m.with.handle;
    form.to.dispatchEvent(new Event('input'));
    form.subject.value = m.subject ? (/^re:/i.test(m.subject) ? m.subject : `Re: ${m.subject}`).slice(0, 80) : '';
    setTimeout(() => form.message.focus(), 60);
  }

  // ---------- the secret "decrypts" into place
  const GLYPHS = '01▚▞▙▟░▒#%&@$§';
  let decryptRun = 0;
  function decrypt(el, text) {
    const run = ++decryptRun;
    if (reduceMotion || text.length > 600) { el.textContent = text; return; }
    const chars = [...text], start = performance.now(), dur = Math.min(900, 300 + chars.length * 12);
    el.classList.add('decrypting');
    const frame = (now) => {
      if (run !== decryptRun) return;
      const t = (now - start) / dur;
      el.textContent = chars.map((c, i) => (/\s/.test(c) || t >= (i / chars.length) * 0.8 + 0.2 ? c : GLYPHS[(Math.random() * GLYPHS.length) | 0])).join('');
      if (t < 1) requestAnimationFrame(frame);
      else { el.textContent = text; el.classList.remove('decrypting'); }
    };
    requestAnimationFrame(frame);
  }

  // ---------- X-ray lens: magnifies the lowest bit of every colour value,
  // the layer where an image message lives. Busy areas look like static.
  const lens = $('[data-lens]'), stageImg = $('[data-d-img]');
  let lsb = null, lsbFor = null;
  function xrayOff() {
    lens.hidden = true;
    $('[data-xray]').classList.remove('on');
    $('[data-stage]').classList.remove('xray');
  }
  function buildLsb() {
    if (lsb && lsbFor === stageImg.src) return lsb;
    const w = stageImg.naturalWidth, h = stageImg.naturalHeight;
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(stageImg, 0, 0);
    const img = ctx.getImageData(0, 0, w, h), d = img.data;
    for (let i = 0; i < d.length; i += 4) {
      d[i] = (d[i] & 1) * 255; d[i + 1] = (d[i + 1] & 1) * 255; d[i + 2] = (d[i + 2] & 1) * 255; d[i + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    lsb = c; lsbFor = stageImg.src;
    return c;
  }
  function contentBox() {   // where the picture is drawn inside the <img> (object-fit: contain)
    const r = stageImg.getBoundingClientRect(), nw = stageImg.naturalWidth, nh = stageImg.naturalHeight;
    const k = Math.min(r.width / nw, r.height / nh);
    return { r, k, x: r.left + (r.width - nw * k) / 2, y: r.top + (r.height - nh * k) / 2, w: nw * k, h: nh * k };
  }
  function drawLens(cx, cy) {
    const b = contentBox(), dpr = devicePixelRatio || 1, R = 74, zoom = 3;
    const W = Math.round(b.r.width * dpr), H = Math.round(b.r.height * dpr);
    if (lens.width !== W || lens.height !== H) { lens.width = W; lens.height = H; }
    const ctx = lens.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, b.r.width, b.r.height);
    if (cx < b.x || cy < b.y || cx > b.x + b.w || cy > b.y + b.h) return;
    const lx = cx - b.r.left, ly = cy - b.r.top;
    const nx = (cx - b.x) / b.k, ny = (cy - b.y) / b.k;   // the point under the cursor, in image pixels
    const src = (2 * R) / zoom;
    ctx.save();
    ctx.beginPath(); ctx.arc(lx, ly, R, 0, Math.PI * 2); ctx.clip();
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#000'; ctx.fillRect(lx - R, ly - R, 2 * R, 2 * R);
    ctx.drawImage(lsb, nx - src / 2, ny - src / 2, src, src, lx - R, ly - R, 2 * R, 2 * R);
    ctx.restore();
    ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.95)';
    ctx.beginPath(); ctx.arc(lx, ly, R, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = 1; ctx.strokeStyle = 'rgba(0,0,0,.35)';
    ctx.beginPath(); ctx.arc(lx, ly, R + 2, 0, Math.PI * 2); ctx.stroke();
  }
  $('[data-xray]').addEventListener('click', () => {
    if (!lens.hidden) { xrayOff(); $('[data-carrier-note]').textContent = ''; return; }
    if (!stageImg.complete || !stageImg.naturalWidth) return toast('Image still loading');
    try { buildLsb(); } catch { return toast('X-ray is not available for this image'); }
    lens.hidden = false;
    $('[data-xray]').classList.add('on');
    $('[data-stage]').classList.add('xray');
    $('[data-carrier-note]').textContent = 'Move over the picture';
    const b = contentBox(); drawLens(b.x + b.w / 2, b.y + b.h / 2);
  });
  const stage = $('[data-stage]');
  stage.addEventListener('pointermove', (e) => { if (!lens.hidden) drawLens(e.clientX, e.clientY); });
  stage.addEventListener('pointerdown', (e) => { if (!lens.hidden) drawLens(e.clientX, e.clientY); });
  stage.addEventListener('pointerleave', (e) => { if (!lens.hidden && e.pointerType === 'mouse') lens.getContext('2d').clearRect(0, 0, lens.width, lens.height); });

  // ---------- Show hidden: a text message's invisible characters, drawn as a colour barcode
  // Member 2's characters (U+200B, U+200C, U+2060, U+2063), plus U+200D from the website's first format
  const ZW = { '\u200b': 0, '\u200c': 1, '\u2060': 2, '\u2063': 3, '\u200d': 3 };
  function renderHidden(pre, text) {
    pre.textContent = '';
    let i = 0, count = 0;
    while (i < text.length) {
      let j = i;
      while (j < text.length && text[j] in ZW) j++;
      if (j - i >= 8) {                       // a hidden message is one long run; short ones belong to emoji or Persian
        const run = document.createElement('span'); run.className = 'zw-run';
        for (let k = i; k < j; k++) { const bar = document.createElement('i'); bar.className = `zw z${ZW[text[k]]}`; run.appendChild(bar); }
        run.title = `${j - i} invisible characters`;
        pre.appendChild(run); count += j - i; i = j;
      } else {
        let e = Math.max(j, i + 1);
        while (e < text.length && !(text[e] in ZW)) e++;
        pre.appendChild(document.createTextNode(text.slice(i, e))); i = e;
      }
    }
    return count;
  }
  // English packets use 4 characters per byte; Arabic ones (only U+200B and U+2060) use 8.
  // Judge by the hidden run only: a Persian cover has its own U+200C outside the run.
  const perByte = (text) => { const run = (text.match(/[\u200b\u200c\u200d\u2060\u2063]{8,}/) || [''])[0]; return /[\u200c\u2063\u200d]/.test(run) ? 4 : 8; };
  $('[data-show-hidden]').addEventListener('click', (e) => {
    const btn = e.currentTarget, pre = $('[data-d-text]'), m = state.selected;
    if (!m) return;
    const on = !btn.classList.contains('on');
    btn.classList.toggle('on', on);
    if (on) {
      const n = renderHidden(pre, m.text);
      $('[data-carrier-note]').textContent = n ? `${n} invisible characters · ${Math.round(n / perByte(m.text))} bytes` : 'None found';
    } else { pre.textContent = m.text; $('[data-carrier-note]').textContent = ''; }
  });

  // ---------- keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (!state.me || appEl.hidden || !composeEl.hidden || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    const mail = state.view === 'inbox' || state.view === 'sent';
    const k = e.key.toLowerCase();
    if (k === 'c') { e.preventDefault(); openCompose(); }
    else if (k === '/' && mail) { e.preventDefault(); $('[data-search]').focus(); }
    else if ((k === 'j' || k === 'k') && mail) {
      const items = visibleItems();
      if (!items.length) return;
      const at = items.findIndex(m => m.id === state.selected?.id);
      const next = items[Math.max(0, Math.min(items.length - 1, at < 0 ? 0 : at + (k === 'j' ? 1 : -1)))];
      openMessage(next);
      $(`.row[data-id="${next.id}"]`)?.scrollIntoView({ block: 'nearest' });
    }
    else if (k === 'p' && state.selected) updateMessage(state.selected, { pinned: !state.selected.pinned });
    else if (k === 'r' && state.selected) { e.preventDefault(); reply(state.selected); }
    else if (k === 'u' && state.selected?.direction === 'inbox') $('[data-mark-unread]').click();
    else if (e.key === 'Delete' && state.selected) deleteMessage(state.selected);
  });

  $('[data-copy-text]').addEventListener('click', async (e) => {
    try { await navigator.clipboard.writeText(state.selected.text); toast('Copied'); }
    catch { toast('Select the text and press Ctrl+C'); }
  });

  const TIPS = [
    'Send pictures as files, not photos: apps that shrink photos erase the hidden message.',
    'Share the password another way, like a phone call.',
    'PNG holds the most. JPEG holds less but survives a re-save.',
    'Text mode hides your secret in invisible characters inside a normal sentence.',
    'Add your own pictures in Gallery to use them again and again.',
  ];
  function renderWelcome() {
    const hour = new Date().getHours();
    const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    $('[data-empty-hello]').textContent = `${greet}, ${state.me.first_name}`;
    $('[data-tip]').textContent = TIPS[Math.floor(Math.random() * TIPS.length)];
  }

  async function refreshUnread() {
    const res = await api('/api/me');
    if (!res.ok || !res.user) return;
    const before = state.unread;
    state.unread = res.unread;
    const badge = $('[data-unread]');
    badge.hidden = !res.unread; badge.textContent = res.unread;
    if (res.unread > before && before !== null) announce(res.unread - before);
    updateTitle();
    fillAbout(res);
  }
  setInterval(() => {
    if (!state.me || document.hidden) return;
    if (state.view === 'inbox' && !state.selected) loadMail(); else refreshUnread();
  }, 30000);

  // ------------------------------------------------------------ gallery
  async function fetchGallery() {
    const res = await api('/api/gallery');
    if (!res.ok) return false;
    state.gallery = res.items;
    buildPickGrid();
    return true;
  }

  async function loadGallery() {
    if (!state.gallery && !(await fetchGallery())) return;
    renderGallery();
  }

  function renderGallery() {
    const grid = $('[data-gallery]');
    $$('.gtile:not(.gadd)', grid).forEach(t => t.remove());
    const tpl = $('#tpl-gallery').content;
    const addTile = $('.gadd', grid);
    for (const g of state.gallery) {
      const t = tpl.firstElementChild.cloneNode(true);
      t.dataset.id = g.id;
      $('img', t).src = g.thumb_url; $('img', t).alt = g.name;
      $('.gname', t).textContent = g.name;
      t.title = 'Send with this picture';
      const pick = () => openCompose({ gallery: g.id });
      t.addEventListener('click', (e) => { if (!e.target.closest('.gdel')) pick(); });
      t.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
      const del = $('.gdel', t);
      del.hidden = !g.own;
      del.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm(`Remove "${g.name}" from your gallery?`)) return;
        const res = await api(`/api/gallery/${g.id}`, { method: 'DELETE' });
        if (!res.ok) return toast(res.error);
        state.gallery = state.gallery.filter(x => x.id !== g.id);
        if (compose.gallery === g.id) selectCover({});
        buildPickGrid(); renderGallery(); toast('Removed');
      });
      grid.insertBefore(t, addTile);
    }
    grid.appendChild(addTile); // keep the add tile last
  }

  $('[data-gallery-add]').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const tile = $('.gadd');
    tile.classList.add('busy');
    const fd = new FormData(); fd.append('image', file);
    const res = await api('/api/gallery', { method: 'POST', body: fd });
    tile.classList.remove('busy');
    e.target.value = '';
    if (!res.ok) return toast(res.error);
    state.gallery = [...(state.gallery || []), res.item];
    buildPickGrid(); renderGallery();
    toast(`Added "${res.item.name}"`);
  });

  // ------------------------------------------------------------ compose
  const form = $('[data-compose]');
  const compose = { carrier: 'image', gallery: null, file: null, cap: null, toUser: null };

  function buildPickGrid() {
    const grid = $('[data-pick-grid]');
    $$('.tile:not(.upload)', grid).forEach(t => t.remove());
    for (const g of state.gallery) {
      const t = document.createElement('button');
      t.type = 'button'; t.className = 'tile'; t.dataset.gallery = g.id; t.title = g.name;
      t.innerHTML = `<img alt="${g.name}" src="${g.thumb_url}">`;
      t.addEventListener('click', () => selectCover({ gallery: g.id }));
      grid.insertBefore(t, $('.tile.upload', grid));
    }
  }

  function selectCover({ gallery = null, file = null }) {
    compose.gallery = gallery; compose.file = file;
    $$('.tile', form).forEach(t => t.classList.toggle('selected', gallery ? t.dataset.gallery === String(gallery) : !!(file && t.classList.contains('upload'))));
    const up = $('.tile.upload', form);
    const img = $('img', up);
    if (file) { img.src = URL.createObjectURL(file); img.hidden = false; up.classList.add('has-file'); }
    else { img.hidden = true; up.classList.remove('has-file'); if (!file) $('input[type=file]', up).value = ''; }
    refreshCapacity();
  }
  $('.tile.upload input', form).addEventListener('change', (e) => { if (e.target.files[0]) selectCover({ file: e.target.files[0] }); });

  let capTimer;
  function refreshCapacity() {
    compose.cap = null; renderMeter();
    clearTimeout(capTimer);
    if (compose.carrier !== 'image' || (!compose.gallery && !compose.file)) return;
    capTimer = setTimeout(async () => {
      const fd = new FormData();
      if (compose.gallery) fd.append('gallery', compose.gallery); else fd.append('image', compose.file);
      fd.append('format', form.format.value);
      fd.append('encrypted', form.lock.checked ? '1' : '0');
      const key = `${compose.gallery}|${compose.file?.name}|${form.format.value}|${form.lock.checked}`;
      const res = await api('/api/image/capacity', { method: 'POST', body: fd });
      if (key !== `${compose.gallery}|${compose.file?.name}|${form.format.value}|${form.lock.checked}`) return;
      compose.cap = res.ok ? res : { error: res.error };
      renderMeter();
    }, 120);
  }

  function renderMeter() {
    const text = $('[data-meter-text]'), bar = $('[data-meter-bar]'), span = $('span', bar);
    const used = bytes(form.message.value);
    text.classList.remove('over'); bar.classList.remove('over');
    if (compose.carrier === 'text') return;
    if (!compose.gallery && !compose.file) { text.textContent = 'Pick a picture'; span.style.width = '0'; return; }
    if (!compose.cap) { text.textContent = 'Checking…'; span.style.width = '0'; return; }
    if (compose.cap.error) { text.textContent = compose.cap.error; text.classList.add('over'); span.style.width = '0'; return; }
    const max = compose.cap.max_message_bytes;
    const over = used > max || !compose.cap.can_embed;
    span.style.width = `${Math.min(100, max ? (used / max) * 100 : 100)}%`;
    text.classList.toggle('over', over); bar.classList.toggle('over', over);
    text.textContent = !compose.cap.can_embed ? 'Picture too small' : `${used.toLocaleString()} / ${max.toLocaleString()} characters`;
  }
  form.message.addEventListener('input', renderMeter);
  form.format.addEventListener('change', refreshCapacity);
  form.lock.addEventListener('change', () => { syncLock(); refreshCapacity(); });
  function syncLock() { form.password.hidden = !form.lock.checked; $('[data-lock-warn]').hidden = form.lock.checked; }

  $$('[data-carrier]', form).forEach(b => b.addEventListener('click', () => {
    compose.carrier = b.dataset.carrier;
    $$('[data-carrier]', form).forEach(x => x.classList.toggle('active', x === b));
    $$('[data-carrier-pane]', form).forEach(p => { p.hidden = p.dataset.carrierPane !== compose.carrier; });
    renderMeter();
  }));

  let toTimer;
  form.to.addEventListener('input', () => {
    compose.toUser = null;
    const st = $('[data-to-status]');
    st.textContent = ''; st.className = 'to-status';
    clearTimeout(toTimer);
    const q = form.to.value.trim();
    if (!q) return;
    toTimer = setTimeout(async () => {
      const res = await api(`/api/users/lookup?q=${encodeURIComponent(q)}`);
      if (form.to.value.trim() !== q) return;
      if (res.ok && res.user) { compose.toUser = res.user; st.textContent = `✓ ${res.user.name}`; st.className = 'to-status ok'; }
      else { st.textContent = 'Not found'; st.className = 'to-status bad'; }
    }, 300);
  });

  function openCompose(opts = {}) {
    composeEl.hidden = false;
    if (opts.gallery && state.gallery) selectCover({ gallery: opts.gallery });
    if (!state.gallery) fetchGallery().then(ok => { if (ok && opts.gallery) selectCover({ gallery: opts.gallery }); });
    syncLock();
    setTimeout(() => (form.to.value ? form.message : form.to).focus(), 50);
  }
  function closeCompose() { composeEl.hidden = true; }
  function resetCompose() {
    form.reset();
    form.lock.checked = state.me?.prefs?.default_lock ?? true;  // Security → "Lock new messages by default"
    syncLock();
    selectCover({});
    compose.toUser = null; compose.carrier = 'image';
    $('[data-to-status]').textContent = '';
    $$('[data-carrier]', form).forEach(x => x.classList.toggle('active', x.dataset.carrier === 'image'));
    $$('[data-carrier-pane]', form).forEach(p => { p.hidden = p.dataset.carrierPane !== 'image'; });
    status(form, '');
  }
  $$('[data-compose-open]').forEach(b => b.addEventListener('click', () => openCompose()));
  $$('[data-compose-close]').forEach(b => b.addEventListener('click', closeCompose));
  composeEl.addEventListener('click', (e) => { if (e.target === composeEl) closeCompose(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (!composeEl.hidden) closeCompose(); else if (state.selected) closeDetail(); } });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const to = form.to.value.trim();
    if (!to) { form.to.focus(); return status(form, 'Who is it for?'); }
    if (!form.message.value.trim()) { form.message.focus(); return status(form, 'Write the secret message.'); }
    if (form.lock.checked && !form.password.value) { form.password.focus(); return status(form, 'Enter a password, or switch Lock off.'); }
    if (compose.carrier === 'image' && !compose.gallery && !compose.file) return status(form, 'Pick a picture.');
    if (compose.carrier === 'text' && !form.cover.value.trim()) { form.cover.focus(); return status(form, 'Write the visible text.'); }

    const fd = new FormData();
    fd.append('to', to);
    fd.append('subject', form.subject.value);
    fd.append('message', form.message.value);
    fd.append('carrier', compose.carrier);
    if (form.lock.checked) fd.append('password', form.password.value);
    if (compose.carrier === 'image') {
      fd.append('format', form.format.value);
      if (compose.gallery) fd.append('gallery', compose.gallery); else fd.append('image', compose.file);
    } else fd.append('cover', form.cover.value);

    const btn = $('button[type=submit]', form);
    status(form, '');
    busy(btn, true, 'Sending…');
    const res = await api('/api/messages', { method: 'POST', body: fd });
    busy(btn, false);
    if (!res.ok) { if (res.code === 'no_user') form.to.focus(); return status(form, res.error); }
    closeCompose(); resetCompose();
    toast(`Sent to ${res.message.with?.name || to}`);
    if (state.view === 'sent' || (state.view === 'inbox' && res.message.to_me)) loadMail(); else refreshUnread();
  });

  // ------------------------------------------------------------ settings
  $('[data-profile-form]').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    const res = await api('/api/me', { method: 'POST', json: { first_name: f.first_name.value, last_name: f.last_name.value } });
    if (!res.ok) return status(f, res.error);
    state.me = res.user; renderMe(); status(f, 'Saved', 'ok'); toast('Saved');
  });

  $('[data-password-form]').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    if (!f.current_password.value || !f.new_password.value) return status(f, 'Fill in both fields.');
    const res = await api('/api/me', { method: 'POST', json: { current_password: f.current_password.value, new_password: f.new_password.value } });
    if (!res.ok) return status(f, res.error);
    f.reset(); status(f, 'Password updated', 'ok');
  });

  const avatarInput = $('[data-avatar-input]');
  $('[data-avatar-pick]').addEventListener('click', () => avatarInput.click());
  $('[data-avatar-open]').addEventListener('click', () => avatarInput.click());
  async function uploadAvatar(blob, name) {
    const fd = new FormData(); fd.append('avatar', blob, name);
    const res = await api('/api/me/avatar', { method: 'POST', body: fd });
    if (!res.ok) { toast(res.error); return false; }
    state.me = res.user; renderMe(); toast('Picture updated');
    return true;
  }
  avatarInput.addEventListener('change', () => {
    const file = avatarInput.files[0];
    avatarInput.value = '';
    if (file) openCropper(file);
  });

  // ---------- profile picture cropper: drag to move, slider or wheel to zoom.
  // The square stage is what gets saved; the circle shows what others will see.
  const cropEl = $('#cropper'), cropStage = $('[data-crop-stage]'), cropImg = $('[data-crop-img]'), cropZoom = $('[data-crop-zoom]');
  const crop = { file: null, url: null, w: 0, h: 0, S: 0, base: 1, z: 1, x: 0, y: 0 };
  function cropClamp() {
    const k = crop.base * crop.z, dw = crop.w * k, dh = crop.h * k;
    const mx = Math.max(0, (dw - crop.S) / 2), my = Math.max(0, (dh - crop.S) / 2);
    crop.x = Math.max(-mx, Math.min(mx, crop.x)); crop.y = Math.max(-my, Math.min(my, crop.y));
  }
  function cropDraw() {
    cropClamp();
    const k = crop.base * crop.z;
    cropImg.style.width = `${crop.w * k}px`; cropImg.style.height = `${crop.h * k}px`;
    cropImg.style.transform = `translate(-50%, -50%) translate(${crop.x}px, ${crop.y}px)`;
  }
  function setZoom(z, cx = 0, cy = 0) {   // zoom around a point (stage-centre coordinates)
    const old = crop.z;
    crop.z = Math.max(1, Math.min(5, z));
    const r = crop.z / old;
    crop.x = cx - (cx - crop.x) * r; crop.y = cy - (cy - crop.y) * r;
    cropZoom.value = crop.z; cropDraw();
  }
  function openCropper(file) {
    if (crop.url) URL.revokeObjectURL(crop.url);
    crop.file = file; crop.url = URL.createObjectURL(file);
    cropImg.onload = () => {
      cropEl.hidden = false;
      crop.S = cropStage.clientWidth;
      crop.w = cropImg.naturalWidth; crop.h = cropImg.naturalHeight;
      crop.base = Math.max(crop.S / crop.w, crop.S / crop.h);   // smallest size that fills the square
      crop.z = 1; crop.x = 0; crop.y = 0; cropZoom.value = 1;
      cropDraw();
    };
    cropImg.onerror = () => { uploadAvatar(file, file.name); };   // e.g. HEIC the browser can't show: the server centres it
    cropImg.src = crop.url;
  }
  function closeCropper() { cropEl.hidden = true; }
  let drag = null;
  cropStage.addEventListener('pointerdown', (e) => {
    drag = { id: e.pointerId, sx: e.clientX, sy: e.clientY, x: crop.x, y: crop.y };
    cropStage.setPointerCapture(e.pointerId); cropStage.classList.add('dragging');
  });
  cropStage.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    crop.x = drag.x + e.clientX - drag.sx; crop.y = drag.y + e.clientY - drag.sy; cropDraw();
  });
  const endDrag = () => { drag = null; cropStage.classList.remove('dragging'); };
  cropStage.addEventListener('pointerup', endDrag);
  cropStage.addEventListener('pointercancel', endDrag);
  cropStage.addEventListener('wheel', (e) => {
    e.preventDefault();
    const r = cropStage.getBoundingClientRect();
    setZoom(crop.z * Math.exp(-e.deltaY * 0.0015), e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2);
  }, { passive: false });
  cropZoom.addEventListener('input', () => setZoom(Number(cropZoom.value)));
  $$('[data-crop-step]').forEach(b => b.addEventListener('click', () => setZoom(crop.z + Number(b.dataset.cropStep))));
  $$('[data-crop-close]').forEach(b => b.addEventListener('click', closeCropper));
  cropEl.addEventListener('click', (e) => { if (e.target === cropEl) closeCropper(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !cropEl.hidden) closeCropper(); });
  $('[data-crop-save]').addEventListener('click', async () => {
    const btn = $('[data-crop-save]');
    const k = crop.base * crop.z, out = 512;
    const left = crop.S / 2 + crop.x - (crop.w * k) / 2, top = crop.S / 2 + crop.y - (crop.h * k) / 2;
    const c = document.createElement('canvas'); c.width = c.height = out;
    c.getContext('2d').drawImage(cropImg, -left / k, -top / k, crop.S / k, crop.S / k, 0, 0, out, out);
    const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.92));
    busy(btn, true, 'Saving…');
    const ok = await uploadAvatar(blob, 'avatar.jpg');
    busy(btn, false);
    if (ok) closeCropper();
  });
  $('[data-avatar-remove]').addEventListener('click', async () => {
    const res = await api('/api/me/avatar', { method: 'DELETE' });
    if (!res.ok) return toast(res.error);
    state.me = res.user; renderMe();
  });

  function applyTheme(t) {
    try { t ? localStorage.setItem('theme', t) : localStorage.removeItem('theme'); } catch {}
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    $$('[data-theme-pick] .seg').forEach(s => s.classList.toggle('active', s.dataset.theme === (t || '')));
  }
  $$('[data-theme-pick] .seg').forEach(s => s.addEventListener('click', () => applyTheme(s.dataset.theme)));
  let savedTheme = ''; try { savedTheme = localStorage.getItem('theme') || ''; } catch {}
  applyTheme(savedTheme);

  // Accent colour: applied at once, remembered in this browser, and saved on the account.
  const ACCENTS = ['navy', 'sky', 'red', 'green', 'purple'];
  function applyAccent(a, save) {
    a = ACCENTS.includes(a) ? a : 'navy';
    document.documentElement.dataset.accent = a;
    try { localStorage.setItem('accent', a); } catch {}
    $$('[data-accent-pick] .swatch').forEach(s => s.classList.toggle('active', s.dataset.accent === a));
    if (save && state.me) api('/api/me', { method: 'POST', json: { accent: a } }).then(res => { if (res.ok) state.me = res.user; });
  }
  $$('[data-accent-pick] .swatch').forEach(s => s.addEventListener('click', () => applyAccent(s.dataset.accent, true)));
  let savedAccent = ''; try { savedAccent = localStorage.getItem('accent') || ''; } catch {}
  applyAccent(savedAccent, false);

  // ---------- settings sections ----------
  $$('[data-subnav] button').forEach(b => b.addEventListener('click', () => {
    $$('[data-subnav] button').forEach(x => x.classList.toggle('active', x === b));
    $$('[data-subpanel]').forEach(p => { p.hidden = p.dataset.subpanel !== b.dataset.sub; });
  }));

  // Account preferences (privacy / security): saved on change.
  function fillPrefs() {
    const p = state.me?.prefs || {};
    $$('[data-pref]').forEach(el => {
      const v = p[el.dataset.pref];
      if (el.type === 'checkbox') el.checked = !!v; else el.value = String(v ?? el.value);
    });
  }
  $$('[data-pref]').forEach(el => el.addEventListener('change', async () => {
    const value = el.type === 'checkbox' ? el.checked : el.value;
    const res = await api('/api/me', { method: 'POST', json: { [el.dataset.pref]: value } });
    if (!res.ok) { toast(res.error); fillPrefs(); return; }
    state.me = res.user; toast('Saved');
    if (el.dataset.pref === 'auto_delete_days' && state.view === 'inbox') loadMail();
  }));

  // Compact list (this browser only)
  function applyDensity(on) {
    if (on) document.documentElement.dataset.density = 'compact'; else delete document.documentElement.dataset.density;
    $('[data-density]').checked = on;
    try { localStorage.setItem('density', on ? 'compact' : ''); } catch {}
  }
  $('[data-density]').addEventListener('change', (e) => applyDensity(e.target.checked));
  let savedDensity = ''; try { savedDensity = localStorage.getItem('density') || ''; } catch {}
  applyDensity(savedDensity === 'compact');

  // Notifications (this browser only)
  let notify = { desktop: false, sound: false, title: true };
  try { notify = { ...notify, ...JSON.parse(localStorage.getItem('notify') || '{}') }; } catch {}
  function saveNotify() { try { localStorage.setItem('notify', JSON.stringify(notify)); } catch {} }
  function fillNotify() { $$('[data-notify]').forEach(el => { el.checked = !!notify[el.dataset.notify]; }); }
  $$('[data-notify]').forEach(el => el.addEventListener('change', async () => {
    const key = el.dataset.notify;
    if (key === 'desktop' && el.checked) {
      if (!('Notification' in window)) { toast('This browser cannot show notifications'); el.checked = false; return; }
      const perm = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission();
      if (perm !== 'granted') { toast('Notifications are blocked for this site'); el.checked = false; return; }
    }
    notify[key] = el.checked; saveNotify();
    if (key === 'title') updateTitle();
  }));
  function chime() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'sine'; o.frequency.value = 880; g.gain.value = 0.0001;
      o.connect(g); g.connect(ctx.destination); o.start();
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
      o.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.12);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6);
      o.stop(ctx.currentTime + 0.6);
    } catch {}
  }
  function announce(count) {
    if (notify.sound) chime();
    if (notify.desktop && 'Notification' in window && Notification.permission === 'granted') {
      const n = new Notification('Stego Mail', { body: count === 1 ? 'New message' : `${count} new messages`, icon: '/static/favicon.svg', tag: 'stego-new' });
      n.onclick = () => { window.focus(); showView('inbox'); n.close(); };
    }
  }
  function updateTitle() { document.title = notify.title && state.me && state.unread ? `(${state.unread}) Stego Mail` : 'Stego Mail'; }
  $('[data-notify-test]').addEventListener('click', () => { if (!notify.desktop && !notify.sound) return toast('Turn on a notification first'); announce(1); });

  // Delete account
  $('[data-delete-account]').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    if (!f.password.value) return status(f, 'Enter your password.');
    if (!confirm('Delete your account and everything in it? This cannot be undone.')) return;
    const res = await api('/api/me', { method: 'DELETE', json: { password: f.password.value } });
    if (!res.ok) return status(f, res.error);
    f.reset(); state.me = null; state.items = []; state.selected = null; state.gallery = null;
    showAuth(); toast('Account deleted');
  });

  function fillAbout(res) {
    if (state.me?.created) $('[data-about=created]').textContent = fmtFull(state.me.created).split(',')[0];
    for (const k of ['received', 'sent', 'pictures']) if (res && k in res) $(`[data-about=${k}]`).textContent = res[k];
  }

  // ------------------------------------------------------------ start
  // Every visit starts signed out: end any previous session, then show sign-in.
  (async () => {
    await api('/api/auth/logout', { method: 'POST' });
    showAuth();
  })();
})();
