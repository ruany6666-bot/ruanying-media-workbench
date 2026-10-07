import os
import re
import html
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse

INGEST_ENDPOINT = os.environ["INGEST_ENDPOINT"]
INGEST_SECRET = os.environ["INGEST_SECRET"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "User-Agent": "RuanyingDiscoveryBot/1.0"
}

# 阮嘤“发现型账号”的核心内容方向
KEYWORDS = {
    "AI工具": [
        "AI tool", "AI app", "AI assistant", "AI productivity",
        "open source AI", "free AI"
    ],
    "网站APP": [
        "useful website", "useful app", "productivity app",
        "free tool", "web app"
    ],
    "公开资源": [
        "open source", "free resource", "awesome list",
        "free course", "free ebook"
    ],
    "省钱效率": [
        "free alternative", "open source alternative",
        "save money", "productivity", "automation"
    ],
    "女性友好": [
        "women safety app", "women productivity",
        "women health app", "female safety"
    ],
    "学习成长": [
        "learning tool", "study app", "book notes",
        "reading app", "knowledge tool"
    ],
}

POSITIVE_WORDS = [
    "free", "open source", "useful", "tool", "app", "website",
    "productivity", "alternative", "privacy", "local",
    "learning", "resource", "automation", "github",
    "免费", "开源", "工具", "效率", "资源", "学习"
]

NEGATIVE_WORDS = [
    "crypto", "token", "casino", "betting", "nsfw",
    "weapon", "adult"
]

NOW = datetime.now(timezone.utc)
MAX_AGE = timedelta(days=7)
MAX_RESULTS = 18


def clean_text(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url):
    if not url:
        return ""
    return url.split("#")[0].rstrip("/")


def domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def relevant_score(title, description=""):
    text = f"{title} {description}".lower()

    if any(word in text for word in NEGATIVE_WORDS):
        return -100

    score = 0

    for word in POSITIVE_WORDS:
        if word.lower() in text:
            score += 2

    # “普通人能直接使用”的东西优先
    for word in [
        "free", "alternative", "tool", "app", "website",
        "open source", "productivity", "privacy",
        "免费", "替代", "工具", "网站", "开源"
    ]:
        if word in text:
            score += 2

    return score


def classify(title, description=""):
    text = f"{title} {description}".lower()

    for category, words in KEYWORDS.items():
        if any(word.lower() in text for word in words):
            return category

    return "互联网发现"


def build_case(title, url, description, platform, discovered_at, signal=""):
    category = classify(title, description)

    why = (
        f"外部观察：该内容来自 {platform} 的近期公开信号。"
        f"题材属于「{category}」。"
        "它具备新鲜感、可立即使用或可降低成本/时间成本中的至少一个传播条件。"
        "当前仅作为候选情报，不把公开热度信号等同于阮嘤账号已验证规律。"
    )

    reusable = (
        "可迁移基因：不要只介绍产品名称；优先转换成"
        "「普通人原来的麻烦/成本 → 新发现 → 实际证据 → 谁适合用 → 限制」。"
    )

    angle = (
        f"阮嘤角度：把「{title}」从科技/产品新闻改写成普通用户能立即理解的发现。"
        "优先回答：它替我省什么、解决什么、为什么现在值得知道。"
    )

    ruanying_title = make_title(title, category)

    return {
        "platform": platform,
        "title": clean_text(title)[:300],
        "source_url": normalize_url(url),
        "discovered_at": discovered_at,
        "tags": [category, "自动发现", platform],
        "status": "candidate",
        "why_it_spreads": why,
        "reusable_gene": reusable,
        "ruanying_angle": angle,
        "ruanying_title": ruanying_title,
    }


def make_title(title, category):
    short = clean_text(title)
    if len(short) > 60:
        short = short[:57] + "..."

    if category == "AI工具":
        return f"这个AI工具，我差点因为名字普通错过了：{short}"
    if category == "省钱效率":
        return f"先别急着花钱，我发现了一个可能更省的替代：{short}"
    if category == "公开资源":
        return f"这个公开资源居然一直没人告诉我：{short}"
    if category == "网站APP":
        return f"我又挖到一个值得收藏的网站/APP：{short}"
    if category == "女性友好":
        return f"女生可以先收藏这个：{short}"
    if category == "学习成长":
        return f"如果你也总觉得学习效率低，看看这个：{short}"

    return f"今天又挖到一个值得知道的东西：{short}"


