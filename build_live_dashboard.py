"""
Kkhavo Interactive Dashboard Generator (v2)
Fully client-side interactive — date range filters everything: KPIs, campaign
cards, funnel, creative tables. Revenue/AOV/ROAS are computed from Meta's own
pixel purchase values (no GA4 dependency).

Usage: python3 build_live_dashboard.py
"""
import os, json, requests
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

META_TOKEN  = os.getenv("META_ACCESS_TOKEN")
AD_ACCOUNT  = "act_26278626595106588"
DATE_TODAY  = date.today().isoformat()

CAMPAIGNS = [
    {"id": "120250638572270577", "key": "cold_v2", "name": "Cold Campaign v2",       "start": "2026-06-18"},
    {"id": "120249093451450577", "key": "cold",    "name": "Cold Campaign v1",        "start": "2026-06-01"},
    {"id": "120250204801330577", "key": "test",    "name": "Test Campaign (CBO)",     "start": "2026-06-01"},
]

BOOST_CAMPAIGN_IDS = [
    "120250042105720577",
    "120250042091900577",
    "120248379576940577",
    "120248016021460577",
    "120247892314930577",
]

FOLLOWERS_FROM_BOOSTS = 106   # client-reported, updated manually
FOLLOWERS_NET_NEW     = 472   # client-reported, updated manually

PURCHASE_KEY = "offsite_conversion.fb_pixel_purchase"
ATC_KEY      = "offsite_conversion.fb_pixel_add_to_cart"
CHECKOUT_KEY = "offsite_conversion.fb_pixel_initiate_checkout"
LPV_KEY      = "landing_page_view"

def parse_action(actions, key):
    return int(float(next((a["value"] for a in actions if a["action_type"] == key), 0)))

def parse_value(values, key):
    return float(next((a["value"] for a in values if a["action_type"] == key), 0))

def fetch_daily_campaign(campaign_id, since, until):
    resp = requests.get(
        f"https://graph.facebook.com/v24.0/{campaign_id}/insights",
        params={
            "fields": "spend,impressions,clicks,actions,action_values",
            "time_increment": 1,
            "time_range": json.dumps({"since": since, "until": until}),
            "access_token": META_TOKEN,
        },
    ).json().get("data", [])
    days = []
    for d in resp:
        acts, vals = d.get("actions", []), d.get("action_values", [])
        days.append({
            "date":        d["date_start"],
            "spend":       round(float(d.get("spend", 0)), 2),
            "impressions": int(d.get("impressions", 0)),
            "clicks":      int(d.get("clicks", 0)),
            "lpv":         parse_action(acts, LPV_KEY),
            "atc":         parse_action(acts, ATC_KEY),
            "checkout":    parse_action(acts, CHECKOUT_KEY),
            "purchases":   parse_action(acts, PURCHASE_KEY),
            "revenue":     round(parse_value(vals, PURCHASE_KEY), 2),
        })
    return days

def fetch_daily_ads(campaign_id, since, until):
    resp = requests.get(
        f"https://graph.facebook.com/v24.0/{campaign_id}/insights",
        params={
            "fields": "ad_name,spend,clicks,impressions,actions,action_values",
            "level": "ad",
            "time_increment": 1,
            "time_range": json.dumps({"since": since, "until": until}),
            "access_token": META_TOKEN,
        },
    ).json().get("data", [])
    ads = {}
    for d in resp:
        name = d["ad_name"].split(" — ", 1)[-1] if " — " in d["ad_name"] else d["ad_name"]
        acts, vals = d.get("actions", []), d.get("action_values", [])
        ads.setdefault(name, []).append({
            "date":        d["date_start"],
            "spend":       round(float(d.get("spend", 0)), 2),
            "impressions": int(d.get("impressions", 0)),
            "clicks":      int(d.get("clicks", 0)),
            "atc":         parse_action(acts, ATC_KEY),
            "checkout":    parse_action(acts, CHECKOUT_KEY),
            "purchases":   parse_action(acts, PURCHASE_KEY),
            "revenue":     round(parse_value(vals, PURCHASE_KEY), 2),
        })
    return ads

