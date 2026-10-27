"""Institution resolution: free text / typo'd name / abbreviation / acronym / AICTE ID -> institution master.
Deterministic and explainable (no external AI service). Bands: auto-link, officer review, unresolved."""
import json, math, re
from dataclasses import dataclass

ABBR = {"engg": "engineering", "eng": "engineering", "instt": "institute", "inst": "institute", "institution": "institute",
        "clg": "college", "coll": "college", "tech": "technology", "technol": "technology", "mgmt": "management",
        "mgt": "management", "univ": "university", "poly": "polytechnic", "pharm": "pharmacy", "sch": "school"}
STOP = {"of", "and", "the", "for", "in", "at", "a"}
AUTO, REVIEW = 0.85, 0.55


def tokens(s: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", (s or "").lower().replace("&", " and ")):
        t = ABBR.get(t, t)
        if t not in STOP:
            out.append(t)
    return out


def jaro_winkler(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    md = max(la, lb) // 2 - 1; ma = [False] * la; mb = [False] * lb; m = 0
    for i in range(la):
        for j in range(max(0, i - md), min(lb, i + md + 1)):
            if not mb[j] and a[i] == b[j]:
                ma[i] = mb[j] = True; m += 1; break
    if not m:
        return 0.0
    t = k = 0
    for i in range(la):
        if ma[i]:
            while not mb[k]:
                k += 1
            t += a[i] != b[k]; k += 1
    t //= 2
    j = (m / la + m / lb + (m - t) / m) / 3; p = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        p += 1
    return j + p * 0.1 * (1 - j)


@dataclass
class _Inst:
    id: int; aicte_id: str; name: str; city: str; variants: list[list[str]]; acronym: str


class InstitutionIndex:
    def __init__(self, institutions):
        self.items: dict[int, _Inst] = {}; df: dict[str, int] = {}
        for i in institutions:
            vs = [tokens(i.name)] + [tokens(a) for a in json.loads(i.aliases or "[]") if len(a) > 5]
            acr = "".join(w[0] for w in i.name.split() if w[0].isupper()).lower()
            self.items[i.id] = _Inst(i.id, i.aicte_id, i.name, i.city.lower(), vs, acr)
            for t in set(vs[0]):
                df[t] = df.get(t, 0) + 1
        n = len(self.items) or 1
        self.idf = lambda t: math.log((n + 1) / (df.get(t, 0) + 1)) + 1
        self.cities = {x.city for x in self.items.values()}
        self.digits = {re.sub(r"\D", "", x.aicte_id): x for x in self.items.values()}

    def _soft(self, qt, vt):
        best = 0.0
        for a in qt:
            m = max((jaro_winkler(a, b) for b in vt), default=0)
            best += self.idf(a) * (m if m >= 0.88 else 0)
        return best

    def resolve(self, text: str) -> dict:
        text = text or ""
        memo = self.__dict__.setdefault("_memo", {})
        if text not in memo:
            memo[text] = self._resolve(text)
        return memo[text]

    def _resolve(self, text: str) -> dict:
        d = re.sub(r"\D", "", text)
        if len(d) >= 9:
            hit = self.digits.get(d)
            if hit:
                return self._out(hit, 1.0, "auto", "Exact AICTE Permanent ID match", [])
        qt_all = tokens(text); city = next((c for c in self.cities if c in qt_all), None)
        qt = [t for t in qt_all if t != city]
        if not qt:
            return {"institution_id": None, "score": 0.0, "band": "none", "reason": "Nothing to match", "candidates": []}
        scored = []
        for it in self.items.values():
            if len(qt) == 1 and 3 <= len(qt[0]) <= 8 and qt[0] == it.acronym:
                s, why = 0.9, f"Acronym '{qt[0].upper()}' matches"
            else:
                s, why = 0.0, ""
                for v in it.variants:
                    wq = sum(self.idf(t) for t in qt) or 1; wi = sum(self.idf(t) for t in v) or 1
                    q_cov = self._soft(qt, v) / wq; i_cov = self._soft(v, qt) / wi
                    sc = 0.7 * q_cov + 0.3 * i_cov
                    if sc > s:
                        s, why = sc, "Name matches after fixing abbreviations/spelling"
            if city:
                s += 0.08 if it.city == city else -0.15
            scored.append((min(s, 1.0), it, why))
        scored.sort(key=lambda x: -x[0]); s1, top, why = scored[0]; s2 = scored[1][0] if len(scored) > 1 else 0
        cand = [{"institution_id": x[1].id, "name": x[1].name, "score": round(x[0], 3)} for x in scored[:3]]
        if s1 >= AUTO and s1 - s2 >= 0.08:
            band = "auto"
        elif s1 >= REVIEW:
            band = "review"; why += " (ambiguous or partial - officer to confirm)"
        else:
            return {"institution_id": None, "score": round(s1, 3), "band": "none", "reason": "No confident match", "candidates": cand}
        return self._out(top, s1, band, why + (f"; city '{top.city.title()}' agrees" if city and top.city == city else ""), cand)

    @staticmethod
    def _out(it, s, band, why, cand):
        return {"institution_id": it.id, "score": round(s, 3), "band": band, "reason": why, "candidates": cand}


_cache: dict = {}


def get_index(db) -> InstitutionIndex:
    from sqlalchemy import func, select
    from ..models import Institution
    n = db.scalar(select(func.count()).select_from(Institution))
    if _cache.get("n") != n or _cache.get("url") != str(db.get_bind().url):
        _cache.update(n=n, url=str(db.get_bind().url), idx=InstitutionIndex(db.scalars(select(Institution)).all()))
    return _cache["idx"]
