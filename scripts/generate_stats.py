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

    return {
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


def main():
    d = coletar()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(svg_stats(d), encoding="utf-8")
    (OUT / "langs.svg").write_text(svg_langs(d), encoding="utf-8")
    print({k: v for k, v in d.items() if k != "linguagens"}, list(d["linguagens"]))


if __name__ == "__main__":
    main()