def github_discovery():
    results = []

    if not GITHUB_TOKEN:
        return results

    headers = {
        **HEADERS,
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    since = (NOW - timedelta(days=7)).date().isoformat()

    queries = [
        f"created:>{since} stars:>30",
        f"pushed:>{since} stars:>200 topic:productivity",
        f"pushed:>{since} stars:>100 topic:ai",
        f"pushed:>{since} stars:>100 topic:education",
    ]

    for query in queries:
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 15,
                },
                timeout=20,
            )
            r.raise_for_status()

            for repo in r.json().get("items", []):
                title = repo.get("full_name", "")
                desc = clean_text(repo.get("description", ""))
                url = repo.get("html_url", "")

                score = relevant_score(title, desc)
                stars = repo.get("stargazers_count", 0)

                if score < 2:
                    continue

                results.append({
                    "score": score + min(stars / 100, 10),
                    "case": build_case(
                        title=title,
                        url=url,
                        description=desc,
                        platform="GitHub",
                        discovered_at=repo.get("created_at") or NOW.isoformat(),
                        signal=f"{stars} stars",
                    ),
                })

        except Exception as e:
            print("GitHub discovery error:", e)

    return results


def hackernews_discovery():
    results = []

    queries = [
        "AI tool",
        "open source",
        "productivity",
        "free alternative",
        "app",
        "learning tool",
    ]

    cutoff = int((NOW - MAX_AGE).timestamp())

    for query in queries:
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff}",
                    "hitsPerPage": 20,
                },
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()

            for item in r.json().get("hits", []):
                title = clean_text(item.get("title"))
                url = item.get("url") or (
                    "https://news.ycombinator.com/item?id="
                    + str(item.get("objectID", ""))
                )

                points = item.get("points") or 0
                comments = item.get("num_comments") or 0
                score = relevant_score(title)

                if score < 2:
                    continue

                results.append({
                    "score": score + min(points / 20, 8) + min(comments / 20, 4),
                    "case": build_case(
                        title=title,
                        url=url,
                        description=f"Hacker News points={points}, comments={comments}",
                        platform="Hacker News",
                        discovered_at=item.get("created_at") or NOW.isoformat(),
                        signal=f"{points} points / {comments} comments",
                    ),
                })

        except Exception as e:
            print("HN discovery error:", e)

    return results


def rss_discovery():
    results = []

    feeds = [
        ("Product Hunt", "https://www.producthunt.com/feed"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
    ]

    for platform, feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:30]:
                title = clean_text(entry.get("title", ""))
                desc = clean_text(
                    entry.get("summary", "") or entry.get("description", "")
                )
                url = entry.get("link", "")

                score = relevant_score(title, desc)

                if score < 3:
                    continue

                published = (
                    entry.get("published")
                    or entry.get("updated")
                    or NOW.isoformat()
                )

                results.append({
                    "score": score,
                    "case": build_case(
                        title=title,
                        url=url,
                        description=desc,
                        platform=platform,
                        discovered_at=published,
                    ),
                })

        except Exception as e:
            print(f"{platform} feed error:", e)

    return results


def dedupe(items):
    seen_urls = set()
    seen_titles = set()
    output = []

    for item in sorted(items, key=lambda x: x["score"], reverse=True):
        case = item["case"]
        url = normalize_url(case["source_url"])
        title_key = re.sub(r"\W+", "", case["title"].lower())

        if not url or not title_key:
            continue

        if url in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title_key)
        output.append(item)

    return output


def send_cases(cases):
    if not cases:
        print("No qualified cases today.")
        return

    # Secret 曾含非 ASCII 字符，所以按已经跑通的协议 URI 编码
    encoded_secret = quote(INGEST_SECRET, safe="")

    headers = {
        "Content-Type": "application/json",
        "x-ingest-secret": encoded_secret,
        "x-ingest-secret-encoding": "uri",
    }

    payload = {
        "cases": cases
    }

    r = requests.post(
        INGEST_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=45,
    )

    print("Ingest HTTP:", r.status_code)
    print("Ingest response:", r.text[:2000])

    r.raise_for_status()


def main():
    print("Ruanying Daily Discovery started:", NOW.isoformat())

    items = []

    items.extend(github_discovery())
    time.sleep(1)

    items.extend(hackernews_discovery())
    time.sleep(1)

    items.extend(rss_discovery())

    items = dedupe(items)

    print("Qualified unique candidates:", len(items))

    selected = items[:MAX_RESULTS]

    for index, item in enumerate(selected, 1):
        case = item["case"]
        print(
            f"{index:02d}. [{case['platform']}] "
            f"score={item['score']:.1f} "
            f"{case['title']}"
        )

    send_cases([item["case"] for item in selected])

    print("Ruanying Daily Discovery finished.")


if __name__ == "__main__":
    main()
