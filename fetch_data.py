"""
Тянет 90 дней дневной статистики по кампаниям Дубравы из Reports API
и пишет data.json для дашборда. Только чтение.
Токен берётся из переменной окружения YANDEX_DIRECT_TOKEN
(в GitHub Actions — из секрета; локально — из .env).
"""
import os, json, time
from datetime import date, timedelta, datetime, timezone
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TOKEN = os.environ.get("YANDEX_DIRECT_TOKEN")
if not TOKEN:
    raise SystemExit("Нет YANDEX_DIRECT_TOKEN")

DAYS = 90
date_to = date.today()
date_from = date_to - timedelta(days=DAYS - 1)

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept-Language": "ru",
    "Content-Type": "application/json; charset=utf-8",
    "processingMode": "auto",
    "returnMoneyInMicros": "false",
    "skipReportHeader": "true",
    "skipReportSummary": "true",
}
body = {
    "params": {
        "SelectionCriteria": {"DateFrom": date_from.isoformat(), "DateTo": date_to.isoformat()},
        "FieldNames": ["Date", "CampaignId", "CampaignName", "Impressions", "Clicks", "Cost", "Conversions"],
        "ReportName": "dash_" + datetime.now().strftime("%Y%m%d%H%M%S"),
        "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
        "DateRangeType": "CUSTOM_DATE",
        "Format": "TSV",
        "IncludeVAT": "YES",
        "IncludeDiscount": "NO",
    }
}
url = "https://api.direct.yandex.com/json/v5/reports"

resp = None
for _ in range(20):
    resp = requests.post(url, json=body, headers=headers)
    if resp.status_code in (201, 202):
        print("отчёт готовится, жду...")
        time.sleep(6)
        continue
    break
if resp.status_code != 200:
    raise SystemExit(f"Reports error HTTP {resp.status_code}: {resp.text[:600]}")

lines = [l for l in resp.text.split("\n") if l.strip()]
head = lines[0].split("\t")
idx = {name: i for i, name in enumerate(head)}

def num(s):
    s = (s or "").strip()
    if s in ("--", "", "-"):
        return 0.0
    return float(s.replace(",", "."))

rows = []
for line in lines[1:]:
    p = line.split("\t")
    y, m, dd = p[idx["Date"]].split("-")
    cost = num(p[idx["Cost"]])
    clicks = int(num(p[idx["Clicks"]]))
    conv = int(num(p[idx["Conversions"]]))
    rows.append({
        "c": p[idx["CampaignName"]],
        "id": p[idx["CampaignId"]],
        "d": f"{dd}.{m}.{y}",
        "shows": int(num(p[idx["Impressions"]])),
        "clicks": clicks,
        "cost": round(cost, 2),
        "conv": conv,
        "cr": round(conv / clicks * 100, 2) if clicks else None,
        "cpa": round(cost / conv, 2) if conv else None,
    })

rows.sort(key=lambda r: (r["d"].split(".")[::-1], r["c"]))

msk = datetime.now(timezone.utc) + timedelta(hours=3)
payload = {
    "updated": msk.strftime("%d.%m.%Y %H:%M") + " МСК",
    "days": DAYS,
    "rows": rows,
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
print(f"data.json: {len(rows)} строк, обновлено {payload['updated']}")