print("Fetching campaign data...")
campaigns_data = {}
for c in CAMPAIGNS:
    campaigns_data[c["key"]] = {
        "name":  c["name"],
        "id":    c["id"],
        "start": c["start"],
        "daily": fetch_daily_campaign(c["id"], c["start"], DATE_TODAY),
        "ads":   fetch_daily_ads(c["id"], c["start"], DATE_TODAY),
    }

print("Fetching Instagram boost data...")
boost_rows = []
for bid in BOOST_CAMPAIGN_IDS:
    info = requests.get(
        f"https://graph.facebook.com/v24.0/{bid}",
        params={"fields": "name,status", "access_token": META_TOKEN},
    ).json()
    ins = requests.get(
        f"https://graph.facebook.com/v24.0/{bid}/insights",
        params={"fields": "spend,impressions,reach,frequency,ctr,actions", "date_preset": "maximum", "access_token": META_TOKEN},
    ).json().get("data", [])
    row = ins[0] if ins else {}
    acts = row.get("actions", [])
    boost_rows.append({
        "name":        info.get("name", "").replace("Instagram post: ", ""),
        "status":      info.get("status", ""),
        "spend":       round(float(row.get("spend", 0)), 2),
        "reach":       int(row.get("reach", 0)),
        "impressions": int(row.get("impressions", 0)),
        "frequency":   round(float(row.get("frequency", 0)), 2),
        "ctr":         round(float(row.get("ctr", 0)), 2),
        "video_views": parse_action(acts, "video_view"),
    })

updated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

global_start = min(c["start"] for c in CAMPAIGNS)

# ── HTML ──────────────────────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kkhavo — Live Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Helvetica Neue',Helvetica,Arial,sans-serif; background:#f0efe6; color:#2a2d1a; min-height:100vh; }}
.page {{ max-width:1180px; margin:0 auto; padding:48px 32px 80px; }}

