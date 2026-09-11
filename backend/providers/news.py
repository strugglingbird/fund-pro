"""Financial headline aggregation across the news channels."""
import logging
import re
import threading
import time

from .core import FORCE_REFRESH, ak, format_timestamp

logger = logging.getLogger(__name__)

IMPORTANT_NEWS_KEYWORDS = (
    "国务院", "证监会", "央行", "财政部", "发改委", "美联储", "降准", "降息", "加息",
    "政策", "监管", "业绩", "财报", "回购", "增持", "并购", "重组", "停牌", "涨停",
    "跌停", "GDP", "CPI", "PMI", "关税", "战争"
)

NEWS_CACHE = {"expires_at": 0, "payload": None}
NEWS_CACHE_LOCK = threading.Lock()
NEWS_CACHE_TTL = 30

NEWS_SOURCE_SPECS = (
    ("财联社电报", "cls", 6),
    ("新浪财经", "sina", 4),
    ("富途牛牛", "futu", 4),
    ("同花顺", "ths", 4)
)


def _source_fetcher(key):
    if key == "cls":
        return ak.stock_info_global_cls
    return getattr(ak, f"stock_info_global_{key}")


def _collect_source_group(source, key, limit):
    """Build one news group from its AkShare channel."""
    return {"source": source, "items": _normalise_news_items(_source_fetcher(key)(), source, limit)}


def fetch_financial_news():
    """Aggregate important real-time financial headlines from the news channels."""
    with NEWS_CACHE_LOCK:
        if not FORCE_REFRESH.get() and NEWS_CACHE["payload"] and NEWS_CACHE["expires_at"] > time.time():
            return NEWS_CACHE["payload"]

    groups = []
    for source, key, limit in NEWS_SOURCE_SPECS:
        try:
            group = _collect_source_group(source, key, limit)
        except Exception as exc:
            # A single dead channel must not hide the others, but silently
            # dropping every channel is how a missing dependency went unnoticed.
            logger.warning("快讯渠道 %s 抓取失败: %s: %s", source, type(exc).__name__, exc)
            continue
        if group["items"]:
            groups.append(group)
        else:
            logger.warning("快讯渠道 %s 返回空数据", source)
    if not groups:
        logger.warning("全部快讯渠道均无数据，AkShare 是否可用: %s", ak is not None)
        return None

    items = [item for group in groups for item in group["items"]]
    payload = {
        "items": items,
        "groups": groups,
        "total_count": len(items),
        "source_label": "财经快讯聚合",
        "generated_at": format_timestamp()
    }
    with NEWS_CACHE_LOCK:
        NEWS_CACHE["payload"] = payload
        NEWS_CACHE["expires_at"] = time.time() + NEWS_CACHE_TTL
    return payload


def _normalise_news_items(frame, source, limit):
    """Map the different AkShare news DataFrame layouts into one UI schema."""
    columns = list(frame.columns)
    return _normalise_news_records(frame.to_dict(orient="records"), columns, source, limit)


def _is_metadata_column(column):
    """Whether a column carries time or link metadata instead of article text."""
    return any(hint in str(column) for hint in ("时间", "日期", "链接"))


def _pick_title_key(columns):
    """Prefer an explicit title column, then any column that is not time/link metadata."""
    return next(
        (column for column in columns if "标题" in str(column)),
        next((column for column in columns if not _is_metadata_column(column)), columns[0])
    )


def _pick_content_key(columns, title_key):
    """Prefer a summary column, then any unused text column, then the title itself."""
    return next(
        (column for column in columns
         if any(text in str(column) for text in ("内容", "摘要", "快讯"))),
        next((column for column in columns
              if column != title_key and not _is_metadata_column(column)), title_key)
    )


def _normalise_news_records(records, columns, source, limit):
    title_key = _pick_title_key(columns)
    content_key = _pick_content_key(columns, title_key)
    time_key = next((column for column in columns if "时间" in str(column)), None)
    url_key = next((column for column in columns if "链接" in str(column)), None)
    items = []
    for index, row in enumerate(records):
        title = _clean_news_text(row.get(title_key))
        summary = "" if content_key == title_key else _clean_news_text(row.get(content_key))
        if not title:
            title, summary = summary, ""
        if not title:
            continue
        score = sum(keyword in f"{title} {summary}" for keyword in IMPORTANT_NEWS_KEYWORDS)
        if source == "财联社电报":
            score += 2
        items.append({
            "id": f"{source}-{index}-{title[:16]}",
            "title": title,
            "summary": summary or "重点财经快讯，建议结合市场走势跟踪影响。",
            "source": source,
            "published_at": str(row.get(time_key) or "最新"),
            "url": str(row.get(url_key) or ""),
            "importance": score
        })

    important = [item for item in items if item["importance"] > 0]
    selected = sorted(
        important or items,
        key=lambda item: item["published_at"],
        reverse=True
    )[:limit]
    for item in selected:
        item.pop("importance", None)
    return selected


def _clean_news_text(value):
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()
