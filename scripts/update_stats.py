import os
import re
import json
import urllib.request
import datetime

USERNAME = "ItsMeVikashKumarSingh"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def fetch_json(url, headers=None):
    req_headers = {"User-Agent": "GitHub-Stats-Updater"}
    if TOKEN:
        req_headers["Authorization"] = f"Bearer {TOKEN}"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_stats():
    # 1. Fetch user profile
    user_data = fetch_json(f"https://api.github.com/users/{USERNAME}")
    public_repos = user_data.get("public_repos", 67)
    followers = user_data.get("followers", 7)
    following = user_data.get("following", 4)

    # 2. Fetch all-time total contributions from streak stats (matches the live streak card)
    total_contributions = 2471
    try:
        req = urllib.request.Request(
            f"https://streak-stats.demolab.com/?user={USERNAME}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_svg = resp.read().decode("utf-8")
            match = re.search(r'Total Contributions big number -->.*?<text[^>]*>\s*([0-9,]+)\s*</text>', raw_svg, re.DOTALL)
            if match:
                total_contributions = int(match.group(1).replace(",", ""))
    except Exception as e:
        print("Notice fetching from streak stats:", e)

    # 3. Fetch language breakdown
    lang_totals = {}

    # Try GraphQL for deep language breakdown if token is available
    if TOKEN:
        try:
            query = """
            query($username: String!) {
              user(login: $username) {
                repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
                  nodes {
                    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                      edges {
                        size
                        node {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            post_data = json.dumps({"query": query, "variables": {"username": USERNAME}}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=post_data,
                headers={"User-Agent": "GitHub-Stats-Updater", "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                gql_res = json.loads(resp.read().decode("utf-8"))
                user_gql = gql_res.get("data", {}).get("user", {})
                
                repos = user_gql.get("repositories", {}).get("nodes", [])
                for r in repos:
                    edges = r.get("languages", {}).get("edges", [])
                    for e in edges:
                        lname = e["node"]["name"]
                        lsize = e["size"]
                        lang_totals[lname] = lang_totals.get(lname, 0) + lsize
        except Exception as e:
            print("GraphQL fetch notice:", e)

    # Fallback to REST language count if lang_totals is empty
    if not lang_totals:
        try:
            repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
            for repo in repos_data:
                if not repo.get("fork"):
                    lang = repo.get("language")
                    if lang:
                        lang_totals[lang] = lang_totals.get(lang, 0) + 1
        except Exception as e:
            print("REST repos fetch notice:", e)

    return {
        "public_repos": public_repos,
        "followers": followers,
        "following": following,
        "total_contributions": total_contributions,
        "lang_totals": lang_totals,
        "date_ym": datetime.datetime.now().strftime("%Y-%m")
    }

def update_analytics_grid(stats):
    filepath = os.path.join("assets", "analytics-grid.svg")
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Update public repos number
    content = re.sub(
        r'(<text[^>]*letter-spacing="3">PUBLIC REPOSITORIES</text>\s*<text[^>]*>)\d+(</text>)',
        rf'\g<1>{stats["public_repos"]}\g<2>',
        content
    )

    # Update total contributions number
    content = re.sub(
        r'(<text[^>]*letter-spacing="3">TOTAL CONTRIBUTIONS</text>\s*<text[^>]*>)[^<]*(<tspan[^>]*>[^<]*</tspan></text>)',
        rf'\g<1>{stats["total_contributions"]:,}\g<2>',
        content
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated assets/analytics-grid.svg")

def update_holographic_foil(stats):
    filepath = os.path.join("assets", "holographic-foil.svg")
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Update TOTAL CONTRIBUTIONS count
    content = re.sub(
        r'(<text[^>]*letter-spacing="3">(?:TOTAL )?CONTRIBUTIONS</text>\s*<text[^>]*>)[^<]*(<tspan[^>]*>[^<]*</tspan></text>)',
        rf'\g<1>{stats["total_contributions"]:,}\g<2>',
        content
    )

    # Update date stamp
    content = re.sub(
        r'UPDATED \d{4}-\d{2}',
        f'UPDATED {stats["date_ym"]}',
        content
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated assets/holographic-foil.svg")

def update_top_langs(stats):
    filepath = os.path.join("assets", "top-langs.svg")
    if not os.path.exists(filepath):
        return
    
    # Calculate top languages
    lang_totals = stats["lang_totals"]
    if not lang_totals:
        print("No language data found to update.")
        return

    # Filter/merge top languages
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)
    top_5 = sorted_langs[:5]
    total_metric = sum(item[1] for item in sorted_langs)
    
    if total_metric <= 0:
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Update footer repos count
    content = re.sub(
        r'DISTRIBUTION COMPUTED ACROSS \d+ PUBLIC REPOSITORIES',
        f'DISTRIBUTION COMPUTED ACROSS {stats["public_repos"]} PUBLIC REPOSITORIES',
        content
    )
    content = re.sub(
        r'>\d+ REPOS<',
        f'>{stats["public_repos"]} REPOS<',
        content
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated assets/top-langs.svg")

def update_github_stats(stats):
    filepath = os.path.join("assets", "github-stats.svg")
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(
        r'(<text[^>]*letter-spacing="1.5">PUBLIC REPOSITORIES</text>\s*<text[^>]*>)\d+(</text>)',
        rf'\g<1>{stats["public_repos"]}\g<2>',
        content
    )
    content = re.sub(
        r'(<text[^>]*letter-spacing="1.5">TOTAL CONTRIBUTIONS</text>\s*<text[^>]*>)[^<]*(<tspan)',
        rf'\g<1>{stats["total_contributions"]:,}\g<2>',
        content
    )
    content = re.sub(
        r'>\d+ <tspan fill="#64748b" font-size="12">Followers</tspan>  ·  \d+ <tspan fill="#64748b" font-size="12">Following</tspan><',
        f'>{stats["followers"]} <tspan fill="#64748b" font-size="12">Followers</tspan>  ·  {stats["following"]} <tspan fill="#64748b" font-size="12">Following</tspan><',
        content
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated assets/github-stats.svg")

def main():
    print(f"Fetching stats for {USERNAME}...")
    stats = get_stats()
    print("Fetched stats:", {k: v for k, v in stats.items() if k != "lang_totals"})
    update_analytics_grid(stats)
    update_holographic_foil(stats)
    update_top_langs(stats)
    update_github_stats(stats)
    print("All stats updated successfully!")

if __name__ == "__main__":
    main()
