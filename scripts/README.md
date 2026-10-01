# Geração dos cards de stats

`generate_stats.py` consulta a API GraphQL do GitHub e gera `assets/stats.svg` e `assets/langs.svg`, que o README do perfil exibe.

Os números incluem commits e repositórios privados (só totais e nomes de linguagens aparecem nos SVGs).

## Atualização automática

O workflow `.github/workflows/stats.yml` roda todo dia e também pode ser disparado na aba **Actions** (`workflow_dispatch`). Ele precisa do secret `STATS_TOKEN`.

### Criando o token

1. Abra https://github.com/settings/personal-access-tokens/new
2. Em *Repository access*, escolha **All repositories**.
3. Em *Repository permissions*, deixe **Metadata** e **Contents** como *Read-only*.
4. Guarde o valor como secret `STATS_TOKEN` em *Settings > Secrets and variables > Actions* deste repositório.

Quando o token expira, o workflow falha e os SVGs ficam no último valor gerado. Basta criar outro token e atualizar o secret.

## Rodando localmente

```
GH_TOKEN=<token> python scripts/generate_stats.py
```
