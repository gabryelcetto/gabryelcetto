"""Gera assets/stats.svg e assets/langs.svg a partir da API GraphQL do GitHub.

Usa só a biblioteca padrão. O token vem da variável GH_TOKEN e precisa ler os
repositórios privados do dono. Nada além de números e nomes de linguagens
vai para os SVGs.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"
OUT = Path(__file__).resolve().parent.parent / "assets"

# tema tokyonight
BG, TITLE, TEXT, ICON = "#1a1b27", "#70a5fd", "#38bdae", "#bf91f3"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
FALLBACK_COLOR = "#8b949e"


def gql(query, variables=None):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    if "errors" in data:
        sys.exit(f"Erro da API: {data['errors']}")
    return data["data"]


def coletar():
    base = gql("""{ viewer { login name createdAt
        pullRequests { totalCount } issues { totalCount }
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
        repositories(ownerAffiliations: OWNER) { totalCount }
    } }""")["viewer"]

    # estrelas e linguagens: repositórios próprios, sem forks, públicos e privados
    estrelas, linguagens, cursor = 0, {}, None
    while True:
        page = gql("""query($after: String) { viewer { repositories(first: 100, after: $after,
            ownerAffiliations: OWNER, isFork: false) {
            pageInfo { hasNextPage endCursor }
            nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                edges { size node { name color } } } } } } }""",
            {"after": cursor})["viewer"]["repositories"]
        for repo in page["nodes"]:
            estrelas += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                lang = linguagens.setdefault(
                    edge["node"]["name"], {"size": 0, "color": edge["node"]["color"] or FALLBACK_COLOR})
                lang["size"] += edge["size"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    # commits de toda a vida (públicos + privados), ano a ano
    commits = 0
    ano_atual = datetime.now(timezone.utc).year
    for ano in range(int(base["createdAt"][:4]), ano_atual + 1):
        c = gql("""query($from: DateTime!, $to: DateTime!) { viewer { contributionsCollection(from: $from, to: $to) {
            totalCommitContributions restrictedContributionsCount } } }""",
            {"from": f"{ano}-01-01T00:00:00Z", "to": f"{ano}-12-31T23:59:59Z"}
            )["viewer"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]

    # calendário do último ano (inclui privadas quando o token é do dono)
    semanas = gql("""{ viewer { contributionsCollection { contributionCalendar {
        weeks { contributionDays { date contributionCount } } } } } }"""
        )["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    dias = [(x["date"], x["contributionCount"]) for w in semanas for x in w["contributionDays"]]

    return {
        "dias": dias,
        "login": base["login"],
        "estrelas": estrelas,
        "commits": commits,
        "prs": base["pullRequests"]["totalCount"],
        "issues": base["issues"]["totalCount"],
        "contribuiu": base["repositoriesContributedTo"]["totalCount"],
        "repos": base["repositories"]["totalCount"],
        "linguagens": linguagens,
    }


def svg_stats(d):
    linhas = [
        ("★", "Total Stars Earned", d["estrelas"]),
        ("⟳", "Total Commits", d["commits"]),
        ("⑂", "Total PRs", d["prs"]),
        ("!", "Total Issues", d["issues"]),
        ("▣", "Repositories", d["repos"]),
        ("⇄", "Contributed to", d["contribuiu"]),
    ]
    corpo = ""
    for i, (icone, rotulo, valor) in enumerate(linhas):
        y = 70 + i * 25
        corpo += (f'<text x="25" y="{y}" fill="{ICON}" font-size="14">{icone}</text>'
                  f'<text x="50" y="{y}" fill="{TEXT}" font-weight="600" font-size="14">{escape(rotulo)}:</text>'
                  f'<text x="260" y="{y}" fill="{TEXT}" font-weight="600" font-size="14">{valor:,}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="467" height="220" viewBox="0 0 467 220" font-family="{FONT}">
<rect width="467" height="220" rx="4.5" fill="{BG}"/>
<text x="25" y="35" fill="{TITLE}" font-weight="600" font-size="18">{escape(d["login"])}'s GitHub Stats</text>
{corpo}
<g transform="translate(385 120)"><circle r="40" fill="none" stroke="#2f3150" stroke-width="6"/>
<circle r="40" fill="none" stroke="{TEXT}" stroke-width="6" stroke-dasharray="180 251" transform="rotate(-90)" stroke-linecap="round"/>
<text y="9" text-anchor="middle" fill="{TEXT}" font-weight="700" font-size="26">{d["commits"]}</text>
<text y="26" text-anchor="middle" fill="{ICON}" font-size="10">commits</text></g>
</svg>
'''


def svg_langs(d, top=6):
    total = sum(l["size"] for l in d["linguagens"].values()) or 1
    ordenadas = sorted(d["linguagens"].items(), key=lambda kv: kv[1]["size"], reverse=True)[:top]
    soma = sum(l["size"] for _, l in ordenadas)
    barra, x = "", 25.0
    for _, l in ordenadas:
        w = 270 * l["size"] / soma
        barra += f'<rect x="{x:.2f}" y="55" width="{w:.2f}" height="8" fill="{l["color"]}"/>'
        x += w
    legenda = ""
    for i, (nome, l) in enumerate(ordenadas):
        cx, cy = 25 + (i % 2) * 140, 90 + (i // 2) * 25
        pct = 100 * l["size"] / total
        legenda += (f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{l["color"]}"/>'
                    f'<text x="{cx + 15}" y="{cy}" fill="{TEXT}" font-size="12">{escape(nome)} {pct:.1f}%</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220" font-family="{FONT}">
<rect width="320" height="220" rx="4.5" fill="{BG}"/>
<text x="25" y="35" fill="{TITLE}" font-weight="600" font-size="18">Most Used Languages</text>
<clipPath id="r"><rect x="25" y="55" width="270" height="8" rx="4"/></clipPath>
<g clip-path="url(#r)">{barra}</g>
{legenda}
</svg>
'''


def sequencias(dias):
    """Devolve (total, sequência atual, maior sequência) a partir de [(data, qtd)]."""
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dias = [x for x in dias if x[0] <= hoje]
    total = sum(q for _, q in dias)
    maior = atual = 0
    for _, q in dias:
        atual = atual + 1 if q > 0 else 0
        maior = max(maior, atual)
    # a sequência atual não quebra se hoje ainda não tem contribuição
    corrente = 0
    for i, (_, q) in enumerate(reversed(dias)):
        if q > 0:
            corrente += 1
        elif i == 0:
            continue
        else:
            break
    return total, corrente, maior


def svg_streak(d):
    total, atual, maior = sequencias(d["dias"])
    colunas = [(total, "Total Contributions", "último ano"),
               (atual, "Current Streak", "dias seguidos"),
               (maior, "Longest Streak", "dias seguidos")]
    corpo = ""
    for i, (valor, titulo, sub) in enumerate(colunas):
        cx = 78 + i * 155
        cor = TITLE if i == 1 else TEXT
        corpo += (f'<text x="{cx}" y="70" text-anchor="middle" fill="{cor}" font-weight="700" font-size="30">{valor:,}</text>'
                  f'<text x="{cx}" y="98" text-anchor="middle" fill="{cor}" font-weight="600" font-size="13">{titulo}</text>'
                  f'<text x="{cx}" y="116" text-anchor="middle" fill="{ICON}" font-size="11">{sub}</text>')
    divisores = "".join(f'<line x1="{155 * i + 1}" y1="35" x2="{155 * i + 1}" y2="125" stroke="#2f3150"/>' for i in (1, 2))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="467" height="150" viewBox="0 0 467 150" font-family="{FONT}">
<rect width="467" height="150" rx="4.5" fill="{BG}"/>
{divisores}
{corpo}
</svg>
'''


def svg_atividade(d):
    # soma por semana (7 dias) para suavizar o gráfico
    dias = [q for _, q in d["dias"]]
    semanas = [sum(dias[i:i + 7]) for i in range(0, len(dias), 7)]
    w, h, px, py = 700, 220, 40, 45
    topo = max(max(semanas), 1)
    passo = (w - 2 * px) / max(len(semanas) - 1, 1)
    pontos = [(px + i * passo, h - py - (h - 2 * py) * v / topo) for i, v in enumerate(semanas)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    area = f"{px},{h - py} " + linha + f" {pontos[-1][0]:.1f},{h - py}"
    grade = "".join(
        f'<line x1="{px}" y1="{y:.1f}" x2="{w - px}" y2="{y:.1f}" stroke="#2f3150"/>'
        f'<text x="{px - 8}" y="{y + 4:.1f}" text-anchor="end" fill="{ICON}" font-size="10">{round(topo * f)}</text>'
        for f, y in ((f, h - py - (h - 2 * py) * f) for f in (0, 0.5, 1)))
    # rótulos de mês
    meses, ultimo, x_ult = "", None, -99
    for i, (data, _) in enumerate(d["dias"][::7]):
        m = data[5:7]
        if m != ultimo and i < len(pontos):
            ultimo = m
            if pontos[i][0] - x_ult < 38:  # evita rótulos sobrepostos
                continue
            x_ult = pontos[i][0]
            meses += f'<text x="{x_ult:.1f}" y="{h - 20}" text-anchor="middle" fill="{ICON}" font-size="10">{m}/{data[2:4]}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<rect width="{w}" height="{h}" rx="4.5" fill="{BG}"/>
<text x="{px}" y="28" fill="{TITLE}" font-weight="600" font-size="18">Contribution Activity (por semana)</text>
{grade}
<polygon points="{area}" fill="{TEXT}" fill-opacity="0.15"/>
<polyline points="{linha}" fill="none" stroke="{TEXT}" stroke-width="2.5" stroke-linejoin="round"/>
{meses}
</svg>
'''


# (título, chave em d, limites para os ranks C, B, A, S)
TROFEUS = [
    ("Commits", "commits", (10, 50, 200, 1000)),
    ("Repositories", "repos", (3, 8, 20, 50)),
    ("Pull Requests", "prs", (2, 10, 50, 200)),
    ("Issues", "issues", (2, 10, 50, 200)),
    ("Stars", "estrelas", (1, 10, 50, 200)),
    ("Languages", "n_langs", (2, 4, 7, 12)),
]
RANKS = [("-", "#4b4f72"), ("C", "#cd7f32"), ("B", "#c0c8d4"), ("A", "#ffd166"), ("S", "#70a5fd")]


def svg_trofeus(d):
    d = dict(d, n_langs=len(d["linguagens"]))
    cel, corpo = 110, ""
    for i, (titulo, chave, limites) in enumerate(TROFEUS):
        valor = d[chave]
        nivel = sum(valor >= x for x in limites)
        letra, cor = RANKS[nivel]
        x = i * cel + cel / 2
        corpo += (f'<g transform="translate({x} 0)">'
                  f'<path d="M-16 28 h32 v14 a16 16 0 0 1 -32 0 z" fill="{cor}"/>'
                  f'<rect x="-6" y="56" width="12" height="9" fill="{cor}"/><rect x="-14" y="64" width="28" height="6" rx="2" fill="{cor}"/>'
                  f'<text y="52" text-anchor="middle" fill="{BG}" font-weight="800" font-size="16">{letra}</text>'
                  f'<text y="92" text-anchor="middle" fill="{cor}" font-weight="700" font-size="12">{escape(titulo)}</text>'
                  f'<text y="110" text-anchor="middle" fill="{TEXT}" font-size="12">{valor:,}</text></g>')
    w = cel * len(TROFEUS)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="130" viewBox="0 0 {w} 130" font-family="{FONT}">
<rect width="{w}" height="130" rx="4.5" fill="{BG}"/>
{corpo}
</svg>
'''


def main():
    d = coletar()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(svg_stats(d), encoding="utf-8")
    (OUT / "langs.svg").write_text(svg_langs(d), encoding="utf-8")
    (OUT / "streak.svg").write_text(svg_streak(d), encoding="utf-8")
    (OUT / "activity.svg").write_text(svg_atividade(d), encoding="utf-8")
    (OUT / "trophies.svg").write_text(svg_trofeus(d), encoding="utf-8")
    print({k: v for k, v in d.items() if k not in ("linguagens", "dias")}, list(d["linguagens"]))


if __name__ == "__main__":
    main()
