"""Genera catalog/data/seo_exclusions.csv (lote C2). Solo lee la base.

    python catalog/data/build_seo_exclusions.py --db db.sqlite3 --sitemap sitemap.xml

  --db       SQLite con el catálogo (copia local de producción).
  --sitemap  sitemap.xml descargado de producción: define el universo de
             productos activos (curl -s https://www.pegasusstoremx.com/sitemap.xml).

Salida (separador ';'): slug;exclusion;canonical_slug;criterios;nombre, que
se carga con `manage.py load_seo_exclusions`. También imprime un resumen.

Decisiones aprobadas:
  - b, c1, c2, c3, a1 → exclusión (noindex, fuera del sitemap y de listas).
  - a2 (accesorios "para/tipo/compatible con <marca>") NO se excluye.
  - d (mismo nombre normalizado): se mantiene el slug sin sufijo -N con
    stock; si no hay, el de menor precio con stock. Los demás llevan
    rel=canonical hacia él. El destino nunca es un producto con noindex.
  - e (armas y productos para adultos): igual que b/c/a1 (noindex, fuera
    del sitemap, de listas y de campañas). Si el producto ya tiene b/c/a1,
    se queda ese criterio.
  - seo_protected_slugs.txt: protegidos de a1, a2 y d (tráfico orgánico).
    b, c1, c2, c3 y e se aplican igual.
"""
import argparse
import collections
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "seo_exclusions.csv"
PROTECTED_FILE = Path(__file__).resolve().parent / "seo_protected_slugs.txt"


def norm(t):
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


# ── (b) basura / servicios ─────────────────────────────────────────────────────
JUNK_NAME = re.compile(
    r"^(x )?envios?\b|envio (prioritario|express|gratis|rapido|bodega|propetario)|garantia extendida"
    r"|seguro (de perdida|\+|garantia|todo riesgo)|seguro garantia|^producto envio|^solo envio|envioprioritario"
)


def classify_junk(slug, name):
    n = norm(name)
    if slug.startswith("product-image"):
        return "product-image"
    if JUNK_NAME.search(n):
        return "servicio (envío/garantía/seguro)"
    if re.sub(r"-\d+$", "", slug) in ("producto", "varios") or re.fullmatch(r"[\d-]+", slug):
        return "nombre genérico"
    return None


# ── (c) salud / adelgazamiento ───────────────────────────────────────────────
C1 = re.compile(
    r"adelgaz|bajar de peso|perder peso|perdida de peso|quema ?grasa|quemador de grasa|fat ?burn|termogenic"
    r"|reductor(es|as|a)? (de )?(abdomen|peso|grasa|medidas)|parches? reductor|detox|desintoxic|keto\b|garcinia"
    r"|l-?carnitina|cafe verde"
    r"|dejar de fumar|anti ?tabaco|anti ?smoke|fumarex|tabacum"
    r"|neuropat|diabet|glucosa|hipertens|presion arterial|artritis|antiartrit|artrosis|prostat|varic|hemorroid"
    r"|gastritis|reflujo|colesterol|tiroid|migran|insomnio|ansiedad|depresion|\basma\b|psoriasis|hongos|alopecia"
    r"|caida del cabello|impotencia|disfuncion erectil|ereccion|viagra|potenciador sexual|retardante|menopaus"
    r"|cistitis|infeccion urinaria|parasit|cartilag|salud renal|higado|hormonal"
    r"|remedio|\bcura\b|curar|homeopat|ozempic|semaglut|minoxidil|antiinflamatori|analges|alivi\w* (el )?dolor"
    r"|dolor (de|lumbar|muscular|articular)|parches? (medicinal|para el dolor|de dolor|herbal)"
)
C1_EXCLUDE = re.compile(r"balon medicinal|nicotinamid")
C2 = re.compile(
    r"suplemento|capsulas?\b|softgels?|tabletas?\b|comprimidos|gomitas?\b|multivitamin|colageno hidrolizado"
    r"|colageno (plus|marino)|\bnad\b|resveratrol|\bnmn\b|ashwagandha|moringa|espirulina|spirulina|maca\b"
    r"|biotin|omega ?3|creatina|proteina|whey|melatonina|probiotico|glutation|jarabe|elixir|\bgotas\b"
    r"|zarzaparrilla|calostro|calustron"
)
C2_TOPICAL = re.compile(
    r"serum|crema|mascarilla|protector solar|shampoo|champu|jabon|locion|tonico facial|gel (facial|de ducha)"
    r"|labial|esmalte|pestan|maquillaje|base de|exfoliante|contorno de ojos|balsamo"
)
C2_NOT = re.compile(r"termo|mezclador|shaker|botella|dispensador|pastillero|organizador")
C3_DESC = re.compile(
    r"neuropat|diabet|hipertens|presion arterial|artritis|artrosis|prostat|varices|hemorroid|gastritis|colesterol"
    r"|tiroid|cancer|tumor|insomnio|ansiedad|depresion|impotencia|disfuncion erectil|cura (la|el|de)"
    r"|elimina (la|el) (diabetes|dolor)|bajar de peso|perder peso|quema grasa|adelgaz|dejar de fumar"
)
C3_CONSUMABLE = re.compile(
    r"\b\d+ ?(ml|gr|g|mg|caps|lt|litros?|oz|und|unidades)\b|jarabe|gotas|capsul|aceite|crema|\bte\b|infusion"
    r"|polvo|tintura|elixir|combo|tratamiento|batido|bebida|unguento|pomada|spray|\bgel\b"
)
C3_DEVICE = re.compile(
    r"tensiometro|oximetro|glucometro|termometro|nebulizador|rodillera|tobillera|faja|cojin|almohada|tapete"
    r"|masajead|electrodo|lampara|pulsera|reloj|cinturon|plantilla|silla|cama|colchon|bascula|balanza"
)


