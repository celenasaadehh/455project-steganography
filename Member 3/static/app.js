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
    concealPasswords(authEl);
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
    requestAnimationFrame(moveNavMarker);
  }

  // A white marker that slides behind the active menu item.
  const nav = $('.nav'), navMarker = document.createElement('span');
  navMarker.className = 'nav-marker'; navMarker.setAttribute('aria-hidden', 'true');
  nav.prepend(navMarker);
  function moveNavMarker() {
    const b = $('button.active', nav);
    navMarker.hidden = !b;
    if (!b) return;
    navMarker.style.transform = `translateY(${b.offsetTop}px)`;
    navMarker.style.height = `${b.offsetHeight}px`;
  }
  new ResizeObserver(moveNavMarker).observe(nav);

  // While a picture is being hidden, coloured "pixels" flicker over the cover.
  function scramble(box) {
    if (reduceMotion || !box) return () => {};
    const c = document.createElement('canvas'), ctx = c.getContext('2d');
    c.className = 'scramble'; box.append(c);
    const rgb = getComputedStyle(document.documentElement).getPropertyValue('--blue-rgb').trim() || '30,79,194';
    const cell = 10;
    let alive = true;
    (function frame() {
      if (!alive) return;
      c.width = box.clientWidth; c.height = box.clientHeight;
      for (let y = 0; y < c.height; y += cell) for (let x = 0; x < c.width; x += cell) {
        const r = Math.random();
        if (r < .55) continue;
        ctx.fillStyle = r > .93 ? 'rgba(255,255,255,.75)' : `rgba(${rgb},${(r - .5).toFixed(2)})`;
        ctx.fillRect(x, y, cell - 1, cell - 1);
      }
      setTimeout(() => requestAnimationFrame(frame), 70);
    })();
    return () => { alive = false; c.classList.add('done'); setTimeout(() => c.remove(), 350); };
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
        if (hide.gallery2 === g.id) selectCover2({});
        if (hide.more.some(m => m.gallery === g.id)) { hide.more = hide.more.filter(m => m.gallery !== g.id); renderMore(); refreshCapacity(); }
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
  const hide = { carrier: 'image', gallery: null, file: null, gallery2: null, file2: null, more: [], cap: null, result: null, urls: [] };

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
  // Clicking the box (or Change) asks where the picture comes from: the gallery or this computer.
  const pickerEl = $('#picker'), pickerGrid = $('[data-picker-grid]');
  function pickerStep(step) {
    $('[data-picker-options]').hidden = step !== 'options';
    pickerGrid.hidden = step !== 'gallery';
    $('[data-picker-back]').hidden = step !== 'gallery';
    $('[data-picker-title]').textContent = step === 'gallery' ? 'Gallery' : 'Choose a picture';
  }
  // The chooser fills either the main picture (1) or, when splitting, the second picture (2).
  let pickFor = 1;
  function openPicker(target = 1) { pickFor = target === 2 || target === 'more' ? target : 1; pickerStep('options'); pickerEl.hidden = false; $('[data-pick="gallery"]').focus(); }
  function closePicker() { pickerEl.hidden = true; }
  async function showPickerGallery() {
    pickerStep('gallery');
    if (!state.gallery && !(await fetchGallery())) { pickerStep('options'); return toast('Could not load the gallery'); }
    pickerGrid.replaceChildren(...state.gallery.map(g => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'tile'; b.title = g.name;
      b.classList.toggle('selected', pickFor !== 'more' && (pickFor === 2 ? hide.gallery2 : hide.gallery) === g.id);
      const im = document.createElement('img'); im.src = g.thumb_url; im.alt = g.name; im.loading = 'lazy';
      const name = document.createElement('span'); name.className = 'tile-name'; name.textContent = g.name;
      b.append(im, name);
      b.addEventListener('click', () => { (pickFor === 'more' ? addMore : pickFor === 2 ? selectCover2 : selectCover)({ gallery: g.id }); closePicker(); });
      return b;
    }));
  }
  coverDrop.addEventListener('click', () => openPicker(1));
  coverDrop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(1); } });
  $('[data-cover-change]').addEventListener('click', () => openPicker(1));
  $('[data-pick="gallery"]').addEventListener('click', showPickerGallery);
  $('[data-pick="computer"]').addEventListener('click', () => { closePicker(); (pickFor === 'more' ? form.more_file : pickFor === 2 ? form.image2 : form.image).click(); });

  // ---------- more pictures: when the message is too long for one picture
  const MAX_PICTURES = 10, PIECE_LABEL = 17;   // each picture also carries a 17-byte label (which piece, of how many)
  function addMore({ gallery = null, file = null }) {
    if (1 + hide.more.length >= MAX_PICTURES) return toast(`Up to ${MAX_PICTURES} pictures`);
    hide.more.push({ gallery, file, url: file ? URL.createObjectURL(file) : null });
    renderMore(); refreshCapacity();
  }
  function renderMore() {
    $('[data-more-list]').replaceChildren(...hide.more.map((m, i) => {
      const g = m.gallery ? (state.gallery || []).find(x => x.id === m.gallery) : null;
      return pictureChip(m.url || g?.thumb_url || g?.url, `Picture ${i + 2}`, g ? g.name : m.file?.name || '', () => {
        if (m.url) URL.revokeObjectURL(m.url);
        hide.more.splice(i, 1); renderMore(); refreshCapacity();
      });
    }));
  }
  function clearMore() { hide.more.forEach(m => m.url && URL.revokeObjectURL(m.url)); hide.more = []; renderMore(); }
  form.more_file.addEventListener('change', () => { [...form.more_file.files].forEach(f => addMore({ file: f })); form.more_file.value = ''; });
  const moreAdd = $('[data-more-add]');
  moreAdd.addEventListener('click', () => openPicker('more'));
  moreAdd.addEventListener('dragover', (e) => { e.preventDefault(); moreAdd.classList.add('over'); });
  moreAdd.addEventListener('dragleave', () => moreAdd.classList.remove('over'));
  moreAdd.addEventListener('drop', (e) => { e.preventDefault(); moreAdd.classList.remove('over'); [...e.dataTransfer.files].forEach(f => addMore({ file: f })); });

  // ---------- second picture (split only)
  let cover2Url = null;
  function selectCover2({ gallery = null, file = null }) {
    hide.gallery2 = gallery; hide.file2 = file;
    if (cover2Url) { URL.revokeObjectURL(cover2Url); cover2Url = null; }
    const g = gallery ? (state.gallery || []).find(x => x.id === gallery) : null;
    const chosen = !!(g || file), im = $('[data-cover2-img]');
    $('[data-cover2-drop]').hidden = chosen; $('[data-cover2-chip]').hidden = !chosen;
    if (file) { cover2Url = URL.createObjectURL(file); im.src = cover2Url; }
    else if (g) im.src = g.thumb_url || g.url;
    else im.removeAttribute('src');
    $('[data-cover2-name]').textContent = g ? g.name : file ? file.name : '';
    form.image2.value = '';
    refreshCapacity();
  }
  form.image2.addEventListener('change', (e) => { const f = e.target.files[0]; if (f) selectCover2({ file: f }); });
  $('[data-cover2-drop]').addEventListener('click', () => openPicker(2));
  $('[data-cover2-change]').addEventListener('click', () => openPicker(2));
  const cover2Drop = $('[data-cover2-drop]');
  cover2Drop.addEventListener('dragover', (e) => { e.preventDefault(); cover2Drop.classList.add('over'); });
  cover2Drop.addEventListener('dragleave', () => cover2Drop.classList.remove('over'));
  cover2Drop.addEventListener('drop', (e) => {
    e.preventDefault(); cover2Drop.classList.remove('over');
    const f = e.dataTransfer.files[0];
    if (f) selectCover2({ file: f });
  });
  $('[data-picker-back]').addEventListener('click', () => pickerStep('options'));
  $('[data-picker-close]').addEventListener('click', closePicker);
  pickerEl.addEventListener('click', (e) => { if (e.target === pickerEl) closePicker(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !pickerEl.hidden) closePicker(); });
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
    if (hide.carrier !== 'image' || (!hide.gallery && !hide.file)) return showMore(false);
    capTimer = setTimeout(async () => {
      const two = form.split.checked && (hide.gallery2 || hide.file2);
      const extra = form.split.checked ? [] : hide.more;
      const key = () => `${hide.gallery}|${hide.file?.name}|${two ? `${hide.gallery2}|${hide.file2?.name}` : ''}|${extra.map(m => m.gallery || m.file?.name).join(',')}|${form.format.value}|${locked()}`;
      const before = key();
      const capOf = (gallery, file) => {
        const fd = new FormData();
        if (gallery) fd.append('gallery', gallery); else fd.append('image', file);
        fd.append('format', form.format.value);
        fd.append('encrypted', locked() ? '1' : '0');   // a password adds a little overhead
        return api('/api/image/capacity', { method: 'POST', body: fd });
      };
      const caps = await Promise.all([capOf(hide.gallery, hide.file), ...(two ? [capOf(hide.gallery2, hide.file2)] : []),
                                      ...extra.map(m => capOf(m.gallery, m.file))]);
      if (key() !== before) return;
      const bad = caps.find(c => !c.ok);
      // splitting: the smaller picture decides; spreading: the pictures add up (less a small label on each)
      hide.cap = bad ? { error: bad.error }
        : two ? { max_message_bytes: Math.min(...caps.map(c => c.max_message_bytes)), can_embed: caps.every(c => c.can_embed) }
        : extra.length ? { max_message_bytes: caps.reduce((t, c) => t + Math.max(0, c.max_message_bytes - PIECE_LABEL), 0), can_embed: caps[0].can_embed, spread: caps.length }
        : { max_message_bytes: caps[0].max_message_bytes, can_embed: caps[0].can_embed };
      renderMeter();
    }, 120);
  }

  function renderMeter() {
    const text = $('[data-meter-text]'), bar = $('[data-meter-bar]'), span = $('span', bar);
    const used = bytes(form.message.value);
    text.classList.remove('over'); bar.classList.remove('over');
    $('[data-tmeter]').hidden = hide.carrier !== 'text';
    if (hide.carrier === 'text') { renderTextMeter(); return showMore(false); }
    if (!hide.gallery && !hide.file) { text.textContent = 'Pick a picture'; span.style.width = '0'; return; }
    if (!hide.cap) { text.textContent = 'Checking…'; span.style.width = '0'; return; }
    if (hide.cap.error) { text.textContent = hide.cap.error; text.classList.add('over'); span.style.width = '0'; return; }
    // a split half carries a 16-byte tag, a self-destruct date 23 bytes
    const extra = (form.split.checked ? 16 : 0) + (locked() && form.expires.value ? 23 : 0);
    const max = Math.max(0, hide.cap.max_message_bytes - extra);
    const over = used > max || !hide.cap.can_embed;
    span.style.width = `${Math.min(100, max ? (used / max) * 100 : 100)}%`;
    text.classList.toggle('over', over); bar.classList.toggle('over', over);
    text.textContent = !hide.cap.can_embed ? 'Picture too small'
      : hide.cap.spread ? `${used.toLocaleString()} / ${max.toLocaleString()} characters · ${hide.cap.spread} pictures`
      : `${used.toLocaleString()} / ${max.toLocaleString()} characters`;
    showMore(over || hide.more.length > 0);
  }
  const TEXT_MAX = 65535;
  function renderTextMeter() {
    const text = $('[data-tmeter-text]'), bar = $('[data-tmeter-bar]'), span = $('span', bar);
    const max = TEXT_MAX - (locked() && form.expires.value ? 23 : 0);
    const used = bytes(form.message.value), over = used > max;
    span.style.width = `${Math.min(100, (used / max) * 100)}%`;
    text.classList.toggle('over', over); bar.classList.toggle('over', over);
    text.textContent = `${used.toLocaleString()} / ${max.toLocaleString()} characters`;
  }
  function showMore(on) {
    $('[data-more]').hidden = !(on && hide.carrier === 'image' && !form.split.checked && (hide.gallery || hide.file));
  }
  form.message.addEventListener('input', renderMeter);
  form.format.addEventListener('change', refreshCapacity);

  const setHideCarrier = carrierSwitch(form, (c) => {
    hide.carrier = c;
    status(form, '');
    renderMeter();
  });

  // ---------- result panel
  function freeUrls() { hide.urls.forEach(u => URL.revokeObjectURL(u)); hide.urls = []; }
  function clearResult() {
    freeUrls(); outViewsOff();
    hide.result = null;
    $('[data-out-result]').hidden = true; $('[data-out-empty]').hidden = false;
  }
  function galleryUrl(id) { return (state.gallery || []).find(g => g.id === id)?.url || null; }

  function showResult(r) {
    freeUrls(); outViewsOff();
    hide.result = r;
    const isImg = r.carrier === 'image';
    $('[data-out-empty]').hidden = true; $('[data-out-result]').hidden = false;
    $('[data-stage="out"]').hidden = !isImg; $('[data-out-text]').hidden = isImg;
    $('[data-xray="out"]').hidden = !isImg; $('[data-show-hidden="out"]').hidden = isImg;
    $('[data-show-hidden="out"]').classList.remove('on');
    $('[data-note="out"]').textContent = '';
    $('[data-out-download]').hidden = !isImg; $('[data-out-copy]').hidden = isImg; $('[data-out-txt]').hidden = isImg;
    $('[data-out-qr]').hidden = isImg;
    $('[data-out-all]').hidden = !(isImg && r.parts.length > 1);
    if (isImg) {
      r.parts.forEach(p => { p.url = URL.createObjectURL(p.blob); hide.urls.push(p.url); if (p.coverUrl?.startsWith('blob:')) hide.urls.push(p.coverUrl); });
      showPart(0);
    } else {
      renderProof(r);
      $('[data-out-text]').textContent = r.text;
      const url = URL.createObjectURL(new Blob([r.text], { type: 'text/plain;charset=utf-8' })); hide.urls.push(url);
      const a = $('[data-out-txt]'); a.href = url; a.download = 'hidden-text.txt';
    }
  }

  // Several pictures (split or spread): arrows on the picture flip through them.
  function showPart(k) {
    const r = hide.result, n = r.parts.length;
    r.at = (k + n) % n;
    const p = r.parts[r.at];
    outViewsOff();
    $('[data-out-img]').src = p.url;
    const orig = $('[data-cmp-orig]');
    if (p.coverUrl) orig.src = p.coverUrl; else orig.removeAttribute('src');
    $('[data-compare]').hidden = $('[data-diff-btn]').hidden = !p.coverUrl;
    renderProof({ ...r, stats: p.stats });
    const many = n > 1;
    $('[data-part-prev]').hidden = $('[data-part-next]').hidden = $('[data-part-count]').hidden = !many;
    $('[data-part-count]').textContent = `${r.at + 1} / ${n}`;
    const dl = $('[data-out-download]'); dl.href = p.url; dl.download = p.name;
    $('[data-dl-label]').textContent = many ? `Download part ${r.at + 1}` : 'Download';
  }
  $('[data-part-prev]').addEventListener('click', () => showPart(hide.result.at - 1));
  $('[data-part-next]').addEventListener('click', () => showPart(hide.result.at + 1));

  // "Download all": one .zip with every part, so the browser asks only once.
  $('[data-out-all]').addEventListener('click', async () => {
    const r = hide.result;
    const zip = await makeZip(await Promise.all(r.parts.map(async p => ({ name: p.name, data: new Uint8Array(await p.blob.arrayBuffer()) }))));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(zip); a.download = `${r.parts[0].name.replace(/(-\d+-of-\d+)?-stego\.\w+$/, '')}-all-parts.zip`;
    hide.urls.push(a.href); a.click();
  });

  // A plain .zip (files stored as they are: pictures are already compressed).
  const CRC_TABLE = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  function crc32(d) { let c = 0xFFFFFFFF; for (let i = 0; i < d.length; i++) c = CRC_TABLE[(c ^ d[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
  async function makeZip(files) {
    const enc = new TextEncoder(), chunks = [], central = [];
    let offset = 0;
    for (const f of files) {
      const name = enc.encode(f.name), crc = crc32(f.data), size = f.data.length;
      const local = new DataView(new ArrayBuffer(30));
      [[0, 0x04034b50, 4], [4, 20, 2], [6, 0x0800, 2], [8, 0, 2], [10, 0, 2], [12, 0x21, 2], [14, crc, 4], [18, size, 4], [22, size, 4], [26, name.length, 2], [28, 0, 2]]
        .forEach(([o, v, w]) => (w === 4 ? local.setUint32(o, v, true) : local.setUint16(o, v, true)));
      chunks.push(local, name, f.data);
      const cen = new DataView(new ArrayBuffer(46));
      [[0, 0x02014b50, 4], [4, 20, 2], [6, 20, 2], [8, 0x0800, 2], [10, 0, 2], [12, 0, 2], [14, 0x21, 2], [16, crc, 4], [20, size, 4], [24, size, 4],
       [28, name.length, 2], [30, 0, 2], [32, 0, 2], [34, 0, 2], [36, 0, 2], [38, 0, 4], [42, offset, 4]]
        .forEach(([o, v, w]) => (w === 4 ? cen.setUint32(o, v, true) : cen.setUint16(o, v, true)));
      central.push(cen, name);
      offset += 30 + name.length + size;
    }
    const cenSize = central.reduce((t, c) => t + c.byteLength, 0);
    const end = new DataView(new ArrayBuffer(22));
    [[0, 0x06054b50, 4], [8, files.length, 2], [10, files.length, 2], [12, cenSize, 4], [16, offset, 4]]
      .forEach(([o, v, w]) => (w === 4 ? end.setUint32(o, v, true) : end.setUint16(o, v, true)));
    return new Blob([...chunks, ...central, end], { type: 'application/zip' });
  }

  // A self-destruct date in the reader's own time, e.g. "28 Nov, 14:05"
  function when(iso) {
    return new Date(iso).toLocaleString(document.documentElement.lang || undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  }

  // ---------- QR code of the text result
  const qrEl = $('#qr');
  $('[data-out-qr]').addEventListener('click', async () => {
    const btn = $('[data-out-qr]');
    busy(btn, true);
    const res = await api('/api/qr', { method: 'POST', json: { text: hide.result.text } });
    busy(btn, false);
    if (!res.ok) return toast(res.error);
    $('[data-qr-img]').src = res.png; $('[data-qr-dl]').href = res.png;
    qrEl.hidden = false;
  });
  $('[data-qr-close]').addEventListener('click', () => { qrEl.hidden = true; });
  qrEl.addEventListener('click', (e) => { if (e.target === qrEl) qrEl.hidden = true; });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') qrEl.hidden = true; });

  // ---------- "did it change?" proof
  function proofItem(value, label) {
    const d = document.createElement('div'); d.className = 'proof-item';
    const b = document.createElement('b'); b.textContent = value;
    const sp = document.createElement('span'); sp.textContent = label;
    d.append(b, sp); return d;
  }
  function pct(x) {   // 0.00012 -> "0.01%", 0.034 -> "3.4%", 0.5 -> "50%"
    const v = x * 100;
    return v === 0 ? '0%' : v < 0.01 ? '<0.01%' : `${v.toFixed(v < 1 ? 2 : v < 10 ? 1 : 0)}%`;
  }
  function renderProof(r) {
    const box = $('[data-proof]'), items = [];
    let verdict = '';
    if (r.carrier === 'image' && r.stats) {
      const { psnr, changed, used, cap } = r.stats;
      if (psnr != null) items.push(proofItem(psnr === Infinity ? 'Identical' : `${psnr.toFixed(1)} dB`, 'picture quality (PSNR)'));
      if (changed != null) items.push(proofItem(pct(changed), r.format === 'JPEG' ? 'of colour values changed' : 'of colour values changed (each by 1)'));
      if (cap) items.push(proofItem(pct(used / cap), "of the picture's space used"));
      if (psnr != null) verdict = psnr >= 40 ? 'Looks identical to the original. Above 40 dB the eye cannot see a difference.'
                                             : 'Close to the original, but small changes may be visible up close.';
    } else if (r.carrier === 'text') {
      items.push(proofItem('Unchanged', 'visible text'));
      items.push(proofItem(`+${(r.text.length - r.cover.length).toLocaleString()}`, 'invisible characters added'));
      verdict = 'Looks exactly like the sentence you wrote.';
    }
    if (r.mode === 'split') items.push(proofItem('2 halves', 'each one alone is random noise'));
    if (r.mode === 'spread') items.push(proofItem(`${r.parts.length} pictures`, 'the message is spread across them'));
    if (r.expires) items.push(proofItem(when(r.expires), 'self-destructs'));
    box.replaceChildren(...items);
    if (verdict) { const v = document.createElement('p'); v.className = 'proof-verdict'; v.textContent = `✓ ${verdict}`; box.append(v); }
    box.hidden = items.length === 0;
  }

  // ---------- Compare (slider) and Changes (map) views of the result picture; one view at a time with X-ray
  const cmp = $('[data-cmp]'), diffCanvas = $('[data-diff]'), outImg = $('[data-out-img]'), cmpOrig = $('[data-cmp-orig]');
  let diffFor = null;
  function outViewsOff() {
    xrayOut.off();
    cmp.hidden = true; $('[data-compare]').classList.remove('on');
    diffCanvas.hidden = true; $('[data-diff-btn]').classList.remove('on');
    $('[data-note="out"]').textContent = '';
  }
  cmpOrig.addEventListener('error', () => { if (cmpOrig.getAttribute('src')) { $('[data-compare]').hidden = $('[data-diff-btn]').hidden = true; } });  // e.g. HEIC
  $('[data-xray="out"]').addEventListener('click', () => {   // X-ray turns the other two views off
    cmp.hidden = true; $('[data-compare]').classList.remove('on');
    diffCanvas.hidden = true; $('[data-diff-btn]').classList.remove('on');
  }, true);
  $('[data-compare]').addEventListener('click', (e) => {
    const btn = e.currentTarget, on = !btn.classList.contains('on');
    outViewsOff();
    if (!on) return;
    btn.classList.add('on'); cmp.hidden = false;
    $('[data-cmp-range]').value = 50; cmp.style.setProperty('--x', '50%');
    $('[data-note="out"]').textContent = 'Drag across the picture';
  });
  $('[data-cmp-range]').addEventListener('input', (e) => cmp.style.setProperty('--x', `${e.target.value}%`));
  function buildDiff() {
    const a = cmpOrig, b = outImg;
    if (!a.naturalWidth || !b.naturalWidth) throw new Error('loading');
    if (a.naturalWidth !== b.naturalWidth || a.naturalHeight !== b.naturalHeight) throw new Error('size');
    const w = b.naturalWidth, h = b.naturalHeight, read = (im) => {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const ctx = c.getContext('2d', { willReadFrequently: true }); ctx.drawImage(im, 0, 0);
      return ctx.getImageData(0, 0, w, h).data;
    };
    const da = read(a), db = read(b);
    diffCanvas.width = w; diffCanvas.height = h;
    const ctx = diffCanvas.getContext('2d');
    ctx.fillStyle = '#0b1220'; ctx.fillRect(0, 0, w, h);
    // one picture pixel is smaller than a screen pixel here, so each change is drawn a little larger to stay visible
    const dot = Math.max(1, Math.ceil(w / Math.max(1, b.getBoundingClientRect().width)));
    ctx.fillStyle = '#5eead4';
    let n = 0;
    for (let i = 0, px = 0; i < da.length; i += 4, px++) {
      if (da[i] !== db[i] || da[i + 1] !== db[i + 1] || da[i + 2] !== db[i + 2]) { n++; ctx.fillRect(px % w, (px / w) | 0, dot, dot); }
    }
    diffFor = b.src;
    return n;
  }
  $('[data-diff-btn]').addEventListener('click', (e) => {
    const btn = e.currentTarget, on = !btn.classList.contains('on');
    outViewsOff();
    if (!on) return;
    let n;
    try { n = diffFor === outImg.src ? hide.result.diffCount : (hide.result.diffCount = buildDiff()); }
    catch (err) { return toast(err.message === 'size' ? 'Cannot compare: the picture was turned when it was loaded' : 'Picture still loading'); }
    btn.classList.add('on'); diffCanvas.hidden = false;
    const total = outImg.naturalWidth * outImg.naturalHeight;
    $('[data-note="out"]').textContent = `${n.toLocaleString()} of ${total.toLocaleString()} pixels changed (${pct(n / total)})`;
  });

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
    if (r.carrier === 'image') {
      const files = r.parts.map(p => new File([p.blob], p.name, { type: p.blob.type }));
      setRevealCarrier('image'); setRevealFile(files[0]);
      if (files.length > 1) addRevealMore(files.slice(1));
    }
    else { setRevealCarrier('text'); rform.text.value = r.text; }
    showView('reveal');
    setTimeout(() => rform.password.focus(), 50);
  });

  // Lock switch: with it off, the message is only hidden, not encrypted.
  function locked() { return form.lock.checked; }
  function applyLock() {
    $('[data-pw-field]').hidden = !locked();
    $('[data-lock-warn]').hidden = locked();
  }
  form.lock.addEventListener('change', () => { applyLock(); refreshCapacity(); });
  function applySplit() {
    $('[data-cover2]').hidden = !form.split.checked;
  }
  form.split.addEventListener('change', () => { applySplit(); refreshCapacity(); });
  form.expires.addEventListener('change', renderMeter);

  function resetHide() {
    form.reset(); concealPasswords(form); pwStrength(); applyLock();
    selectCover({}); selectCover2({}); clearMore(); applySplit();
    setHideCarrier('image');
    clearResult();
    status(form, '');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (hide.carrier === 'image' && !hide.gallery && !hide.file) return status(form, 'Pick a picture.');
    if (hide.carrier === 'image' && form.split.checked && !hide.gallery2 && !hide.file2) return status(form, 'Choose the second picture.');
    if (hide.carrier === 'text' && !form.cover.value.trim()) { form.cover.focus(); return status(form, 'Write the visible text.'); }
    if (!form.message.value.trim()) { form.message.focus(); return status(form, 'Write the secret message.'); }
    if (locked() && !form.password.value) { form.password.focus(); return status(form, 'Enter a password.'); }
    if (locked() && form.password.value.length < 6) { form.password.focus(); return status(form, 'Use a password of at least 6 characters.'); }
    if (hide.carrier === 'text' && bytes(form.message.value) > TEXT_MAX) { form.message.focus(); return status(form, 'The secret message is too long for text mode.'); }

    const fd = new FormData();
    fd.append('message', form.message.value);
    fd.append('carrier', hide.carrier);
    fd.append('lock', locked() ? '1' : '0');
    if (locked()) fd.append('password', form.password.value);
    if (locked() && form.expires.value) fd.append('expires', form.expires.value);
    if (hide.carrier === 'image') {
      fd.append('format', form.format.value);
      if (!form.split.checked && hide.more.length) {
        fd.append('more_count', String(hide.more.length));
        hide.more.forEach((m, i) => { if (m.gallery) fd.append(`gallery_m${i}`, m.gallery); else fd.append(`image_m${i}`, m.file); });
      }
      if (form.split.checked) {
        fd.append('split', '1');
        if (hide.gallery2) fd.append('gallery2', hide.gallery2); else fd.append('image2', hide.file2);
      }
      if (hide.gallery) fd.append('gallery', hide.gallery); else fd.append('image', hide.file);
    } else fd.append('cover', form.cover.value);

    const btn = $('[data-hide-btn]');
    status(form, '');
    busy(btn, true, 'Hiding…');
    const stopScramble = scramble(hide.carrier === 'image' ? $('.cover-preview') : null);
    // the original, kept for Compare / Changes (a gallery picture by its address, an upload as a local copy)
    const coverUrl = hide.carrier !== 'image' ? null
      : hide.file ? URL.createObjectURL(hide.file) : (state.gallery || []).find(g => g.id === hide.gallery)?.url || null;
    let res;
    try { res = await fetch('/api/hide', { method: 'POST', body: fd }); }
    catch { busy(btn, false); stopScramble(); return status(form, 'Cannot reach the server.'); }
    const isFile = res.ok && !(res.headers.get('Content-Type') || '').includes('json');
    if (isFile) {
      const blob = await res.blob();
      busy(btn, false); stopScramble();
      const name = (res.headers.get('Content-Disposition') || '').match(/filename="?([^";]+)"?/)?.[1] || 'stego.png';
      const h = (k) => res.headers.get(k);
      const [used, cap] = (h('X-Stego-Used') || '').split('/').map(Number);
      const stats = { psnr: h('X-Stego-Psnr') == null ? null : h('X-Stego-Psnr') === 'inf' ? Infinity : Number(h('X-Stego-Psnr')),
                      changed: h('X-Stego-Changed') == null ? null : Number(h('X-Stego-Changed')), used, cap };
      showResult({ carrier: 'image', parts: [{ blob, name, stats, coverUrl }], format: fd.get('format'), expires: h('X-Stego-Expires') });
      return toast('Done');
    }
    const data = await readJson(res);
    busy(btn, false); stopScramble();
    if (!data.ok) return status(form, data.error);
    if (data.split || data.chain) {
      // the picture each part was made from, for Compare / Changes
      const covers = [coverUrl, ...(data.split ? [hide.file2 ? URL.createObjectURL(hide.file2) : galleryUrl(hide.gallery2)]
                                               : hide.more.map(m => (m.file ? URL.createObjectURL(m.file) : galleryUrl(m.gallery))))];
      const parts = await Promise.all(data.parts.map(async p => ({
        name: p.name, blob: await (await fetch(p.data)).blob(), coverUrl: covers[p.cover] || null,
        stats: { psnr: p.psnr, changed: p.changed, used: p.used, cap: p.capacity },
      })));
      showResult({ carrier: 'image', parts, mode: data.split ? 'split' : 'spread', format: fd.get('format'), expires: data.expires });
      return toast('Done');
    }
    showResult({ carrier: 'text', text: data.text, cover: fd.get('cover'), expires: data.expires });
    toast('Done');
  });

  // ------------------------------------------------------------ reveal
  const rform = $('[data-reveal]');
  const rev = { carrier: 'image', file: null, url: null, more: [] };

  const setRevealCarrier = carrierSwitch(rform, (c) => { rev.carrier = c; clearSecret(); });

  function clearSecret() {
    decryptRun++; $('[data-secret]').hidden = true; $('[data-secret-note]').hidden = true; status(rform, '');
  }

  // A small row for an extra picture: thumbnail, label, name and a remove button.
  function pictureChip(src, label, name, onRemove) {
    const d = document.createElement('div'); d.className = 'pic-chip';
    const im = document.createElement('img'); im.alt = ''; if (src) im.src = src;
    const t = document.createElement('span');
    const b = document.createElement('b'); b.textContent = label;
    const sm = document.createElement('small'); sm.textContent = name; sm.setAttribute('translate', 'no');
    t.append(b, sm);
    const x = document.createElement('button'); x.type = 'button'; x.className = 'icon-btn'; x.setAttribute('aria-label', 'Remove');
    x.innerHTML = '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>';
    x.addEventListener('click', onRemove);
    d.append(im, t, x);
    return d;
  }

  function setRevealFile(file) {
    if (rev.url) URL.revokeObjectURL(rev.url);
    rev.file = file; rev.url = file ? URL.createObjectURL(file) : null;
    xrayIn.off(); clearSecret();
    $('[data-drop]').hidden = !!file; $('[data-r-box]').hidden = !file;
    const im = $('[data-r-img]');
    if (file) im.src = rev.url; else im.removeAttribute('src');
    setRevealMore([]);
    $('[data-part2]').hidden = !file;    // more pictures can always be added: halves of a split, or pieces of a long message
  }
  // Extra pictures: the other half of a split message, or the other pieces of a spread one.
  function setRevealMore(files) {
    rev.more.forEach(m => URL.revokeObjectURL(m.url));
    rev.more = files.map(f => ({ file: f, url: URL.createObjectURL(f) }));
    renderRevealMore();
  }
  function addRevealMore(files) {
    files.forEach(f => rev.more.push({ file: f, url: URL.createObjectURL(f) }));
    if (files.length) status(rform, '');
    renderRevealMore();
  }
  function renderRevealMore() {
    $('[data-r-more-list]').replaceChildren(...rev.more.map((m, i) => pictureChip(m.url, 'Added picture', m.file.name, () => {
      URL.revokeObjectURL(m.url); rev.more.splice(i, 1); renderRevealMore();
    })));
    if (rev.more.length) $('[data-part2]').hidden = false;
  }
  function takeFiles(files) {
    if (!files.length) return;
    setRevealFile(files[0]);
    if (files.length > 1) addRevealMore(files.slice(1));
  }
  rform.image.addEventListener('change', () => { takeFiles([...rform.image.files]); rform.image.value = ''; });
  rform.image2.addEventListener('change', () => { addRevealMore([...rform.image2.files]); rform.image2.value = ''; });
  $('[data-r-change]').addEventListener('click', () => rform.image.click());
  const drop = $('[data-drop]'), drop2 = $('[data-drop2]');
  for (const [el, take] of [[drop, (fs) => takeFiles(fs)], [drop2, (fs) => addRevealMore(fs)]]) {
    el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('over'); });
    el.addEventListener('dragleave', () => el.classList.remove('over'));
    el.addEventListener('drop', (e) => { e.preventDefault(); el.classList.remove('over'); take([...e.dataTransfer.files]); });
  }

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
    rform.reset(); hiddenViewOff(); concealPasswords(rform);
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
      rev.more.forEach(m => fd.append('more', m.file));
    } else {
      if (!rform.text.value.trim()) { rform.text.focus(); return status(rform, 'Paste the text first.'); }
      fd.append('text', rform.text.value);
    }
    if (rform.password.value) fd.append('password', rform.password.value);   // only locked messages need one
    const btn = $('button[type=submit]', rform);
    clearSecret();
    busy(btn, true, 'Revealing…');
    const res = await api('/api/reveal', { method: 'POST', body: fd });
    busy(btn, false);
    if (!res.ok) {
      if (res.code === 'password') rform.password.focus();
      if (res.code === 'need_part') $('[data-part2]').hidden = false;
      return status(rform, res.error);
    }
    const sec = $('[data-secret]');
    sec.hidden = false;
    decrypt(sec, res.message);
    const note = $('[data-secret-note]');
    note.hidden = !res.expires;
    if (res.expires) note.textContent = `Self-destructs ${when(res.expires)}`;
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

  // Sign-in boxes start read-only so Chrome does not fill them on page load: its
  // on-load fill uses its own smaller font, and the text jumped when clicked.
  // The first press or Tab unlocks the box, and Chrome then offers the saved login.
  $$('[data-nofill]').forEach(i => {
    const unlock = () => { i.readOnly = false; };
    i.addEventListener('pointerdown', unlock);
    i.addEventListener('focus', unlock);
  });

  // ------------------------------------------------------------ password helpers
  // An eye button on every password box, to see what you typed.
  const EYE = '<svg viewBox="0 0 24 24"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg viewBox="0 0 24 24"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.6 10.6 0 0112 5c6 0 10 7 10 7a17 17 0 01-3.2 3.9M6.6 6.6C3.9 8.4 2 12 2 12s4 7 10 7a9.7 9.7 0 004.4-1"/><path d="M9.9 9.9a3 3 0 004.2 4.2"/></svg>';
  function setShown(input, shown) {
    input.type = shown ? 'text' : 'password';
    const b = input.parentElement.querySelector('.pw-eye');
    b.innerHTML = shown ? EYE_OFF : EYE;
    b.setAttribute('aria-label', shown ? 'Hide password' : 'Show password'); b.title = b.getAttribute('aria-label');
  }
  $$('input[type=password]').forEach(input => {
    const wrap = document.createElement('span'); wrap.className = 'pw-wrap';
    input.replaceWith(wrap); wrap.append(input);
    const b = document.createElement('button'); b.type = 'button'; b.className = 'pw-eye'; b.tabIndex = -1;
    wrap.append(b); setShown(input, false);
    b.addEventListener('click', () => { setShown(input, input.type === 'password'); input.focus(); });
  });
  function concealPasswords(root = document) { $$('.pw-wrap > input', root).forEach(i => setShown(i, false)); }

  // Strength bar under the Hide password: length counts most, then the mix of character kinds.
  function strength(pw) {
    if (pw.length < 6) return 0;
    const kinds = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length;
    const weak = /^(.)\1+$/.test(pw) || /^(?:0?123456|password|qwerty|abc123|111111)/i.test(pw);
    let level = 1;
    if (pw.length >= 10 && kinds >= 2) level = 2;
    if (pw.length >= 12 && kinds >= 3) level = 3;
    if (pw.length >= 16 && kinds >= 3) level = 4;
    return weak ? 1 : level;
  }
  function pwStrength() {
    const pw = form.password.value, level = pw ? strength(pw) : 0;
    $('[data-pw-bar]').dataset.level = pw ? Math.max(level, 1) : 0;
    $('[data-pw-label]').textContent = !pw ? '' : ['Too short', 'Weak', 'Fair', 'Good', 'Strong'][level];
  }
  form.password.addEventListener('input', pwStrength);

  // A random 16-character password, without look-alike characters (0/O, 1/l/I).
  function suggestPassword() {
    const chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!#$%&*?@';
    const out = [], buf = new Uint8Array(1);
    while (out.length < 16) {
      crypto.getRandomValues(buf);
      if (buf[0] < 256 - (256 % chars.length)) out.push(chars[buf[0] % chars.length]);   // no bias
    }
    return out.join('');
  }
  $('[data-pw-suggest]').addEventListener('click', async () => {
    const pw = suggestPassword();
    form.password.value = pw; setShown(form.password, true); pwStrength();
    try { await navigator.clipboard.writeText(pw); toast('Copied. Keep it somewhere safe'); }
    catch { toast('Write it down somewhere safe'); }
  });

  // ------------------------------------------------------------ start
  // Every visit starts signed out: end any previous session, then show sign-in.
  (async () => {
    await api('/api/auth/logout', { method: 'POST' });
    showAuth();
  })();
})();
