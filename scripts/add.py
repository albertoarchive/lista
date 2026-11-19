#!/usr/bin/env python3
"""Lee los enlaces pendientes en pedidos/*.json y los añade a listas/<lista>.json."""
import glob, json, os, re, sys, html as H
import urllib.request, urllib.parse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"

def get(url, accept="text/html,application/xhtml+xml,*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

def num(s):
    if s is None: return None
    s = str(s).strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s: return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try: return float(s)
    except ValueError: return None

def clean_name(s):
    s = urllib.parse.unquote(s or "")
    s = re.sub(r"\.[a-z0-9]{3,4}$", "", s, flags=re.I)
    s = re.sub(r"[-_]+\d{5,}$", "", s)
    return re.sub(r"[-_]+", " ", s).strip()

def absu(u, base):
    if not u: return ""
    if u.startswith("//"): u = "https:" + u
    return urllib.parse.urljoin(base, H.unescape(u))

def img_key(u):
    p = urllib.parse.urlsplit(u)
    return p.netloc + re.sub(r"[-_]\d+x\d*(?=\.)|_\d+x(?=\.)", "", p.path)

def uniq_imgs(lst):
    out, seen = [], set()
    for u in lst:
        if not u or not u.startswith("http"): continue
        k = img_key(u)
        if k in seen: continue
        seen.add(k); out.append(u)
    return out


def turbo(doc):
    """Decodifica los datos embebidos (React Router / turbo-stream) si existen."""
    m = re.search(r'streamController\.enqueue\((".*?")\);?</script>', doc, re.S)
    if not m: return None
    try: arr = json.loads(json.loads(m.group(1)))
    except Exception: return None
    memo = {}
    def res(i, depth=0):
        if not isinstance(i, int) or i < 0: return None
        if i in memo: return memo[i]
        if depth > 60 or i >= len(arr): return None
        v = arr[i]
        if isinstance(v, dict):
            out = memo[i] = {}
            for k, x in v.items():
                if k.startswith("_") and k[1:].isdigit():
                    kk = arr[int(k[1:])]
                    out[kk if isinstance(kk, str) else str(kk)] = res(x, depth + 1)
        elif isinstance(v, list):
            out = memo[i] = []
            for x in v: out.append(res(x, depth + 1))
        else:
            out = memo[i] = v
        return out
    return res(0)

def find_product(o, depth=0):
    if depth > 40: return None
    if isinstance(o, dict):
        vs = o.get("variants")
        if (isinstance(vs, list) and vs and isinstance(vs[0], dict) and "price" in vs[0]) or "compareAtPriceRange" in o:
            return o
        for v in o.values():
            r = find_product(v, depth + 1)
            if r: return r
    elif isinstance(o, list):
        for v in o:
            r = find_product(v, depth + 1)
            if r: return r
    return None

def money(x):
    if isinstance(x, dict):
        for k in ("amount", "value", "price"):
            if k in x: return num(x[k])
        for v in x.values():
            r = money(v)
            if r: return r
        return None
    return num(x)

def shopify(url):
    u = urllib.parse.urlsplit(url)
    m = re.search(r"/products?/([^/?#]+)", u.path)
    if not m: return None
    handle = m.group(1)
    q = urllib.parse.parse_qs(u.query)
    for path in (re.sub(r"/products?/.*", "", u.path) + "/products/" + handle, "/products/" + handle):
        try:
            t = get(f"{u.scheme}://{u.netloc}{path}.js", "application/json")
            if not t.lstrip().startswith("{"): continue
            j = json.loads(t)
        except Exception:
            continue
        vs = j.get("variants") or []
        v = next((x for x in vs if str(x.get("id")) == (q.get("variant") or [""])[0]), vs[0] if vs else {})
        price = (v.get("price", j.get("price")) or 0) / 100
        cmp_ = v.get("compare_at_price") or j.get("compare_at_price")
        cmp_ = cmp_ / 100 if cmp_ else None
        imgs = uniq_imgs([absu(i, url) for i in (j.get("images") or [])])
        return {"n": j.get("title", ""), "p": price or None, "po": cmp_ if cmp_ and cmp_ > price else None,
                "img": imgs[0] if imgs else "", "img2": imgs[1] if len(imgs) > 1 else ""}
    return None

def find_type(o, t):
    if isinstance(o, list):
        for x in o:
            r = find_type(x, t)
            if r: return r
    elif isinstance(o, dict):
        ty = o.get("@type")
        if ty == t or (isinstance(ty, list) and t in ty): return o
        for v in o.values():
            if isinstance(v, (dict, list)):
                r = find_type(v, t)
                if r: return r
    return None

def meta(doc, *names):
    for n in names:
        for pat in (r'<meta[^>]+(?:property|name|itemprop)=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(n),
                    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name|itemprop)=["\']%s["\']' % re.escape(n)):
            m = re.search(pat, doc, re.I)
            if m and m.group(1).strip(): return H.unescape(m.group(1).strip())
    return ""

def page(url):
    doc = get(url)
    n = p = po = None
    imgs = []
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
        try: data = json.loads(blk)
        except Exception: continue
        pr = find_type(data, "Product")
        if not pr: continue
        n = n or pr.get("name")
        im = pr.get("image")
        if isinstance(im, str): imgs.append(im)
        elif isinstance(im, list): imgs += [i if isinstance(i, str) else (i or {}).get("url", "") for i in im]
        elif isinstance(im, dict): imgs.append(im.get("url", ""))
        of = pr.get("offers")
        if isinstance(of, list): of = of[0] if of else None
        if isinstance(of, dict):
            p = p or num(of.get("price") or of.get("lowPrice"))
            for ps in (of.get("priceSpecification") if isinstance(of.get("priceSpecification"), list) else [of.get("priceSpecification") or {}]):
                if isinstance(ps, dict) and "List" in str(ps.get("priceType", "")): po = po or num(ps.get("price"))
    n = n or meta(doc, "og:title", "twitter:title") or (re.search(r"<title>(.*?)</title>", doc, re.S | re.I) or [None, ""])[1]
    n = re.sub(r"\s+[-|–—·]\s+(Sitio web oficial|Official (Web)?[Ss]ite|Tienda oficial).*$", "", H.unescape(n or "").strip())
    p = p or num(meta(doc, "product:price:amount", "og:price:amount", "price"))
    po = po or num(meta(doc, "product:original_price:amount", "og:price:standard_amount"))
    if not p:  # busca "89,00 €" cerca de la etiqueta de precio
        m = re.search(r'class="[^"]*price[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([\d.,]+)\s*(?:€|&euro;|EUR)', doc, re.I)
        if m: p = num(m.group(1))
    if not po:
        m = re.search(r'<(?:s|del|strike)(?=[\s>])[^>]*>\s*(?:<[^>]+>\s*)*([\d.,]+)\s*(?:€|&euro;|EUR)', doc, re.I)
        if m: po = num(m.group(1))
    if not imgs:
        imgs = [meta(doc, "og:image", "twitter:image")]
    imgs = [absu(i, url) for i in imgs]
    if len(uniq_imgs(imgs)) < 2:  # cdn de producto en el HTML
        imgs += [absu(i, url) for i in re.findall(r'(?:https?:)?//cdn\.shopify\.com/[^"\'\s>]+?\.(?:jpe?g|png|webp)[^"\'\s>]*', doc)]
    imgs = uniq_imgs(imgs)
    if po and p and po <= p: po = None
    return {"n": n, "p": p, "po": po, "img": imgs[0] if imgs else "", "img2": imgs[1] if len(imgs) > 1 else ""}

def read(url):
    u = urllib.parse.urlsplit(url)
    if re.search(r"\.(jpe?g|png|webp|avif|gif)$", u.path, re.I):
        base = {"n": clean_name(u.path.split("/")[-1]), "p": None, "po": None, "img": f"{u.scheme}://{u.netloc}{u.path}", "img2": ""}
        h = re.sub(r"\s+", "-", base["n"])
        s = None
        try: s = shopify(f"{u.scheme}://{u.netloc}/products/{h}")
        except Exception: pass
        return s or base
    res = None
    try: res = shopify(url)
    except Exception as e: print("shopify:", e)
    if not (res and res["n"] and res["p"]):
        try:
            g = page(url)
            if res:
                for k, v in g.items():
                    if not v and res.get(k): g[k] = res[k]
            res = g if (g["n"] or g["img"]) else res
        except Exception as e: print("page:", e)
    if not res or not res.get("n"):
        m = re.search(r"/products?/([^/?#]+)", u.path)
        slug = clean_name(m.group(1) if m else u.path.rstrip("/").split("/")[-1])
        res = {"n": slug or u.netloc, "p": None, "po": None, "img": "", "img2": ""}
    return res

def main():
    for f in sorted(glob.glob("pedidos/*.json")):
        try: ped = json.load(open(f))
        except Exception: os.remove(f); continue
        lst, url = ped.get("lista"), ped.get("url")
        path = f"listas/{lst}.json"
        if lst not in ("alberto", "elena", "mama", "papa") or not str(url).startswith("http") or not os.path.exists(path):
            os.remove(f); continue
        r = read(url)
        print(lst, url, "->", r)
        item = {"n": r["n"], "l": url}
        for k in ("p", "po", "img", "img2"):
            if r.get(k): item[k] = r[k]
        data = json.load(open(path))
        data.append(item)
        json.dump(data, open(path, "w"), ensure_ascii=False, indent=2)
        open(path, "a").write("\n")
        os.remove(f)

if __name__ == "__main__":
    main()
