(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const enc = new TextEncoder();
  const bytes = (s) => enc.encode(s).length;

  const state = { me: null, view: 'hide', gallery: null };
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const authEl = $('#auth'), appEl = $('#app');

  // ------------------------------------------------------------ helpers
  async function api(url, { method = 'GET', body, json } = {}) {
    const opts = { method, headers: {} };
    if (json) { opts.body = JSON.stringify(json); opts.headers['Content-Type'] = 'application/json'; }
    else if (body) opts.body = body;
    let res;
    try { res = await fetch(url, opts); }
    catch { return { ok: false, error: 'Cannot reach the server.' }; }
    return readJson(res);
  }
  async function readJson(res) {
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

  const fmtFull = (s) => new Date(s.replace(' ', 'T') + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });

  // ------------------------------------------------------------ auth
  function showAuthForm(name) {
    ['login', 'register', 'verify'].forEach(n => { $(`#${n}-form`).hidden = n !== name; });
    $(`#${name}-form input:not([type=hidden])`).focus();
  }
  function showAuth() {
    appEl.hidden = true; authEl.hidden = false;
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
    busy(btn, true, url.endsWith('login') ? 'Signing in…' : 'Creating…');
    const res = await api(url, { method: 'POST', json });
    busy(btn, false);
    if (res.code === 'unverified') { form.reset(); return startVerify(res.email, res.mail_sent, res.error); }
    if (!res.ok) return status(form, res.error);
    form.reset();
    if (res.verify) return startVerify(res.email, res.mail_sent);
    enter(res.user);
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
    enter(res.user);
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

  function signedOut() {
    state.me = null; state.gallery = null;
    resetHide(); resetReveal();
    showAuth();
  }
  $$('[data-logout]').forEach(b => b.addEventListener('click', async () => {
    await api('/api/auth/logout', { method: 'POST' });
    signedOut();
  }));

  // ------------------------------------------------------------ app shell
  function enter(user) {
    state.me = user;
    authEl.hidden = true; appEl.hidden = false;
    if (user.accent) applyAccent(user.accent, false);
    renderMe();
    resetHide(); resetReveal();
    showView('hide');
  }

  function renderMe() {
    const u = state.me;
    setAvatar($('.me [data-avatar]'), u);
    setAvatar($('.settings [data-avatar]'), u);
    $('[data-me-name]').textContent = u.name;
    const pf = $('[data-profile-form]');
    pf.first_name.value = u.first_name; pf.last_name.value = u.last_name; pf.handle.value = u.handle;
    fillPrefs(); fillAbout(null); renderWelcome();
  }

  const TITLES = { hide: 'Hide', reveal: 'Reveal', gallery: 'Gallery', tutorial: 'Learn', history: 'History', settings: 'Settings' };
  function showView(name) {
    state.view = name;
    $$('[data-nav]').forEach(b => b.classList.toggle('active', b.dataset.nav === name && b.closest('.nav')));
    $('[data-title]').textContent = TITLES[name];
    const icon = $(`.nav [data-nav="${name}"] svg`);          // same icon as the menu item
    $('[data-title-icon]').replaceChildren(...(icon ? [icon.cloneNode(true)] : []));
    $$('[data-view]').forEach(v => { v.hidden = v.dataset.view !== name; });
    appEl.classList.remove('side-open');
    if (name === 'hide' && !state.gallery) fetchGallery();
    if (name === 'gallery') loadGallery();
    if (name === 'settings') refreshAbout();
  }
  $$('[data-nav]').forEach(b => b.addEventListener('click', () => showView(b.dataset.nav)));
  $$('[data-go]').forEach(b => b.addEventListener('click', () => showView(b.dataset.go)));
  $('[data-menu]').addEventListener('click', () => appEl.classList.toggle('side-open'));
  $('.main').addEventListener('click', (e) => { if (appEl.classList.contains('side-open') && !e.target.closest('.menu')) appEl.classList.remove('side-open'); });

  const TIPS = [
    'Share pictures as files, not photos: apps that shrink photos erase the hidden message.',
    'Share the password another way, like a phone call.',
    'PNG holds the most. JPEG holds less but survives a re-save.',
    'Text mode hides your secret in invisible characters inside a normal sentence.',
    'Add your own pictures in Gallery to use them again and again.',
  ];
  function renderWelcome() {
    const hour = new Date().getHours();
    const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    $('[data-hello]').textContent = `${greet}, ${state.me.first_name}`;
    $('[data-tip]').textContent = TIPS[Math.floor(Math.random() * TIPS.length)];
  }

  // Image / Text switch, shared by the Hide and Reveal forms
  function carrierSwitch(form, onChange) {
    const set = (c) => {
      $$('[data-carrier]', form).forEach(x => x.classList.toggle('active', x.dataset.carrier === c));
      $$('[data-carrier-pane]', form).forEach(p => { p.hidden = p.dataset.carrierPane !== c; });
      onChange(c);
    };
    $$('[data-carrier]', form).forEach(b => b.addEventListener('click', () => set(b.dataset.carrier)));
    return set;
  }

  // ------------------------------------------------------------ the secret "decrypts" into place
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

  // ------------------------------------------------------------ X-ray lens
  // Magnifies the lowest bit of every colour value, the layer where an image
  // message lives. Busy areas look like static. One lens per picture stage.
  function makeXray(key) {
    const stage = $(`[data-stage="${key}"]`), img = $('img', stage), lens = $('.lens', stage);
    const btn = $(`[data-xray="${key}"]`), note = $(`[data-note="${key}"]`);
    let lsb = null, lsbFor = null;
    function off() {
      lens.hidden = true; btn.classList.remove('on'); stage.classList.remove('xray'); note.textContent = '';
    }
    function build() {
      if (lsb && lsbFor === img.src) return lsb;
      const w = img.naturalWidth, h = img.naturalHeight;
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, w, h), d = data.data;
      for (let i = 0; i < d.length; i += 4) {
        d[i] = (d[i] & 1) * 255; d[i + 1] = (d[i + 1] & 1) * 255; d[i + 2] = (d[i + 2] & 1) * 255; d[i + 3] = 255;
      }
      ctx.putImageData(data, 0, 0);
      lsb = c; lsbFor = img.src;
      return c;
    }
    function box() {   // where the picture is drawn inside the <img> (object-fit: contain)
      const r = img.getBoundingClientRect(), nw = img.naturalWidth, nh = img.naturalHeight;
      const k = Math.min(r.width / nw, r.height / nh);
      return { r, k, x: r.left + (r.width - nw * k) / 2, y: r.top + (r.height - nh * k) / 2, w: nw * k, h: nh * k };
    }
    function draw(cx, cy) {
      const b = box(), dpr = devicePixelRatio || 1, R = 74, zoom = 3;
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
    btn.addEventListener('click', () => {
      if (!lens.hidden) return off();
      if (!img.complete || !img.naturalWidth) return toast('Image still loading');
      try { build(); } catch { return toast('X-ray is not available for this image'); }
      lens.hidden = false; btn.classList.add('on'); stage.classList.add('xray');
      note.textContent = 'Move over the picture';
      const b = box(); draw(b.x + b.w / 2, b.y + b.h / 2);
    });
    stage.addEventListener('pointermove', (e) => { if (!lens.hidden) draw(e.clientX, e.clientY); });
    stage.addEventListener('pointerdown', (e) => { if (!lens.hidden) draw(e.clientX, e.clientY); });
    stage.addEventListener('pointerleave', (e) => { if (!lens.hidden && e.pointerType === 'mouse') lens.getContext('2d').clearRect(0, 0, lens.width, lens.height); });
    return { off };
  }
  const xrayOut = makeXray('out'), xrayIn = makeXray('in');

  // ------------------------------------------------------------ Show hidden
  // A text's invisible characters, drawn as a colour barcode.
  // Member 2's characters (U+200B, U+200C, U+2060, U+2063), plus U+200D from the website's first format
  const ZW = { '​': 0, '‌': 1, '⁠': 2, '⁣': 3, '‍': 3 };
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
  const perByte = (text) => { const run = (text.match(/[​‌‍⁠⁣]{8,}/) || [''])[0]; return /[‌⁣‍]/.test(run) ? 4 : 8; };
  const hiddenNote = (n, text) => (n ? `${n} invisible characters · ${Math.round(n / perByte(text))} bytes` : 'None found');

  // ------------------------------------------------------------ gallery
  async function fetchGallery() {
    const res = await api('/api/gallery');
    if (!res.ok) return false;
    state.gallery = res.items;
    return true;
  }

  async function loadGallery() {
    if (!state.gallery && !(await fetchGallery())) return;
    renderGallery();
  }

  function renderGallery() {
    const grid = $('[data-gallery-grid]');
    $$('.gtile:not(.gadd)', grid).forEach(t => t.remove());
    const tpl = $('#tpl-gallery').content;
    const addTile = $('.gadd', grid);
    for (const g of state.gallery) {
      const t = tpl.firstElementChild.cloneNode(true);
      t.dataset.id = g.id;
      $('img', t).src = g.thumb_url; $('img', t).alt = g.name;
      $('.gname', t).textContent = g.name;
      t.title = 'Hide in this picture';
      const pick = () => { showView('hide'); setHideCarrier('image'); selectCover({ gallery: g.id }); };
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
        if (hide.gallery === g.id) selectCover({});
        renderGallery(); toast('Removed');
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
    renderGallery();
    toast(`Added "${res.item.name}"`);
  });

  // ------------------------------------------------------------ hide
  const form = $('[data-hide]');
  const hide = { carrier: 'image', gallery: null, file: null, cap: null, result: null, urls: [] };

  // One big upload box. A picture chosen in Gallery shows up in the same box.
  const coverImg = $('[data-cover-img]'), coverDrop = $('[data-cover-drop]');
  let coverUrl = null;
  function selectCover({ gallery = null, file = null }) {
    hide.gallery = gallery; hide.file = file;
    if (coverUrl) { URL.revokeObjectURL(coverUrl); coverUrl = null; }
    const g = gallery ? (state.gallery || []).find(x => x.id === gallery) : null;
    const chosen = !!(g || file);
    coverDrop.hidden = chosen; $('[data-cover-box]').hidden = !chosen;
    coverImg.hidden = false;
    if (file) { coverUrl = URL.createObjectURL(file); coverImg.src = coverUrl; }
    else if (g) coverImg.src = g.url;
    else coverImg.removeAttribute('src');
    $('[data-cover-name]').textContent = g ? g.name : file ? file.name : '';
    form.image.value = '';
    refreshCapacity();
  }
  coverImg.addEventListener('error', () => { if (coverImg.getAttribute('src')) coverImg.hidden = true; });  // e.g. HEIC: no preview, name only
  form.image.addEventListener('change', (e) => { const f = e.target.files[0]; if (f) selectCover({ file: f }); });
  $('[data-cover-change]').addEventListener('click', () => form.image.click());
  coverDrop.addEventListener('dragover', (e) => { e.preventDefault(); coverDrop.classList.add('over'); });
  coverDrop.addEventListener('dragleave', () => coverDrop.classList.remove('over'));
  coverDrop.addEventListener('drop', (e) => {
    e.preventDefault(); coverDrop.classList.remove('over');
    const f = e.dataTransfer.files[0];
    if (f) selectCover({ file: f });
  });

  let capTimer;
  function refreshCapacity() {
    hide.cap = null; renderMeter();
    clearTimeout(capTimer);
    if (hide.carrier !== 'image' || (!hide.gallery && !hide.file)) return;
    capTimer = setTimeout(async () => {
      const key = () => `${hide.gallery}|${hide.file?.name}|${form.format.value}`;
      const before = key();
      const fd = new FormData();
      if (hide.gallery) fd.append('gallery', hide.gallery); else fd.append('image', hide.file);
      fd.append('format', form.format.value);
      fd.append('encrypted', '1');   // a password is always used
      const res = await api('/api/image/capacity', { method: 'POST', body: fd });
      if (key() !== before) return;
      hide.cap = res.ok ? res : { error: res.error };
      renderMeter();
    }, 120);
  }

  function renderMeter() {
    const text = $('[data-meter-text]'), bar = $('[data-meter-bar]'), span = $('span', bar);
    const used = bytes(form.message.value);
    text.classList.remove('over'); bar.classList.remove('over');
    if (hide.carrier === 'text') return;
    if (!hide.gallery && !hide.file) { text.textContent = 'Pick a picture'; span.style.width = '0'; return; }
    if (!hide.cap) { text.textContent = 'Checking…'; span.style.width = '0'; return; }
    if (hide.cap.error) { text.textContent = hide.cap.error; text.classList.add('over'); span.style.width = '0'; return; }
    const max = hide.cap.max_message_bytes;
    const over = used > max || !hide.cap.can_embed;
    span.style.width = `${Math.min(100, max ? (used / max) * 100 : 100)}%`;
    text.classList.toggle('over', over); bar.classList.toggle('over', over);
    text.textContent = !hide.cap.can_embed ? 'Picture too small' : `${used.toLocaleString()} / ${max.toLocaleString()} characters`;
  }
  form.message.addEventListener('input', renderMeter);
  form.format.addEventListener('change', refreshCapacity);

  const setHideCarrier = carrierSwitch(form, (c) => {
    hide.carrier = c;
    $('[data-hide-btn]').textContent = c === 'image' ? 'Hide and download' : 'Hide';
    renderMeter();
  });

  // ---------- result panel
  function freeUrls() { hide.urls.forEach(u => URL.revokeObjectURL(u)); hide.urls = []; }
  function clearResult() {
    freeUrls(); xrayOut.off();
    hide.result = null;
    $('[data-out-result]').hidden = true; $('[data-out-empty]').hidden = false;
  }
  function showResult(r) {
    freeUrls(); xrayOut.off();
    hide.result = r;
    const isImg = r.carrier === 'image';
    $('[data-out-empty]').hidden = true; $('[data-out-result]').hidden = false;
    $('[data-stage="out"]').hidden = !isImg; $('[data-out-text]').hidden = isImg;
    $('[data-xray="out"]').hidden = !isImg; $('[data-show-hidden="out"]').hidden = isImg;
    $('[data-show-hidden="out"]').classList.remove('on');
    $('[data-note="out"]').textContent = '';
    $('[data-out-download]').hidden = !isImg; $('[data-out-copy]').hidden = isImg; $('[data-out-txt]').hidden = isImg;
    if (isImg) {
      const url = URL.createObjectURL(r.blob); hide.urls.push(url);
      $('[data-out-img]').src = url;
      const dl = $('[data-out-download]'); dl.href = url; dl.download = r.name;
      dl.click();   // the picture downloads straight away; the button is there to save it again
    } else {
      $('[data-out-text]').textContent = r.text;
      const url = URL.createObjectURL(new Blob([r.text], { type: 'text/plain;charset=utf-8' })); hide.urls.push(url);
      const a = $('[data-out-txt]'); a.href = url; a.download = 'hidden-text.txt';
    }
  }

  $('[data-show-hidden="out"]').addEventListener('click', (e) => {
    const btn = e.currentTarget, pre = $('[data-out-text]'), text = hide.result?.text;
    if (text == null) return;
    if (btn.classList.toggle('on')) $('[data-note="out"]').textContent = hiddenNote(renderHidden(pre, text), text);
    else { pre.textContent = text; $('[data-note="out"]').textContent = ''; }
  });
  $('[data-out-copy]').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(hide.result.text); toast('Copied'); }
    catch { toast('Select the text and press Ctrl+C'); }
  });
  $('[data-out-try]').addEventListener('click', () => {
    const r = hide.result;
    if (!r) return;
    resetReveal();
    if (r.carrier === 'image') { setRevealCarrier('image'); setRevealFile(new File([r.blob], r.name, { type: r.blob.type })); }
    else { setRevealCarrier('text'); rform.text.value = r.text; }
    showView('reveal');
    setTimeout(() => rform.password.focus(), 50);
  });

  function resetHide() {
    form.reset();
    selectCover({});
    setHideCarrier('image');
    clearResult();
    status(form, '');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (hide.carrier === 'image' && !hide.gallery && !hide.file) return status(form, 'Pick a picture.');
    if (hide.carrier === 'text' && !form.cover.value.trim()) { form.cover.focus(); return status(form, 'Write the visible text.'); }
    if (!form.message.value.trim()) { form.message.focus(); return status(form, 'Write the secret message.'); }
    if (!form.password.value) { form.password.focus(); return status(form, 'Enter a password.'); }
    if (form.password.value.length < 6) { form.password.focus(); return status(form, 'Use a password of at least 6 characters.'); }

    const fd = new FormData();
    fd.append('message', form.message.value);
    fd.append('carrier', hide.carrier);
    fd.append('password', form.password.value);
    if (hide.carrier === 'image') {
      fd.append('format', form.format.value);
      if (hide.gallery) fd.append('gallery', hide.gallery); else fd.append('image', hide.file);
    } else fd.append('cover', form.cover.value);

    const btn = $('[data-hide-btn]');
    status(form, '');
    busy(btn, true, 'Hiding…');
    let res;
    try { res = await fetch('/api/hide', { method: 'POST', body: fd }); }
    catch { busy(btn, false); return status(form, 'Cannot reach the server.'); }
    const isFile = res.ok && !(res.headers.get('Content-Type') || '').includes('json');
    if (isFile) {
      const blob = await res.blob();
      busy(btn, false);
      const name = (res.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/)?.[1] || 'stego.png';
      showResult({ carrier: 'image', blob, name });
      return toast('Downloaded');
    }
    const data = await readJson(res);
    busy(btn, false);
    if (!data.ok) return status(form, data.error);
    showResult({ carrier: 'text', text: data.text });
    toast('Done');
  });

  // ------------------------------------------------------------ reveal
  const rform = $('[data-reveal]');
  const rev = { carrier: 'image', file: null, url: null };

  const setRevealCarrier = carrierSwitch(rform, (c) => { rev.carrier = c; clearSecret(); });

  function clearSecret() { decryptRun++; $('[data-secret]').hidden = true; status(rform, ''); }

  function setRevealFile(file) {
    if (rev.url) URL.revokeObjectURL(rev.url);
    rev.file = file; rev.url = file ? URL.createObjectURL(file) : null;
    xrayIn.off(); clearSecret();
    $('[data-drop]').hidden = !!file; $('[data-r-box]').hidden = !file;
    const im = $('[data-r-img]');
    if (file) im.src = rev.url; else im.removeAttribute('src');
  }
  rform.image.addEventListener('change', () => { if (rform.image.files[0]) setRevealFile(rform.image.files[0]); rform.image.value = ''; });
  $('[data-r-change]').addEventListener('click', () => rform.image.click());
  const drop = $('[data-drop]');
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault(); drop.classList.remove('over');
    const f = e.dataTransfer.files[0];
    if (f) setRevealFile(f);
  });

  // Show hidden on the pasted text: swap the box for the barcode view while on
  const showIn = $('[data-show-hidden="in"]'), rText = $('[data-r-text]');
  function hiddenViewOff() { showIn.classList.remove('on'); rText.hidden = true; rform.text.hidden = false; $('[data-note="in-text"]').textContent = ''; }
  showIn.addEventListener('click', () => {
    if (showIn.classList.contains('on')) return hiddenViewOff();
    const text = rform.text.value;
    if (!text) return toast('Paste the text first');
    showIn.classList.add('on'); rform.text.hidden = true; rText.hidden = false;
    $('[data-note="in-text"]').textContent = hiddenNote(renderHidden(rText, text), text);
  });
  rText.addEventListener('click', hiddenViewOff);
  rform.text.addEventListener('input', clearSecret);

  function resetReveal() {
    rform.reset(); hiddenViewOff();
    setRevealFile(null);
    setRevealCarrier('image');
  }

  rform.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append('carrier', rev.carrier);
    if (rev.carrier === 'image') {
      if (!rev.file) return status(rform, 'Choose a picture first.');
      fd.append('image', rev.file);
    } else {
      if (!rform.text.value.trim()) { rform.text.focus(); return status(rform, 'Paste the text first.'); }
      fd.append('text', rform.text.value);
    }
    if (!rform.password.value) { rform.password.focus(); return status(rform, 'Enter the password.'); }
    fd.append('password', rform.password.value);
    const btn = $('button[type=submit]', rform);
    clearSecret();
    busy(btn, true, 'Revealing…');
    const res = await api('/api/reveal', { method: 'POST', body: fd });
    busy(btn, false);
    if (!res.ok) { if (res.code === 'password') rform.password.focus(); return status(rform, res.error); }
    const sec = $('[data-secret]');
    sec.hidden = false;
    decrypt(sec, res.message);
    if (rev.carrier === 'image' && !reduceMotion) {
      const st = $('[data-stage="in"]');
      st.classList.remove('scanning'); void st.offsetWidth; st.classList.add('scanning');
    }
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
  // The square stage is what gets saved; the circle shows the profile picture.
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

  // Account preferences: saved on change.
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
  }));

  // Delete account
  $('[data-delete-account]').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    if (!f.password.value) return status(f, 'Enter your password.');
    if (!confirm('Delete your account and everything in it? This cannot be undone.')) return;
    const res = await api('/api/me', { method: 'DELETE', json: { password: f.password.value } });
    if (!res.ok) return status(f, res.error);
    f.reset();
    signedOut(); toast('Account deleted');
  });

  function fillAbout(res) {
    if (state.me?.created) $('[data-about=created]').textContent = fmtFull(state.me.created).split(',')[0];
    if (res && 'pictures' in res) $('[data-about=pictures]').textContent = res.pictures;
  }
  async function refreshAbout() {
    const res = await api('/api/me');
    if (res.ok && res.user) fillAbout(res);
  }

  // ------------------------------------------------------------ start
  // Every visit starts signed out: end any previous session, then show sign-in.
  (async () => {
    await api('/api/auth/logout', { method: 'POST' });
    showAuth();
  })();
})();
