// Servidor de la lista: guarda el token de GitHub en secreto (variable GH_TOKEN en Netlify).
const REPO = process.env.GH_REPO || 'albertoarchive/lista';
const LISTS = ['alberto', 'elena', 'mama', 'papa'];
const API = 'https://api.github.com/repos/' + REPO + '/contents/';

const gh = (path, opts = {}) => fetch(API + path, {
  ...opts,
  headers: { Authorization: 'Bearer ' + process.env.GH_TOKEN, Accept: 'application/vnd.github+json',
    'Content-Type': 'application/json', 'User-Agent': 'lista' }
});
const out = (code, body) => ({ statusCode: code, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }, body: JSON.stringify(body) });

async function readList(id) {
  const r = await gh('listas/' + id + '.json?ref=main&t=' + Date.now());
  if (!r.ok) throw new Error('lectura ' + r.status);
  const j = await r.json();
  return { sha: j.sha, items: JSON.parse(Buffer.from(j.content, 'base64').toString('utf8')) };
}
async function writeList(id, mutate, msg) {
  for (let i = 0; i < 4; i++) {
    const { sha, items } = await readList(id);
    const next = mutate(items);
    const r = await gh('listas/' + id + '.json', { method: 'PUT', body: JSON.stringify({
      message: msg, branch: 'main', sha,
      content: Buffer.from(JSON.stringify(next, null, 2) + '\n').toString('base64') }) });
    if (r.ok) return next;
    if (r.status !== 409 && r.status !== 422) throw new Error('escritura ' + r.status);
  }
  throw new Error('conflicto, inténtalo de nuevo');
}

const str = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
const url = v => { v = str(v, 2000); return /^https?:\/\//i.test(v) ? v : ''; };
const pic = v => { v = str(v, 2000); return /^https?:\/\//i.test(v) || /^fotos\/[\w.-]+$/.test(v) ? v : ''; };
const price = v => { const n = Number(v); return isFinite(n) && n > 0 && n < 100000 ? n : undefined; };
function clean(it) {
  it = it || {};
  const o = { n: str(it.n, 200) };
  if (!o.n) return null;
  const p = price(it.p), po = price(it.po);
  if (p !== undefined) o.p = p;
  if (po !== undefined) o.po = po;
  const l = url(it.l), img = pic(it.img), img2 = pic(it.img2), note = str(it.o, 300);
  if (l) o.l = l; if (img) o.img = img; if (img2) o.img2 = img2; if (note) o.o = note;
  return o;
}

exports.handler = async (ev) => {
  try {
    if (!process.env.GH_TOKEN) return out(500, { error: 'Falta GH_TOKEN en Netlify' });
    if (ev.httpMethod === 'GET') {
      const id = (ev.queryStringParameters || {}).lista;
      if (!LISTS.includes(id)) return out(400, { error: 'lista' });
      return out(200, (await readList(id)).items);
    }
    if (ev.httpMethod !== 'POST') return out(405, { error: 'método' });
    const b = JSON.parse(ev.body || '{}');
    if (b.op === 'photo') {
      const d = str(b.data, 2500000);
      if (!d.startsWith('/9j/')) return out(400, { error: 'foto no válida' });
      const name = 'fotos/w' + Date.now() + Math.floor(Math.random() * 1000) + '.jpg';
      const r = await gh(name, { method: 'PUT', body: JSON.stringify({ message: 'Sube foto', content: d, branch: 'main' }) });
      if (!r.ok) return out(502, { error: 'foto ' + r.status });
      return out(200, { path: name });
    }
    if (!LISTS.includes(b.lista)) return out(400, { error: 'lista' });
    if (b.op === 'link') {
      const u = url(b.url);
      if (!u) return out(400, { error: 'enlace' });
      const name = 'pedidos/' + Date.now() + Math.floor(Math.random() * 1000) + '.json';
      const r = await gh(name, { method: 'PUT', body: JSON.stringify({ message: 'Pedido: ' + u.slice(0, 80), branch: 'main',
        content: Buffer.from(JSON.stringify({ lista: b.lista, url: u })).toString('base64') }) });
      if (!r.ok) return out(502, { error: 'pedido ' + r.status });
      return out(200, { ok: true });
    }
    if (b.op === 'add') {
      const it = clean(b.item); if (!it) return out(400, { error: 'datos' });
      return out(200, await writeList(b.lista, a => a.concat([it]), 'Añade ' + it.n));
    }
    if (b.op === 'update' || b.op === 'remove') {
      const i = Number(b.index), nm = str(b.name, 200);
      const it = b.op === 'update' ? clean(b.item) : {};
      if (!it) return out(400, { error: 'datos' });
      return out(200, await writeList(b.lista, a => {
        if (!a[i] || a[i].n !== nm) throw new Error('La lista ha cambiado, recarga');
        if (b.op === 'remove') return a.filter((_, k) => k !== i);
        return a.map((x, k) => (k === i ? it : x));
      }, (b.op === 'update' ? 'Edita ' : 'Elimina ') + nm));
    }
    return out(400, { error: 'op' });
  } catch (e) { return out(500, { error: String(e.message || e) }); }
};
