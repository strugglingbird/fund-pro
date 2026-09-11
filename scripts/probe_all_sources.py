"""Probe every external data source used by the fund-pro backend."""
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

SSL_CONTEXT = ssl._create_unverified_context()
USER_AGENT = "Mozilla/5.0 FundProWorkbench/0.1"
CHINA_TZ = timezone(timedelta(hours=8))


def beijing_now():
    """Return Beijing-local naive datetime so probe dates match the backend convention."""
    return datetime.now(CHINA_TZ).replace(tzinfo=None)


def http_get(url, headers=None, encoding="utf-8", timeout=15):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors="ignore")


def http_post_json(url, payload, headers=None, timeout=15):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers=headers or {"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST"
    )
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def probe(name, url, headers=None, encoding="utf-8", timeout=15, check=None):
    try:
        body = http_get(url, headers=headers, encoding=encoding, timeout=timeout)
        ok = True if check is None else check(body)
        snippet = body[:180].replace("\n", " ").replace("\r", " ")
        return {"name": name, "url": url, "status": "OK" if ok else "PARSE_FAIL", "snippet": snippet}
    except urllib.error.HTTPError as e:
        return {"name": name, "url": url, "status": f"HTTP_{e.code}", "snippet": str(e)[:120]}
    except urllib.error.URLError as e:
        return {"name": name, "url": url, "status": "NETWORK_ERROR", "snippet": str(e.reason)[:120]}
    except Exception as e:
        return {"name": name, "url": url, "status": "EXCEPTION", "snippet": str(e)[:120]}


def main():
    results = []

    # Tencent quotes
    results.append(probe("tencent_quote_single", "https://qt.gtimg.cn/q=sh000001", encoding="gbk",
                         check=lambda b: "sh000001" in b and "~" in b))
    results.append(probe("tencent_quote_batch", "https://qt.gtimg.cn/q=sh000001,sz399001", encoding="gbk",
                         check=lambda b: "~" in b and b.count("v_") >= 2))
    results.append(probe("tencent_intraday", "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh000001",
                         check=lambda b: "data" in b and "sh000001" in b))
    results.append(probe("tencent_trading_days", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,,,10,qfq",
                         check=lambda b: "sh000001" in b and ("qfqday" in b or "day" in b)))
    results.append(probe("tencent_sector_rank", "https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank?board_type=hy&sort_type=price&direct=down&offset=0&count=100",
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"},
                         check=lambda b: "rank_list" in b))

    # Market index symbols
    for sym in ["sh000001", "sz399001", "sz399006", "sh000688", "hkHSI", "hkHSTECH", "usDJI", "usIXIC", "usINX"]:
        results.append(probe(f"tencent_index_{sym}", f"https://qt.gtimg.cn/q={sym}", encoding="gbk",
                             check=lambda b, s=sym: s in b and "~" in b))

    # Yahoo
    results.append(probe("yahoo_dji", "https://query1.finance.yahoo.com/v8/finance/chart/%5EDJI?range=1d&interval=5m",
                         headers={"User-Agent": "Mozilla/5.0"},
                         check=lambda b: "chart" in b and "result" in b))

    # fund123
    fund123_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
        "X-API-Key": "foobar"
    }
    results.append(probe("fund123_fund_page", "https://www.fund123.cn/fund",
                         headers=fund123_headers,
                         check=lambda b: "csrf" in b.lower() or "fund123" in b.lower() or "<html" in b.lower()))

    try:
        page = http_get("https://www.fund123.cn/fund", headers=fund123_headers)
        import re
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="") if csrf_match else None
        results.append({"name": "fund123_csrf_extract", "status": "OK" if csrf else "FAIL", "snippet": csrf or page[:120]})

        if csrf:
            body = http_post_json(f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
                                  {"fundCode": "001632"}, headers=fund123_headers)
            fund_info = json.loads(body).get("fundInfo") or {}
            results.append({"name": "fund123_searchFund", "status": "OK" if fund_info.get("key") else "FAIL",
                            "snippet": body[:200]})
            product_id = fund_info.get("key")
            if product_id:
                body2 = http_post_json(f"https://www.fund123.cn/api/fund/queryFundEstimateIntraday?_csrf={csrf}",
                                       {"startTime": beijing_now().strftime("%Y-%m-%d"),
                                        "endTime": (beijing_now()+timedelta(days=1)).strftime("%Y-%m-%d"),
                                        "limit": 10, "productId": product_id, "format": True, "source": "WEALTHBFFWEB"},
                                       headers=fund123_headers)
                results.append({"name": "fund123_queryFundEstimateIntraday", "status": "OK" if json.loads(body2).get("list") else "EMPTY",
                                "snippet": body2[:200]})
                body3 = http_post_json(f"https://www.fund123.cn/api/fund/queryFundHistoryNetValueList?_csrf={csrf}",
                                       {"productId": product_id, "startDate": "20260101", "endDate": "20260930",
                                        "pageNum": 1, "pageSize": 10}, headers=fund123_headers)
                results.append({"name": "fund123_queryFundHistoryNetValueList", "status": "OK" if (json.loads(body3).get("list") or (json.loads(body3).get("data") or {}).get("list")) else "EMPTY",
                                "snippet": body3[:200]})
                body4 = http_post_json(f"https://www.fund123.cn/api/fund/queryFundHolding?_csrf={csrf}",
                                       {"productId": product_id}, headers=fund123_headers)
                results.append({"name": "fund123_queryFundHolding", "status": "OK" if json.loads(body4) else "EMPTY",
                                "snippet": body4[:200]})
                body5 = http_post_json(f"https://www.fund123.cn/api/fund/queryFundQuotationCurves?_csrf={csrf}",
                                       {"productId": product_id, "dateInterval": "THREE_MONTH"},
                                       headers=fund123_headers)
                results.append({"name": "fund123_queryFundQuotationCurves", "status": "OK" if json.loads(body5).get("points") else "EMPTY",
                                "snippet": body5[:200]})
    except Exception as e:
        results.append({"name": "fund123_session", "status": "EXCEPTION", "snippet": str(e)[:120]})

    # AkShare news
    try:
        import akshare as ak
        for label, fn in [("akshare_cls", lambda: ak.stock_info_global_cls(symbol="重点")),
                          ("akshare_sina", ak.stock_info_global_sina),
                          ("akshare_futu", ak.stock_info_global_futu),
                          ("akshare_ths", ak.stock_info_global_ths)]:
            try:
                df = fn()
                ok = df is not None and not df.empty
                results.append({"name": label, "status": "OK" if ok else "EMPTY", "snippet": str(df.head(1).to_dict())[:160] if ok else "empty"})
            except Exception as e:
                results.append({"name": label, "status": "ERROR", "snippet": str(e)[:120]})
    except ImportError:
        results.append({"name": "akshare_import", "status": "MISSING", "snippet": "akshare not installed"})

    # Print summary
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("\n=== SUMMARY ===")
    for r in results:
        if r["status"] != "OK":
            print(f"[FAIL] {r['name']}: {r['status']} | {r.get('snippet','')[:60]}")


if __name__ == "__main__":
    main()