.header {{ display:flex; align-items:flex-end; justify-content:space-between; border-bottom:2px solid #c8c9a8; padding-bottom:28px; margin-bottom:32px; flex-wrap:wrap; gap:12px; }}
.brand-tag {{ font-size:10px; letter-spacing:5px; text-transform:uppercase; color:#5a7028; margin-bottom:10px; }}
.page-title {{ font-family:Georgia,serif; font-size:34px; font-weight:normal; color:#2a2d1a; line-height:1; }}
.page-title span {{ color:#5a7028; }}
.updated {{ font-size:11px; color:#9a9c7a; text-align:right; }}
.updated strong {{ color:#5a7028; }}

.datebar {{ display:flex; align-items:center; gap:10px; margin-bottom:28px; padding:14px 18px; background:#fff; border:1px solid #d4d5b8; border-radius:8px; flex-wrap:wrap; }}
.datebar label {{ font-size:9px; letter-spacing:2px; text-transform:uppercase; color:#5a7028; white-space:nowrap; }}
.datebar input {{ border:1px solid #d4d5b8; border-radius:5px; padding:6px 10px; font-size:12px; color:#2a2d1a; background:#f8f8f2; outline:none; }}
.qbtn {{ background:#fff; color:#5a7028; border:1px solid #a8b870; border-radius:5px; padding:6px 14px; font-size:11px; letter-spacing:0.5px; cursor:pointer; transition:all 0.15s; }}
.qbtn:hover {{ background:#eef2e4; }}
.qbtn.active {{ background:#5a7028; color:#fff; border-color:#5a7028; }}
.rangeinfo {{ font-size:11px; color:#9a9c7a; margin-left:auto; }}

.sec-head {{ display:flex; align-items:center; gap:14px; margin-bottom:18px; margin-top:36px; }}
.sec-tag {{ font-size:9px; letter-spacing:3px; text-transform:uppercase; color:#5a7028; white-space:nowrap; }}
.sec-line {{ flex:1; height:1px; background:#d4d5b8; }}

.kpi-row {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; }}
.kpi {{ background:#fff; border:1px solid #d4d5b8; border-radius:8px; padding:18px 14px; text-align:center; position:relative; }}
.kpi.accent {{ border-color:#7a9040; background:#f4f6ec; }}
.kpi-label {{ font-size:9px; letter-spacing:2px; text-transform:uppercase; color:#9a9c7a; margin-bottom:8px; }}
.kpi-val {{ font-family:Georgia,serif; font-size:25px; line-height:1; color:#2a2d1a; }}
.kpi-sub {{ font-size:10px; color:#9a9c7a; margin-top:5px; }}
.kpi-delta {{ font-size:10px; font-weight:bold; margin-top:4px; }}
.kpi-delta.up {{ color:#3d7a1a; }}
.kpi-delta.down {{ color:#c03a2a; }}

.camp-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:18px; }}
.camp-card {{ background:#fff; border:2px solid #d4d5b8; border-radius:10px; padding:22px; cursor:pointer; transition:all 0.15s; }}
.camp-card:hover {{ border-color:#a8b870; transform:translateY(-1px); }}
.camp-card.selected {{ border-color:#5a7028; background:#f4f6ec; }}
.camp-card-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
.camp-card-name {{ font-family:Georgia,serif; font-size:17px; color:#2a2d1a; }}
.camp-card-badge {{ font-size:8px; letter-spacing:1px; text-transform:uppercase; background:#eef2e4; color:#5a7028; border:1px solid #a8b870; border-radius:3px; padding:2px 7px; }}
.camp-mini-row {{ display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; }}
.camp-mini {{ text-align:center; }}
.camp-mini-label {{ font-size:8px; letter-spacing:1px; text-transform:uppercase; color:#9a9c7a; margin-bottom:4px; }}
.camp-mini-val {{ font-family:Georgia,serif; font-size:17px; color:#2a2d1a; }}
.roas-good {{ color:#3d7a1a !important; }}
.roas-mid {{ color:#b8860b !important; }}
.roas-bad {{ color:#c03a2a !important; }}

.detail-panel {{ display:none; margin-top:18px; }}
.card {{ background:#fff; border:1px solid #d4d5b8; border-radius:8px; padding:24px; margin-bottom:20px; }}
.card-title {{ font-size:10px; letter-spacing:2px; text-transform:uppercase; color:#5a7028; margin-bottom:16px; }}

.funnel {{ display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 0; }}
.vfunnel-step {{ display:flex; align-items:center; justify-content:space-between; padding:14px 24px; border-radius:6px; min-width:30%; color:#fff; }}
.vfunnel-label {{ font-size:10px; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,0.75); }}
.vfunnel-num {{ font-family:Georgia,serif; font-size:22px; }}
.vfunnel-pct {{ font-size:11px; color:rgba(255,255,255,0.6); text-align:right; }}
.vfunnel-drop {{ font-size:10px; color:#9a9c7a; text-align:center; padding:2px 0; }}

table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
thead th {{ font-size:9px; letter-spacing:1.5px; text-transform:uppercase; color:#9a9c7a; padding:10px 12px; text-align:right; border-bottom:1px solid #d4d5b8; background:#f8f8f2; white-space:nowrap; cursor:pointer; user-select:none; }}
thead th:first-child {{ text-align:left; }}
thead th:hover {{ color:#5a7028; }}
tbody tr {{ border-bottom:1px solid #eaead8; }}
tbody tr:last-child {{ border-bottom:none; }}
tbody tr:hover {{ background:#f4f6ec; }}
tbody td {{ padding:11px 12px; color:#5a5c42; text-align:right; }}
tbody td:first-child {{ text-align:left; }}
.badge {{ display:inline-block; font-size:8px; letter-spacing:1px; text-transform:uppercase; background:#eef2e4; color:#5a7028; border:1px solid #a8b870; border-radius:3px; padding:1px 5px; margin-left:6px; }}

.camp-label {{ font-size:9px; letter-spacing:2px; text-transform:uppercase; color:#9a9c7a; margin-bottom:4px; }}
.camp-name-big {{ font-family:Georgia,serif; font-size:19px; color:#2a2d1a; margin-bottom:18px; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <div>
      <div class="brand-tag">Kkhavo</div>
      <div class="page-title">Live <span>Performance</span> Dashboard</div>
    </div>
    <div class="updated">Last updated<br><strong>{updated_at}</strong></div>
  </div>

  <div class="datebar">
    <label>Date Range</label>
    <input type="date" id="dateFrom">
    <span style="color:#9a9c7a;font-size:12px">to</span>
    <input type="date" id="dateTo">
    <button class="qbtn" onclick="quickRange(0)">Today</button>
    <button class="qbtn" onclick="quickRange(6)">7D</button>
    <button class="qbtn" onclick="quickRange(13)">14D</button>
    <button class="qbtn active" id="allBtn" onclick="quickRange('all')">All</button>
    <span class="rangeinfo" id="rangeInfo"></span>
  </div>

  <!-- TOP KPIs -->
  <div class="sec-head"><span class="sec-tag">Overview — All Campaigns</span><div class="sec-line"></div></div>
  <div class="kpi-row" id="topKpis"></div>

  <!-- CAMPAIGNS -->
  <div class="sec-head"><span class="sec-tag">Campaigns — click to view details</span><div class="sec-line"></div></div>
  <div class="camp-grid" id="campGrid"></div>

  <div class="detail-panel" id="detailPanel">
    <div class="sec-head"><span class="sec-tag" id="detailTag">Campaign Detail</span><div class="sec-line"></div></div>

    <div class="card">
      <div class="camp-label" id="detailLabel">SELECTED CAMPAIGN</div>
      <div class="camp-name-big" id="detailName"></div>
      <div class="kpi-row" id="detailKpis"></div>
    </div>

    <div class="grid2" style="display:grid;grid-template-columns:1fr;gap:20px">
      <div class="card">
        <div class="card-title">Purchase Funnel</div>
        <div class="funnel" id="detailFunnel"></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title" id="detailCreativeTitle">Creative Performance</div>
      <table id="detailTable">
        <thead><tr>
          <th data-key="name">Creative</th>
          <th data-key="spend">Spend</th>
          <th data-key="clicks">Clicks</th>
          <th data-key="atc">ATC</th>
          <th data-key="checkout">Checkout</th>
          <th data-key="purchases">Purchases</th>
          <th data-key="cpp">CPP</th>
          <th data-key="roas">ROAS</th>
        </tr></thead>
        <tbody id="detailTableBody"></tbody>
      </table>
    </div>
  </div>

  <!-- INSTAGRAM BOOSTS -->
  <div class="sec-head"><span class="sec-tag">Instagram Boosts</span><div class="sec-line"></div></div>
  <div class="card">
    <div class="card-title">Boosted Posts — Reach &amp; Followers Gained</div>
    <table>
      <thead><tr><th>Post</th><th>Spend</th><th>Reach</th><th>Frequency</th><th>CTR</th><th>Video Views</th><th>Verdict</th></tr></thead>
      <tbody>{"".join(f'''<tr>
        <td>{b["name"]} {f'<span class="badge">Active</span>' if b["status"]=="ACTIVE" else ""}</td>
        <td>₹{b["spend"]:,.0f}</td>
        <td>{b["reach"]:,}</td>
        <td class="{"roas-bad" if b["frequency"]>=2 else ""}">{b["frequency"]:.2f}</td>
        <td class="{"roas-good" if b["ctr"]>=2 else "roas-mid" if b["ctr"]>=1 else "roas-bad"}">{b["ctr"]:.2f}%</td>
        <td>{b["video_views"]:,}</td>
        <td>{(
            "Too early" if b["status"]=="ACTIVE" and b["reach"]<2000
            else "Keep running" if b["status"]=="ACTIVE" and b["ctr"]>=2
            else "Watch CTR" if b["status"]=="ACTIVE"
            else "Paused — low CTR" if b["status"]!="ACTIVE" and b["ctr"]<1
            else "Paused"
        )}</td>
      </tr>''' for b in boost_rows)}</tbody>
    </table>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px">
      <div style="background:#f4f6ec;border:1px solid #a8b870;border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;color:#5a7028;margin-bottom:6px">Followers From Boosts</div>
        <div style="font-family:Georgia,serif;font-size:26px;color:#2a2d1a">{FOLLOWERS_FROM_BOOSTS}</div>
      </div>
      <div style="background:#f4f6ec;border:1px solid #a8b870;border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;color:#5a7028;margin-bottom:6px">Total Net New Followers</div>
        <div style="font-family:Georgia,serif;font-size:26px;color:#2a2d1a">{FOLLOWERS_NET_NEW}</div>
      </div>
    </div>
  </div>

</div>

<script>
const campaignsData = {json.dumps(campaigns_data)};
const GLOBAL_START = "{global_start}";
const TODAY = "{DATE_TODAY}";
const ROAS_TARGET = 4.0;

let selectedCampaign = null;

function fmtInr(v) {{
  if (v >= 100000) return '₹' + (v/100000).toFixed(1) + 'L';
  if (v >= 1000)   return '₹' + (v/1000).toFixed(1) + 'k';
  return '₹' + Math.round(v).toLocaleString();
}}
function pct(num, denom) {{ return denom ? (num/denom*100).toFixed(1) + '%' : '—'; }}

function sumDaily(days, from, to) {{
  const s = {{spend:0, purchases:0, revenue:0, atc:0, checkout:0, lpv:0, clicks:0, impressions:0}};
  for (const d of days) {{
    if (d.date >= from && d.date <= to) {{
      s.spend += d.spend; s.purchases += d.purchases; s.revenue += d.revenue;
      s.atc += d.atc; s.checkout += d.checkout; s.lpv += d.lpv;
      s.clicks += d.clicks; s.impressions += d.impressions;
    }}
  }}
  return s;
}}

function metrics(s) {{
  return {{
    ...s,
    aov:  s.purchases > 0 ? s.revenue / s.purchases : 0,
    cac:  s.purchases > 0 ? s.spend / s.purchases : 0,
    roas: s.spend > 0 ? s.revenue / s.spend : 0,
  }};
}}

function prevRange(from, to) {{
  const f = new Date(from), t = new Date(to);
  const days = Math.round((t - f) / 86400000) + 1;
  const prevTo = new Date(f); prevTo.setDate(prevTo.getDate() - 1);
  const prevFrom = new Date(prevTo); prevFrom.setDate(prevFrom.getDate() - days + 1);
  return [prevFrom.toISOString().slice(0,10), prevTo.toISOString().slice(0,10)];
}}

function deltaHtml(curr, prev, higherIsBetter=true) {{
  if (!prev || prev === 0) return '';
  const change = ((curr - prev) / prev) * 100;
  if (Math.abs(change) < 0.1) return '';
  const up = change > 0;
  const good = higherIsBetter ? up : !up;
  const arrow = up ? '▲' : '▼';
  return `<div class="kpi-delta ${{good ? 'up' : 'down'}}">${{arrow}} ${{Math.abs(change).toFixed(0)}}% vs prev period</div>`;
}}

function roasClass(r) {{
  if (r >= ROAS_TARGET - 0.5) return 'roas-good';
  if (r >= 2) return 'roas-mid';
  return 'roas-bad';
}}

function allCampaignsAggregate(from, to) {{
  const agg = {{spend:0, purchases:0, revenue:0, atc:0, checkout:0, lpv:0, clicks:0, impressions:0}};
  for (const key in campaignsData) {{
    const s = sumDaily(campaignsData[key].daily, from, to);
    for (const k in agg) agg[k] += s[k];
  }}
  return metrics(agg);
}}

function renderTopKpis(from, to) {{
  const m = allCampaignsAggregate(from, to);
  const [pf, pt] = prevRange(from, to);
  const pm = allCampaignsAggregate(pf, pt);

  document.getElementById('topKpis').innerHTML = `
    <div class="kpi"><div class="kpi-label">Total Spend</div><div class="kpi-val">${{fmtInr(m.spend)}}</div>${{deltaHtml(m.spend, pm.spend, false)}}</div>
    <div class="kpi"><div class="kpi-label">Purchases</div><div class="kpi-val">${{m.purchases}}</div>${{deltaHtml(m.purchases, pm.purchases, true)}}</div>
    <div class="kpi accent"><div class="kpi-label">Revenue</div><div class="kpi-val">${{fmtInr(m.revenue)}}</div><div class="kpi-sub">Meta pixel value</div>${{deltaHtml(m.revenue, pm.revenue, true)}}</div>
    <div class="kpi accent"><div class="kpi-label">CAC</div><div class="kpi-val">${{m.cac ? fmtInr(m.cac) : '—'}}</div>${{deltaHtml(m.cac, pm.cac, false)}}</div>
    <div class="kpi accent"><div class="kpi-label">ROAS</div><div class="kpi-val ${{roasClass(m.roas)}}">${{m.roas.toFixed(2)}}x</div><div class="kpi-sub">Target ${{ROAS_TARGET}}x</div>${{deltaHtml(m.roas, pm.roas, true)}}</div>
  `;
}}

function renderCampaignCards(from, to) {{
  const grid = document.getElementById('campGrid');
  grid.innerHTML = '';
  for (const key in campaignsData) {{
    const c = campaignsData[key];
    const s = sumDaily(c.daily, from, to);
    const m = metrics(s);
    const card = document.createElement('div');
    card.className = 'camp-card' + (selectedCampaign === key ? ' selected' : '');
    card.onclick = () => {{ selectedCampaign = (selectedCampaign === key) ? null : key; refresh(); }};
    card.innerHTML = `
      <div class="camp-card-head">
        <div class="camp-card-name">${{c.name}}</div>
        <div class="camp-card-badge">${{m.purchases}} purchases</div>
      </div>
      <div class="camp-mini-row">
        <div class="camp-mini"><div class="camp-mini-label">Spend</div><div class="camp-mini-val">${{fmtInr(m.spend)}}</div></div>
        <div class="camp-mini"><div class="camp-mini-label">AOV</div><div class="camp-mini-val">${{m.aov ? fmtInr(m.aov) : '—'}}</div></div>
        <div class="camp-mini"><div class="camp-mini-label">CAC</div><div class="camp-mini-val">${{m.cac ? fmtInr(m.cac) : '—'}}</div></div>
        <div class="camp-mini"><div class="camp-mini-label">ROAS</div><div class="camp-mini-val ${{roasClass(m.roas)}}">${{m.roas.toFixed(2)}}x</div></div>
      </div>
    `;
    grid.appendChild(card);
  }}
}}

let sortKey = 'spend', sortDir = -1;

function renderDetail(from, to) {{
  const panel = document.getElementById('detailPanel');
  if (!selectedCampaign) {{ panel.style.display = 'none'; return; }}
  panel.style.display = 'block';

  const c = campaignsData[selectedCampaign];
  const s = sumDaily(c.daily, from, to);
  const m = metrics(s);

  document.getElementById('detailTag').textContent = c.name + ' — Detail';
  document.getElementById('detailName').textContent = c.name;
  document.getElementById('detailCreativeTitle').textContent = c.name + ' — Creative Performance';

  document.getElementById('detailKpis').innerHTML = `
    <div class="kpi"><div class="kpi-label">Spend</div><div class="kpi-val">${{fmtInr(m.spend)}}</div></div>
    <div class="kpi"><div class="kpi-label">Purchases</div><div class="kpi-val">${{m.purchases}}</div></div>
    <div class="kpi accent"><div class="kpi-label">AOV</div><div class="kpi-val">${{m.aov ? fmtInr(m.aov) : '—'}}</div></div>
    <div class="kpi accent"><div class="kpi-label">CAC</div><div class="kpi-val">${{m.cac ? fmtInr(m.cac) : '—'}}</div></div>
    <div class="kpi accent"><div class="kpi-label">ROAS</div><div class="kpi-val ${{roasClass(m.roas)}}">${{m.roas.toFixed(2)}}x</div></div>
  `;

  const steps = [
    ['Landing Page', s.lpv, null, '#3d5a1a'],
    ['Add to Cart',  s.atc, s.lpv, '#4f7022'],
    ['Checkout',     s.checkout, s.atc, '#5a7028'],
    ['Purchases',    s.purchases, s.checkout, '#6a8a32'],
  ];
  document.getElementById('detailFunnel').innerHTML = steps.map(([label, val, denom, color], i) => {{
    const width = s.lpv > 0 ? Math.max(20, Math.round(val / s.lpv * 100)) : 30;
    const dropHtml = i > 0 ? `<div class="vfunnel-drop">▼ ${{pct(steps[i-1][1]-val, steps[i-1][1])}} dropped</div>` : '';
    return `${{dropHtml}}<div class="vfunnel-step" style="width:${{width}}%;background:${{color}}">
      <div><div class="vfunnel-label">${{label}}</div><div class="vfunnel-num">${{val.toLocaleString()}}</div></div>
      <div class="vfunnel-pct">${{denom ? pct(val, denom) : ''}}</div>
    </div>`;
  }}).join('');

  const rows = Object.entries(c.ads).map(([name, days]) => {{
    const ad_s = sumDaily(days.map(d => ({{...d, lpv:0}})), from, to);
    const cpp  = ad_s.purchases > 0 ? ad_s.spend / ad_s.purchases : null;
    const roas = ad_s.spend > 0 ? ad_s.revenue / ad_s.spend : 0;
    return {{ name, ...ad_s, cpp, roas }};
  }});

  rows.sort((a, b) => (a[sortKey] - b[sortKey]) * sortDir);

  document.getElementById('detailTableBody').innerHTML = rows.map(r => `
    <tr>
      <td>${{r.name}}${{r.purchases > 0 ? '<span class="badge">Converting</span>' : ''}}</td>
      <td>${{fmtInr(r.spend)}}</td>
      <td>${{r.clicks}}</td>
      <td>${{r.atc}}</td>
      <td>${{r.checkout}}</td>
      <td><b>${{r.purchases}}</b></td>
      <td>${{r.cpp ? fmtInr(r.cpp) : '—'}}</td>
      <td class="${{roasClass(r.roas)}}">${{r.roas > 0 ? r.roas.toFixed(2)+'x' : '—'}}</td>
    </tr>
  `).join('');
}}

document.querySelectorAll('#detailTable thead th').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.key;
    if (sortKey === key) sortDir *= -1; else {{ sortKey = key; sortDir = -1; }}
    refresh();
  }});
}});

function refresh() {{
  const from = document.getElementById('dateFrom').value;
  const to   = document.getElementById('dateTo').value;
  if (!from || !to) return;
  document.getElementById('rangeInfo').textContent = from + ' → ' + to;
  renderTopKpis(from, to);
  renderCampaignCards(from, to);
  renderDetail(from, to);
}}

function quickRange(n) {{
  document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active'));
  let from;
  if (n === 'all') {{
    from = GLOBAL_START;
    document.getElementById('allBtn').classList.add('active');
  }} else {{
    const d = new Date(TODAY); d.setDate(d.getDate() - n);
    from = d.toISOString().slice(0,10);
    event.target.classList.add('active');
  }}
  document.getElementById('dateFrom').value = from;
  document.getElementById('dateTo').value = TODAY;
  refresh();
}}

document.getElementById('dateFrom').addEventListener('change', refresh);
document.getElementById('dateTo').addEventListener('change', refresh);

document.getElementById('dateFrom').value = GLOBAL_START;
document.getElementById('dateTo').value = TODAY;
refresh();
</script>
</body>
</html>"""

out = os.getenv("OUTPUT_PATH", "/Users/gautami/agency/clients/kkhavo/kkhavo_live_dashboard.html")
with open(out, "w") as f:
    f.write(html)

print(f"✓ Dashboard saved: {out}")