def classify_health(name, desc, cat):
    n = norm(name)
    m = C1.search(n)
    if m and not C1_EXCLUDE.search(n):
        return "c1", m.group(0)
    m = C2.search(n)
    if m and not C2_TOPICAL.search(n) and not C2_NOT.search(n):
        return "c2", m.group(0)
    if cat == "store:salud_bienestar" and C3_CONSUMABLE.search(n) and not C3_DEVICE.search(n):
        d = C3_DESC.search(norm(desc)[:4000])
        if d:
            return "c3", d.group(0)
    return None, ""


# ── (a) marcas registradas ────────────────────────────────────────────────────
BRANDS = [
    r"jbl", r"apple", r"iphone", r"ipad", r"airpods?", r"macbook", r"apple watch", r"samsung", r"xiaomi", r"huawei",
    r"sony", r"playstation", r"ps4", r"ps5", r"xbox", r"nintendo", r"gopro", r"bose",
    r"nike", r"adidas", r"puma", r"reebok", r"converse", r"new balance", r"under armour", r"skechers", r"crocs", r"vans",
    r"gucci", r"louis vuitton", r"vuitton", r"chanel", r"dior", r"prada", r"versace", r"armani", r"calvin klein",
    r"tommy hilfiger", r"lacoste", r"ralph lauren", r"michael kors", r"carolina herrera", r"paco rabanne", r"hugo boss",
    r"lancome", r"victoria.?s secret", r"bvlgari", r"dolce gabbana", r"givenchy", r"yves saint laurent",
    r"jean paul gaultier", r"montblanc", r"ck one", r"ck be", r"dkny",
    r"rolex", r"casio", r"g-?shock", r"ray-?ban", r"oakley", r"garmin", r"fitbit",
    r"dyson", r"philips", r"braun", r"remington", r"gillette", r"oral-?b", r"babyliss", r"wahl", r"conair", r"revlon",
    r"loreal", r"maybelline", r"kylie", r"huda beauty", r"nyx", r"mac cosmetics", r"olaplex", r"kerastase", r"cerave",
    r"la roche.posay", r"the ordinary",
    r"disney", r"marvel", r"pokemon", r"hello kitty", r"barbie", r"lego", r"hot wheels", r"labubu", r"stitch",
    r"minecraft", r"spiderman", r"frozen", r"paw patrol", r"sanrio", r"kuromi", r"stanley", r"owala",
    r"tupperware", r"oster", r"black ?\+? ?decker", r"bosch", r"makita", r"dewalt", r"stihl", r"milwaukee",
    r"kenworth", r"harley", r"ferrari", r"lamborghini", r"bmw", r"toyota", r"chevrolet", r"ford",
]
BRAND_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(BRANDS) + r")(?![a-z0-9])")
COMPAT_RE = re.compile(
    r"(para|compatible|compat\.?|tipo|estilo|inspirad[oa]|repuesto|funda|forro|case|protector|cargador|cable|correa"
    r"|pulso|vidrio|mica|lamina|soporte|adaptador)\b[^|]{0,30}$"
)
REPLICA_RE = re.compile(r"replica|\b1\.1\b|\baaa\b|inspirad[oa] en|tipo original|copia\b")
BATTERY_RE = re.compile(r"bateri|\bpilas?\b")


def classify_brand(name):
    n = norm(name)
    r = REPLICA_RE.search(n)
    if r and not (r.group(0) == "aaa" and BATTERY_RE.search(n)):
        return "a1", r.group(0)
    m = BRAND_RE.search(n)
    if not m:
        return None, ""
    if COMPAT_RE.search(n[: m.start()]):
        return "a2", m.group(0)
    return "a1", m.group(0)


