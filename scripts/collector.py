"""Public discovery -> verified attention evidence -> compatible V24 ingestion.
No pushed_at, historical stars, or original creation date is a heat signal.
"""
import os
import re
import json
import html
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
import requests
import feedparser
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

NOW = datetime.now(timezone.utc)
MAX_RESULTS = 10
RUN_ID = os.getenv("GITHUB_RUN_ID") or NOW.strftime("local-%Y%m%dT%H%M%SZ")
HEADERS = {"User-Agent": "RuanyingDiscovery/24 (+public research; no private data)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
TOKEN = os.getenv("GITHUB_TOKEN", "")
POSITIVE = ["ai", "tool", "app", "website", "productivity", "alternative", "privacy", "learning", "education", "study", "reading", "book", "course", "design", "career", "office", "travel", "health", "beauty", "fashion", "open source", "free", "automation", "resource"]
NEGATIVE = ["casino", "betting", "nsfw", "weapon", "cryptocurrency", "crypto trading", "adult content"]

def clean(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(v or "")))).strip()

def timestamp(v):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.replace(tzinfo=d.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

def recent(v):
    d = timestamp(v)
    return d if d and NOW-timedelta(days=30) <= d <= NOW+timedelta(minutes=5) else None

def grade(v):
    d = recent(v)
    if not d:
        return "OUT"
    age = NOW-d
    return "S" if age <= timedelta(hours=24) else "A" if age <= timedelta(days=7) else "B"

def number(v):
    if v is None or v == "":
        return None
    try:
        n = int(v)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None

def normalize_url(v):
    u = urlsplit(str(v))
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("invalid URL")
    host = u.hostname.lower().removeprefix("www.")
    path = u.path.rstrip("/")
    if host == "github.com":
        path = path.lower().removesuffix(".git")
    query = [(k, val) for k, val in parse_qsl(u.query) if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid")]
    return urlunsplit(("https" if host in ("github.com", "news.ycombinator.com") else u.scheme, host, path, urlencode(sorted(query)), ""))

def relevance(title, description=""):
    text = (title+" "+description).lower()
    if any(word in text for word in NEGATIVE):
        return -100
    hits = sum(bool(re.search(r"\b"+re.escape(word)+r"\b", text)) for word in POSITIVE)
    return min(20, hits*3)

def audience_commercial(text):
    text = text.lower()
    if any(w in text for w in ("course", "learning", "education", "study", "career", "job")):
        return "大学/毕业期女性", "教育/学习/求职", "medium", "学习或求职效率"
    if any(w in text for w in ("beauty", "skincare", "cosmetic")):
        return "品质生活女性", "美妆个护", "medium", "消费信息筛选"
    if any(w in text for w in ("travel", "trip", "local guide")):
        return "品质生活女性", "旅行/本地生活", "medium", "旅行决策"
    if any(w in text for w in ("book", "reading")):
        return "成长型女性", "图书/成长", "medium", "阅读与成长"
    if any(w in text for w in ("ai", "app", "software", "tool", "productivity", "automation")):
        return "初入职场女性", "AI/软件/APP", "medium", "办公效率与工具筛选"
    return "成长型女性", "生活方式/消费品牌", "unknown", "信息筛选；适配待人工验证"

def build_case(title, url, description, evidence, published=None):
    signal = recent(evidence["signal_at"])
    if not signal:
        return None
    canonical = normalize_url(url)
    aud, lane, level, need = audience_commercial(title+" "+description)
    title = clean(title)[:300]
    return {
        "title": title, "source_url": canonical, "canonical_url": canonical,
        "entity_key": "url:"+canonical, "platform": evidence["source"], "source_name": evidence["source"],
        "source_published_at": published, "signal_at": signal.isoformat(),
        "discovered_at": NOW.isoformat(), "signal_type": evidence["signal_type"],
        "signal_confidence": "medium", "signal_evidence": [evidence],
        "audience_segment": aud, "target_audience": "20–40岁女性；"+aud,
        "commercial_lane": lane, "commercial_level": level,
        "content_object": title, "core_need": need,
        "tags": ["自动发现", "V24", lane], "status": "candidate", "source_verified": True,
        "evidence_level": "外部观察", "collection_run_id": RUN_ID,
        "why_it_spreads": evidence["summary"]+"。这是近期外部信号；传播原因与国内饱和度仍需验证。",
        "reusable_gene": "具体麻烦 → 新发现 → 可核验实测 → 适合谁 → 限制；验证筛选信任价值。",
        "do_not_copy": "不照搬海外热度、历史累计指标或因果结论；发布前核验适用条件与国内可用性。",
        "ruanying_angle": "面向"+aud+"，围绕"+need+"筛选和实测；受众及商业判断只是启发式观察。",
        "ruanying_title": "我替你筛了一遍，这个发现值得再看看："+title[:60],
        "ruanying_first_3_seconds": "先展示一个真实使用结果，再讲限制和适用人群。",
        "material_plan": "原始传播来源、官网、实测录屏、限制条件；未知数据不补数字。",
        "experiment_variable": "结果型开头", "target_metric": "收藏率（未知时不计算）",
        "analysis_details": {"description": clean(description)[:1500], "content_task": "建信任", "audience_basis": "文本关键词启发式，待真实账号数据验证", "commercial_basis": "赛道适配观察，不判断购买力", "cover_direction": "实测结果与使用场景", "content_structure": "需求、发现、证据、场景、限制", "domestic_saturation": None},
    }

GH_METADATA = {}
def github_metadata(url):
    u = urlsplit(url)
    parts = u.path.strip("/").split("/")
    if u.hostname not in ("github.com", "www.github.com") or len(parts) != 2:
        return {}
    name = "/".join(parts).removesuffix(".git").lower()
    if name not in GH_METADATA:
        headers = {"Accept": "application/vnd.github+json"}
        if TOKEN:
            headers["Authorization"] = "Bearer "+TOKEN
        try:
            r = SESSION.get("https://api.github.com/repos/"+name, headers=headers, timeout=(10, 25), allow_redirects=False)
            r.raise_for_status()
            GH_METADATA[name] = r.json()
        except requests.RequestException:
            GH_METADATA[name] = {}
    return GH_METADATA[name]

def github_discovery():
    output = []
    try:
        r = SESSION.get("https://github.com/trending?since=daily", timeout=(10, 30))
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for article in soup.select("article.Box-row"):
            link = article.select_one("h2 a")
            if not link:
                continue
            name = clean(link.get_text()).replace(" / ", "/").replace(" ", "")
            desc = clean(article.select_one("p").get_text()) if article.select_one("p") else ""
            if relevance(name, desc) < 3:
                continue
            url = "https://github.com"+link.get("href", "")
            short_growth = re.search(r"([\d,]+)\s+stars today", article.get_text(" ", strip=True))
            day_stars = number(short_growth.group(1).replace(",", "")) if short_growth else None
            meta = github_metadata(url)
            ev = {"source": "GitHub", "url": "https://github.com/trending?since=daily", "entity_url": normalize_url(url), "signal_at": NOW.isoformat(), "signal_type": "github_trending_daily", "observed_at": NOW.isoformat(), "metrics": {"stars_today": day_stars}, "summary": "实际出现在 GitHub 今日 Trending；短期增长 "+(str(day_stars)+" stars today" if day_stars is not None else "未知"), "time_basis": "榜单实际观察时间"}
            c = build_case(name, url, desc, ev, meta.get("created_at"))
            if c:
                output.append(c)
    except requests.RequestException as e:
        print("GitHub Trending unavailable:", type(e).__name__)
    return output

def hackernews_discovery():
    output, seen = [], set()
    cutoff = int((NOW-timedelta(days=30)).timestamp())
    for query in ("AI tool", "open source", "productivity", "learning", "app", "book"):
        try:
            r = SESSION.get("https://hn.algolia.com/api/v1/search", params={"query":query, "tags":"story", "numericFilters":f"created_at_i>{cutoff},points>=30", "hitsPerPage":40}, timeout=(10,25))
            r.raise_for_status()
            for item in r.json().get("hits", []):
                ident = str(item.get("objectID", ""))
                if not ident or ident in seen:
                    continue
                seen.add(ident)
                title = clean(item.get("title"))
                points, comments = number(item.get("points")), number(item.get("num_comments"))
                if not recent(item.get("created_at")) or points is None or points < 30 or relevance(title) < 3:
                    continue
                discussion = "https://news.ycombinator.com/item?id="+ident
                url = item.get("url") or discussion
                meta = github_metadata(url)
                ev = {"source":"Hacker News", "url":discussion, "entity_url":normalize_url(url), "signal_at":item["created_at"], "signal_type":"recent_discussion", "observed_at":NOW.isoformat(), "metrics":{"points":points,"comments":comments}, "summary":f"近30天 HN 讨论：{points} points；评论 "+(str(comments) if comments is not None else "未知"), "time_basis":"讨论发布时间；互动量为本次观察值"}
                c = build_case(title,url,meta.get("description") or "",ev,meta.get("created_at"))
                if c:
                    output.append(c)
        except (requests.RequestException, ValueError) as e:
            print("HN source unavailable:", type(e).__name__)
    return output

def rss_discovery():
    """Editorial coverage is medium evidence; a feed alone is never a ranked launch."""
    output = []
    try:
        r = SESSION.get("https://techcrunch.com/feed/",timeout=(10,25))
        r.raise_for_status()
        for e in feedparser.parse(r.content).entries[:40]:
            title, desc = clean(e.get("title")), clean(e.get("summary"))
            t = e.get("published_parsed")
            if not t or relevance(title,desc) < 9:
                continue
            at = datetime(*t[:6],tzinfo=timezone.utc).isoformat()
            if not recent(at):
                continue
            ev={"source":"TechCrunch","url":e.get("link"),"signal_at":at,"signal_type":"recent_media_coverage","observed_at":NOW.isoformat(),"metrics":{},"summary":"TechCrunch 近期报道；不是播放量或购买力证据","time_basis":"报道发布时间"}
            c=build_case(title,e.get("link"),desc,ev,at)
            if c:
                output.append(c)
    except (requests.RequestException,ValueError) as e:
        print("News source unavailable:",type(e).__name__)
    return output

def aggregate(cases):
    entities={}
    for c in cases:
        if not c:
            continue
        key=c["entity_key"]
        if key not in entities:
            entities[key]=c
            continue
        old=entities[key]
        evs={e["url"]+"|"+e["signal_at"]:e for e in old["signal_evidence"]+c["signal_evidence"]}
        old["signal_evidence"]=list(evs.values())
        if not old.get("source_published_at"):
            old["source_published_at"]=c.get("source_published_at")
    for c in entities.values():
        evs=sorted(c["signal_evidence"],key=lambda e:timestamp(e["signal_at"]),reverse=True)
        c["signal_at"],c["signal_type"]=evs[0]["signal_at"],evs[0]["signal_type"]
        independent=len({e["source"] for e in evs})
        c["signal_confidence"]="high" if independent>=2 else "medium"
        freshness={"S":30,"A":22,"B":12}.get(grade(c["signal_at"]),0)
        utility=relevance(c["title"],c["analysis_details"]["description"])
        # Additive observed factors. Missing metrics are excluded, never multiplied by zero.
        metric_bonus=0
        for ev in evs:
            metrics=ev["metrics"]
            if metrics.get("stars_today") is not None:
                metric_bonus=max(metric_bonus,min(10,metrics["stars_today"]/50))
            if metrics.get("points") is not None:
                metric_bonus=max(metric_bonus,min(10,metrics["points"]/30))
        c["recommendation_score"]=round(freshness+(22 if independent>=2 else 14)+utility+min(8,independent*3)+metric_bonus+8,2)
        c["why_it_spreads"]="；".join(e["summary"] for e in evs)+"。传播原因待实测验证。"
        c["analysis_details"]["score_basis"]={"freshness":freshness,"confidence":22 if independent>=2 else 14,"text_relevance":utility,"independent_sources":independent,"observed_attention_bonus":metric_bonus,"editorial_fit":8,"unknown_factors":["国内饱和度","真实用户购买力","账号涨粉潜力"]}
    return sorted((c for c in entities.values() if grade(c["signal_at"])!="OUT"),key=lambda c:c["recommendation_score"],reverse=True)[:MAX_RESULTS]

def send_cases(cases):
    if not cases:
        return {"ok":True,"received":0,"inserted":0,"updated":0,"empty_day":True}
    endpoint, secret=os.getenv("INGEST_ENDPOINT"),os.getenv("INGEST_SECRET")
    if not endpoint or not secret:
        raise RuntimeError("Missing ingestion configuration")
    r=SESSION.post(endpoint,headers={"Content-Type":"application/json","x-ingest-secret":quote(secret,safe=""),"x-ingest-secret-encoding":"uri"},json={"cases":cases,"schema_version":24},timeout=(10,60))
    print("Ingest HTTP:",r.status_code)
    r.raise_for_status()
    result=r.json()
    print("Ingest counts:",json.dumps({k:result.get(k) for k in ("ok","received","inserted","updated","skipped","inserted_ids","updated_ids")}))
    if not result.get("ok") or result.get("received")!=len(cases) or result.get("inserted",0)+result.get("updated",0)+result.get("skipped",0)!=len(cases):
        print("Ingest validation errors:",result.get("errors"))
        raise RuntimeError("Incomplete ingestion")
    return result

def main():
    print("Ruanying V24 started:",NOW.isoformat())
    cases=aggregate(github_discovery()+hackernews_discovery()+rss_discovery())
    for i,c in enumerate(cases,1):
        print(f"{i:02d}. {grade(c['signal_at'])} {c['title']} | evidence={len(c['signal_evidence'])}")
    report={"schema_version":24,"run_id":RUN_ID,"discovered_at":NOW.isoformat(),"cases":cases}
    os.makedirs("reports",exist_ok=True)
    with open("reports/discovery.json","w",encoding="utf8") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    result=send_cases(cases)
    report["ingestion"]=result
    with open("reports/discovery.json","w",encoding="utf8") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf8") as f:
            f.write(f"## V24 discovery\nQualified: {len(cases)} | Inserted: {result.get('inserted',0)} | Updated: {result.get('updated',0)}\n")
            for c in cases:
                f.write(f"- **{grade(c['signal_at'])}** {c['title']} | {c['signal_confidence']} | {c['canonical_url']}\n")
    print("Ruanying V24 completed.")

if __name__=="__main__":
    main()