# ── (e) armas y productos para adultos ────────────────────────────────────────
E_RE = re.compile(
    r"\btaser\b|paraliza|electrochoq|aturdidor|manopla|puno americano"
    r"|baston (de )?(defensa|electrico|retractil|policial|extensible|telescopico)"
    r"|gas pimienta|spray (de )?pimienta|gas paralizante|defensa personal"
    r"|vibrador|dildo|consolador|masturbador|succionador|juguetes? sexual|plug anal|bala vibradora"
    r"|lubricante (intimo|sexual|anal)|estimulador (de )?(clitoris|femenino|masculino|sexual|prostata)"
    r"|lenceria erotica|erotic|sexual"
    r"|armador(a)? de cigarr|armar cigarr|enrolador|maquina (de|para) cigarr|entubador"
)
E_NOT = re.compile(r"baldosa|ceramica|loseta|concreto|nivelador|azulejo|\bpiso\b")


def classify_adult_weapon(name, cat):
    n = norm(name)
    if cat == "store:bienestar_intimo":
        return "categoría Bienestar íntimo"
    m = E_RE.search(n)
    if m and not E_NOT.search(n):
        return m.group(0)
    return None


EXCLUDED = ("b", "c1", "c2", "c3", "a1", "e")  # en orden de prioridad
SEO_NOINDEX = {"b", "c1", "c2", "c3", "a1", "e"}
PROTECTABLE = {"a1", "a2", "d"}


def build(db_path, sitemap_path):
    active = set(re.findall(r"/producto/([^/<]+)/</loc>", Path(sitemap_path).read_text(encoding="utf-8")))
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = [
        r for r in db.execute(
            "select p.slug, p.name, coalesce(p.description,''), coalesce(c.dropi_id,''), p.price, p.stock "
            "from catalog_product p left join catalog_category c on c.id = p.category_id"
        )
        if r[0] in active
    ]

    info = {}
    for slug, name, desc, cat, price, stock in rows:
        crit = {}
        junk = classify_junk(slug, name)
        if junk:
            crit["b"] = junk
        t, k = classify_health(name, desc, cat)
        if t:
            crit[t] = k
        t, k = classify_brand(name)
        if t:
            crit[t] = k
        adult = classify_adult_weapon(name, cat)
        if adult:
            crit["e"] = adult
        info[slug] = {"name": name, "price": float(price or 0), "stock": stock or 0, "crit": crit}

    protected = {
        line.strip() for line in PROTECTED_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for slug in protected & set(info):
        for c in PROTECTABLE:
            info[slug]["crit"].pop(c, None)
        info[slug]["protected"] = True

    def exclusion_of(slug):
        crit = info[slug]["crit"]
        return next((c for c in EXCLUDED if c in crit), "")

    # (d) casi duplicados por nombre normalizado.
    groups = collections.defaultdict(list)
    for slug, data in info.items():
        key = re.sub(r"[^a-z0-9]", "", norm(data["name"]))
        if key:
            groups[key].append(slug)
    canonical = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        candidates = [s for s in members if info[s]["stock"] > 0 and exclusion_of(s) not in SEO_NOINDEX]
        unsuffixed = [s for s in candidates if not re.search(r"-\d+$", s)]
        if unsuffixed:
            keep = min(unsuffixed, key=len)
        elif candidates:
            keep = min(candidates, key=lambda s: (info[s]["price"], len(s)))
        else:
            continue
        for s in members:
            if s != keep and exclusion_of(s) not in SEO_NOINDEX and not info[s].get("protected"):
                canonical[s] = keep
                info[s]["crit"]["d"] = keep

    out_rows = []
    for slug, data in sorted(info.items()):
        exclusion = exclusion_of(slug)
        canon = canonical.get(slug, "")
        if exclusion or canon:
            out_rows.append([slug, exclusion, canon, ",".join(sorted(data["crit"])), data["name"]])
    return out_rows, info, sorted(protected - set(info))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--sitemap", required=True)
    args = parser.parse_args()
    out_rows, info, missing_protected = build(args.db, args.sitemap)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["slug", "exclusion", "canonical_slug", "criterios", "nombre"])
        w.writerows(out_rows)
    counts = collections.Counter(r[1] or "d (solo canónica)" for r in out_rows)
    print(f"Universo: {len(info)} activos · filas: {len(out_rows)} → {OUTPUT}")
    for key, value in sorted(counts.items()):
        print(f"  {key}: {value}")
    print(f"Protegidos encontrados: {sum(1 for d in info.values() if d.get('protected'))} · sin datos: {missing_protected}")
    for slug, data in sorted(info.items()):
        if data.get("protected") and data["crit"]:
            print(f"  protegido pero excluido igual: {slug} → {','.join(sorted(data['crit']))}")


if __name__ == "__main__":
    main()
