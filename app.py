"""Multimodal Construction Intelligence Platform
Skill Wallet Capstone Project 1 - Streamlit + Google Gemini.
Zero external databases: all state lives in st.session_state.
"""
from __future__ import annotations

import io
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

import streamlit as st
from PIL import Image

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
APP_TITLE = "Multimodal Construction Intelligence Platform"
DEFAULT_MODEL = "gemini-2.5-flash"
MODEL_OPTIONS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
SEVERITY_ORDER = ["Low", "Medium", "High", "Critical"]

st.set_page_config(page_title=APP_TITLE, page_icon="🏗️", layout="wide",
                   initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3, .cip-title { font-family: 'Bricolage Grotesque', sans-serif !important; letter-spacing: -0.01em; }
.block-container { padding-top: 1.6rem; max-width: 1180px; }
.cip-hero { background: #1D2733; color: #F6F5F2; border-radius: 14px; padding: 1.6rem 1.8rem;
  border-left: 10px solid #E8A317; margin-bottom: 1.2rem; }
.cip-hero h1 { color: #F6F5F2; font-size: 2rem; margin: 0 0 .3rem 0; }
.cip-hero p { color: #B8C2CC; margin: 0; max-width: 62ch; }
.cip-card { background: #fff; border: 1px solid #E2E0DA; border-radius: 10px; padding: .9rem 1.1rem; height: 100%; }
.cip-card .k { color: #5B6773; font-size: .85rem; }
.cip-card .v { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.7rem; color: #1D2733; line-height: 1.2; }
.cip-card .s { color: #5B6773; font-size: .8rem; }
.pill { display: inline-block; padding: .18rem .7rem; border-radius: 999px; font-weight: 600; font-size: .82rem; }
.pill.ok { background: #DDF3E4; color: #17653A; }
.pill.warn { background: #FFF1CC; color: #7A5600; }
.pill.bad { background: #FFE0D6; color: #9A2C0E; }
.pill.crit { background: #7A1B1B; color: #fff; }
.pill.neutral { background: #E7EAEE; color: #33404D; }
.haz { background: #fff; border: 1px solid #E2E0DA; border-left-width: 6px; border-radius: 8px; padding: .75rem 1rem; margin-bottom: .6rem; }
.haz.Low { border-left-color: #3E9B5F; } .haz.Medium { border-left-color: #E8A317; }
.haz.High { border-left-color: #D9531E; } .haz.Critical { border-left-color: #7A1B1B; }
.haz .t { font-weight: 600; } .haz .r { color: #33404D; font-size: .92rem; margin-top: .25rem; }
.alert { border-radius: 10px; padding: .9rem 1.1rem; margin-bottom: .6rem; background: #fff; border: 1px solid #E2E0DA; }
.demo-banner { background: #FFF1CC; color: #7A5600; border-radius: 8px; padding: .5rem .9rem; font-size: .9rem; margin-bottom: .8rem; }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [data-baseweb="tab"]:focus-visible { outline: 2px solid #E8A317; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Small UI helpers
# --------------------------------------------------------------------------- #
def metric_card(label: str, value: str, sub: str = "") -> str:
    return (f'<div class="cip-card"><div class="k">{label}</div>'
            f'<div class="v">{value}</div><div class="s">{sub}</div></div>')


def pill(text: str, kind: str = "neutral") -> str:
    return f'<span class="pill {kind}">{text}</span>'


def status_kind(status: str) -> str:
    s = (status or "").lower()
    if any(w in s for w in ("compliant", "safe", "pass", "good", "stable", "monitor")) and "non" not in s:
        return "ok"
    if "critical" in s or "immediate" in s or "unsafe" in s or "non" in s or "fail" in s:
        return "bad"
    return "warn"


def severity_kind(sev: str) -> str:
    return {"Low": "ok", "Medium": "warn", "High": "bad", "Critical": "crit"}.get(sev, "neutral")


def format_inr(amount: float) -> str:
    """Format rupees as Crores / Lakhs."""
    if amount >= 1e7:
        return f"₹{amount / 1e7:,.2f} Cr"
    if amount >= 1e5:
        return f"₹{amount / 1e5:,.2f} Lakh"
    return f"₹{amount:,.0f}"


def load_image(uploaded) -> Image.Image:
    img = Image.open(io.BytesIO(uploaded.getvalue()))
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    return img


def parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


# --------------------------------------------------------------------------- #
# Gemini service layer
# --------------------------------------------------------------------------- #
@dataclass
class AIConfig:
    api_key: str
    model: str

    @property
    def live(self) -> bool:
        return bool(self.api_key)


def _client(cfg: AIConfig):
    from google import genai  # imported lazily so demo mode never needs it
    return genai.Client(api_key=cfg.api_key)


def gemini_json(cfg: AIConfig, prompt: str, image: Image.Image) -> dict:
    from google.genai import types
    resp = _client(cfg).models.generate_content(
        model=cfg.model,
        contents=[prompt, image],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return parse_json_response(resp.text or "")


def gemini_chat(cfg: AIConfig, system: str, history: list[dict]) -> str:
    from google.genai import types
    contents = [types.Content(role="user" if m["role"] == "user" else "model",
                              parts=[types.Part(text=m["content"])]) for m in history]
    resp = _client(cfg).models.generate_content(
        model=cfg.model, contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
    )
    return resp.text or "I could not generate a reply. Please try again."


SAFETY_PROMPT = """You are a certified construction safety officer auditing a site photo against OSHA 1926
and Indian standards (IS 456 for concrete works, IS 3764 for excavation safety, IS 4130 for demolition).
Assess every visible worker for: hard helmet, high-visibility vest, steel-toe safety boots, safety harness
(where working at height). Also identify site hazards (edge protection, scaffolding, housekeeping,
electrical, excavation, material storage). Only report what is visible; use "Not visible" when unsure.
Return ONLY JSON in this exact schema:
{
 "safety_score": <integer 0-100>,
 "overall_status": "Compliant" | "Needs Improvement" | "Non-Compliant",
 "workers_detected": <integer>,
 "summary": "<2 sentence summary>",
 "ppe_detection": {
   "helmet":      {"status": "Compliant|Non-Compliant|Not visible", "note": "<short>"},
   "high_vis_vest": {"status": "...", "note": "..."},
   "steel_toe_boots": {"status": "...", "note": "..."},
   "safety_harness": {"status": "...", "note": "..."}
 },
 "hazards": [{"hazard": "<name>", "severity": "Low|Medium|High|Critical",
              "standard": "<OSHA / IS clause>", "remedy": "<corrective action>"}]
}"""

CRACK_PROMPT = """You are a structural engineer diagnosing a concrete or masonry surface photo.
Classify the defect as exactly one of: Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling.
Estimate crack width in mm from visible cues (state your uncertainty), reasoning per IS 456 crack-width limits
(0.3 mm typical limit for moderate exposure). Return ONLY JSON in this exact schema:
{
 "defect_type": "Hairline|Settlement|Structural Shear|Thermal Expansion|Spalling",
 "confidence_pct": <integer 0-100>,
 "estimated_crack_width_mm": <number>,
 "crack_pattern": "<vertical / diagonal / map / stair-step etc.>",
 "severity": "Low|Medium|High|Critical",
 "urgency": "Monitor|Repair within 3 months|Repair within 2 weeks|Immediate action",
 "root_causes": ["<cause>", ...],
 "recommended_repairs": [{"method": "<e.g. Epoxy injection, Structural re-grouting, Polymer-modified mortar patching>",
                           "details": "<procedure and materials>"}],
 "monitoring_plan": "<tell-tale / crack gauge instructions>",
 "engineer_note": "<1-2 sentences; advise on-site structural engineer verification>"
}"""

CHAT_SYSTEM = """You are SiteMate, a senior civil/construction engineer assistant for Indian construction sites.
Give practical, concise answers grounded in IS codes (IS 456, IS 800, IS 1786, IS 383, IS 2502), NBC 2016 and OSHA
where relevant. Use bullet points for procedures, state assumptions, and recommend verification by a licensed
structural engineer for any load-bearing or life-safety decision. Current site weather: {weather}."""


# --------------------------------------------------------------------------- #
# Demonstration-mode data
# --------------------------------------------------------------------------- #
DEMO_SAFETY = {
    "safety_score": 62, "overall_status": "Needs Improvement", "workers_detected": 4,
    "summary": "Most workers wear helmets and vests, but footwear and fall protection are inconsistent. "
               "Open edges and loose materials add avoidable risk.",
    "ppe_detection": {
        "helmet": {"status": "Compliant", "note": "4 of 4 workers wearing helmets."},
        "high_vis_vest": {"status": "Compliant", "note": "Vests visible on 3 of 4 workers."},
        "steel_toe_boots": {"status": "Non-Compliant", "note": "One worker appears to be in sandals."},
        "safety_harness": {"status": "Non-Compliant", "note": "Worker near slab edge has no harness."},
    },
    "hazards": [
        {"hazard": "Unprotected slab edge", "severity": "Critical", "standard": "OSHA 1926.502",
         "remedy": "Install guardrails (1.0 m top rail, mid rail, toe board) and enforce harness anchorage."},
        {"hazard": "Loose rebar and debris on walkway", "severity": "Medium", "standard": "OSHA 1926.25",
         "remedy": "Daily housekeeping; designate material stacking zones and cap exposed rebar ends."},
        {"hazard": "Improvised scaffold planking", "severity": "High", "standard": "OSHA 1926.451",
         "remedy": "Replace with certified scaffold boards, add base plates and inspect before each shift."},
        {"hazard": "Fresh concrete without curing cover", "severity": "Low", "standard": "IS 456 cl. 13.5",
         "remedy": "Apply wet hessian or curing compound; cure for at least 7 days (10 for blended cements)."},
    ],
}
DEMO_CRACK = {
    "defect_type": "Structural Shear", "confidence_pct": 78, "estimated_crack_width_mm": 1.8,
    "crack_pattern": "Diagonal, 45 degrees, widening toward the beam-column junction",
    "severity": "High", "urgency": "Repair within 2 weeks",
    "root_causes": ["Insufficient shear reinforcement or stirrup spacing near the support",
                    "Overloading or unanticipated live load transfer",
                    "Differential settlement of the supporting column footing"],
    "recommended_repairs": [
        {"method": "Epoxy injection", "details": "Seal surface, install injection ports at 150 mm c/c and inject low-viscosity epoxy (IS 456 repair practice) until refusal."},
        {"method": "Structural re-grouting", "details": "Remove loose concrete, apply non-shrink cementitious grout and add external jacketing (FRP wrap or steel plates) at the shear zone."}],
    "monitoring_plan": "Fix glass tell-tales and take weekly crack-gauge readings for 8 weeks; escalate if width grows by 0.2 mm.",
    "engineer_note": "Demonstration output. Have a licensed structural engineer verify before any repair work.",
}
DEMO_CHAT = {
    "slump": "For pumped RCC work, target a slump of 100-150 mm (IS 456 Table 7 gives 75-100 mm for beams and columns without pumping). Always run a slump test per batch and add superplasticiser instead of water.",
    "curing": "Cure concrete for at least 7 days with OPC and 10 days with blended cement (IS 456 cl. 13.5). Start within 24 hours; use wet hessian, ponding or curing compound.",
    "cover": "Nominal cover per IS 456 Table 16: 20 mm slabs/walls and 30 mm beams (mild exposure), 40 mm columns, 50 mm footings. Use cover blocks every 1 m.",
    "steel": "Use Fe500D (IS 1786) for seismic zones. Typical consumption in a residential RCC building is 3.5-4.5 kg per sq ft built-up.",
}


# --------------------------------------------------------------------------- #
# Valuation model (illustrative planning assumptions, INR)
# --------------------------------------------------------------------------- #
STRUCTURES = {  # cost per sqft by tier [T1, T2, T3], steel kg/sqft, cement bags/sqft
    "RCC Framed Residential":   {"cost": [2400, 2000, 1700], "steel": 4.0, "cement": 0.45},
    "Load-Bearing Masonry":     {"cost": [1900, 1600, 1350], "steel": 2.2, "cement": 0.40},
    "Commercial RCC Complex":   {"cost": [3200, 2650, 2200], "steel": 5.0, "cement": 0.50},
    "Steel Frame Industrial":   {"cost": [2800, 2350, 2000], "steel": 8.5, "cement": 0.25},
}
TIERS = {"Tier 1 (Mumbai, Delhi NCR, Bengaluru)": 0, "Tier 2 (Indore, Pune, Jaipur)": 1, "Tier 3 (Smaller cities & towns)": 2}
MARKET_RATE = [11000, 6500, 3800]   # INR per sqft ready market value by tier
LAND_SHARE = 0.35                   # share of market value attributable to land
MILESTONES = [(0, "Site setup"), (10, "Foundation"), (30, "Plinth & columns"), (50, "Slab & structure"),
              (70, "Masonry & services"), (85, "Finishing"), (100, "Handover")]


def compute_valuation(structure: str, sqft: int, tier_idx: int, pct: int) -> dict:
    spec = STRUCTURES[structure]
    budget = spec["cost"][tier_idx] * sqft
    capex = budget * pct / 100
    full_value = MARKET_RATE[tier_idx] * sqft
    current_value = full_value * (LAND_SHARE + (1 - LAND_SHARE) * pct / 100)
    return {
        "budget": budget, "capex": capex, "full_value": full_value, "current_value": current_value,
        "steel_total_t": spec["steel"] * sqft / 1000, "cement_total_bags": spec["cement"] * sqft,
        "steel_used_t": spec["steel"] * sqft / 1000 * min(1, pct / 70),   # structure ~70% of the work consumes steel
        "cement_used_bags": spec["cement"] * sqft * min(1, pct / 80),
    }


def pollinations_url(prompt: str, seed: int) -> str:
    return (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            f"?width=1024&height=640&nologo=true&seed={seed}")


# --------------------------------------------------------------------------- #
# Weather advisories
# --------------------------------------------------------------------------- #
WEATHER = {
    "Normal": {"icon": "☀️", "level": "ok", "alerts": [
        ("Routine operations", "Proceed with standard toolbox talk and daily PPE checks."),
        ("Hydration and rest", "Provide drinking water points and shaded rest areas."),
        ("Housekeeping", "Clear walkways and stack materials before shift end.")]},
    "High Wind": {"icon": "💨", "level": "bad", "alerts": [
        ("Suspend crane operations", "Stop tower and mobile crane lifts when sustained wind exceeds 36 km/h (about 10 m/s); lower booms and set slew brakes to free-wheel."),
        ("Secure the site", "Lash loose sheets, formwork and scaffolding boards; check scaffold ties and hoarding."),
        ("Work at height", "Stop work on open slabs, façade and roof edges; keep workers away from cantilevered areas.")]},
    "Heavy Rain": {"icon": "🌧️", "level": "bad", "alerts": [
        ("Electrical hazard mitigation", "De-energise temporary panels in wet zones, use RCCB/ELCB-protected circuits and keep cable joints off the ground."),
        ("Excavation and shoring", "Inspect trench walls for slips; pump out water and halt entry until a competent person clears it (IS 3764)."),
        ("Concrete works", "Postpone pours; protect fresh concrete with tarpaulin and avoid rainwater dilution."),
        ("Slip control", "Lay anti-skid mats on ramps and ladders; stop hot work and lifting if visibility is poor.")]},
    "Extreme Heat": {"icon": "🔥", "level": "warn", "alerts": [
        ("Concrete curing protocol", "Pour early morning or night; keep concrete below 35 °C at placement, use chilled water or ice, retarding admixture, and start wet curing immediately (IS 456 cl. 13.5)."),
        ("Heat-stress prevention", "Enforce 10-15 minute rest per hour above 38 °C, provide ORS and shade, and watch for cramps and dizziness."),
        ("Steel and formwork", "Shade rebar and shuttering; hot steel causes burns and rapid moisture loss from concrete."),
        ("Work window", "Shift heavy manual work to before 11:00 and after 16:00.")]},
}


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
def render_safety(report: dict) -> None:
    score = int(report.get("safety_score", 0))
    status = report.get("overall_status", "Unknown")
    hazards = sorted(report.get("hazards", []), key=lambda h: -SEVERITY_ORDER.index(h.get("severity", "Low"))
                     if h.get("severity") in SEVERITY_ORDER else 0)
    crit = sum(1 for h in hazards if h.get("severity") in ("High", "Critical"))
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Safety score", f"{score}/100", "Higher is safer"), unsafe_allow_html=True)
    c2.markdown(metric_card("Overall status", pill(status, status_kind(status))), unsafe_allow_html=True)
    c3.markdown(metric_card("Workers detected", str(report.get("workers_detected", "n/a"))), unsafe_allow_html=True)
    c4.markdown(metric_card("High / Critical hazards", str(crit), f"{len(hazards)} hazards total"), unsafe_allow_html=True)
    st.progress(max(0, min(score, 100)) / 100)
    if report.get("summary"):
        st.write(report["summary"])

    st.markdown("#### PPE checklist")
    labels = {"helmet": "Helmet", "high_vis_vest": "High-vis vest",
              "steel_toe_boots": "Steel-toe boots", "safety_harness": "Safety harness"}
    cols = st.columns(4)
    for col, (key, label) in zip(cols, labels.items()):
        item = report.get("ppe_detection", {}).get(key, {"status": "Not visible", "note": ""})
        kind = {"Compliant": "ok", "Non-Compliant": "bad"}.get(item.get("status"), "neutral")
        col.markdown(metric_card(label, pill(item.get("status", "n/a"), kind), item.get("note", "")),
                     unsafe_allow_html=True)

    st.markdown("#### Identified hazards")
    if not hazards:
        st.success("No hazards identified in this image.")
    for h in hazards:
        sev = h.get("severity", "Low")
        st.markdown(
            f'<div class="haz {sev}"><div class="t">{h.get("hazard", "Hazard")} &nbsp;{pill(sev, severity_kind(sev))}'
            f' <span style="color:#5B6773;font-size:.82rem">{h.get("standard", "")}</span></div>'
            f'<div class="r"><b>Remedy:</b> {h.get("remedy", "")}</div></div>', unsafe_allow_html=True)


def render_crack(report: dict) -> None:
    width = report.get("estimated_crack_width_mm", 0)
    sev = report.get("severity", "Medium")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Defect type", report.get("defect_type", "n/a"),
                            f'Confidence {report.get("confidence_pct", "n/a")}%'), unsafe_allow_html=True)
    c2.markdown(metric_card("Crack width", f"{width} mm", "IS 456 limit ~0.3 mm"), unsafe_allow_html=True)
    c3.markdown(metric_card("Severity", pill(sev, severity_kind(sev))), unsafe_allow_html=True)
    c4.markdown(metric_card("Urgency", report.get("urgency", "n/a")), unsafe_allow_html=True)
    st.caption(f"Pattern: {report.get('crack_pattern', 'n/a')}")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Likely root causes")
        for cause in report.get("root_causes", []):
            st.markdown(f"- {cause}")
        st.markdown("#### Monitoring plan")
        st.write(report.get("monitoring_plan", "n/a"))
    with right:
        st.markdown("#### Recommended engineering repairs")
        for rep in report.get("recommended_repairs", []):
            st.markdown(f"**{rep.get('method', 'Repair')}**  \n{rep.get('details', '')}")
    if report.get("engineer_note"):
        st.info(report["engineer_note"])


def run_analysis(cfg: AIConfig, uploaded, prompt: str, demo: dict, state_key: str) -> None:
    """Run (live or demo) analysis and cache the result in session state."""
    try:
        if not cfg.live:
            st.session_state[state_key] = {"data": demo, "demo": True}
            return
        image = load_image(uploaded)
        with st.spinner("Analyzing image with Gemini..."):
            data = gemini_json(cfg, prompt, image)
        st.session_state[state_key] = {"data": data, "demo": False}
    except Exception as exc:  # noqa: BLE001 - surface any API/parsing failure gracefully
        st.error(f"Analysis failed ({type(exc).__name__}): {exc}. Showing demonstration output instead.")
        st.session_state[state_key] = {"data": demo, "demo": True}


def analysis_tab(cfg: AIConfig, key: str, title: str, hint: str, prompt: str, demo: dict, renderer, fname: str) -> None:
    st.subheader(title)
    uploaded = st.file_uploader(hint, type=["jpg", "jpeg", "png"], key=f"up_{key}")
    if uploaded is None:
        st.info("Upload a JPG or PNG to begin." + ("" if cfg.live else " Demo mode will return sample results."))
        return
    left, right = st.columns([1, 1.6])
    with left:
        try:
            st.image(load_image(uploaded), use_container_width=True)
        except Exception:  # noqa: BLE001
            st.error("This file could not be read as an image. Upload a valid JPG or PNG.")
            return
        if st.button("Run analysis", type="primary", key=f"btn_{key}"):
            run_analysis(cfg, uploaded, prompt, demo, f"res_{key}")
    with right:
        res = st.session_state.get(f"res_{key}")
        if not res:
            st.write("Press **Run analysis** to generate the report.")
            return
        if res["demo"]:
            st.markdown('<div class="demo-banner">Demonstration mode: sample output, not derived from your image.</div>',
                        unsafe_allow_html=True)
    if res:
        renderer(res["data"])
        report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                  "mode": "demo" if res["demo"] else "live", "model": cfg.model, **res["data"]}
        st.download_button("Download JSON report", json.dumps(report, indent=2),
                           file_name=f"{fname}_{datetime.now():%Y%m%d_%H%M}.json", mime="application/json",
                           key=f"dl_{key}")
        with st.expander("View raw JSON"):
            st.json(report)


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def tab_planning() -> None:
    st.subheader("Planning and real estate valuation")
    c1, c2 = st.columns(2)
    structure = c1.selectbox("Structure type", list(STRUCTURES))
    tier_name = c2.selectbox("Location tier", list(TIERS))
    c3, c4 = st.columns(2)
    sqft = c3.number_input("Built-up area (sq ft)", min_value=100, max_value=1_000_000, value=2400, step=100)
    pct = c4.slider("Completion (%)", 0, 100, 40)
    v = compute_valuation(structure, int(sqft), TIERS[tier_name], pct)

    m = st.columns(4)
    m[0].markdown(metric_card("Total project budget", format_inr(v["budget"]), "Estimated construction cost"), unsafe_allow_html=True)
    m[1].markdown(metric_card("Capital expenditure", format_inr(v["capex"]), f"{pct}% of budget incurred"), unsafe_allow_html=True)
    m[2].markdown(metric_card("Current asset value", format_inr(v["current_value"]), "Land plus built portion"), unsafe_allow_html=True)
    m[3].markdown(metric_card("Value at completion", format_inr(v["full_value"]), "Ready market value"), unsafe_allow_html=True)

    st.markdown("#### Material requirements")
    s = st.columns(4)
    s[0].markdown(metric_card("Steel (total)", f"{v['steel_total_t']:.1f} t", "Fe500D reinforcement"), unsafe_allow_html=True)
    s[1].markdown(metric_card("Steel used so far", f"{v['steel_used_t']:.1f} t"), unsafe_allow_html=True)
    s[2].markdown(metric_card("Cement (total)", f"{v['cement_total_bags']:,.0f} bags", "50 kg bags"), unsafe_allow_html=True)
    s[3].markdown(metric_card("Cement used so far", f"{v['cement_used_bags']:,.0f} bags"), unsafe_allow_html=True)

    st.markdown("#### Milestone progress")
    st.progress(pct / 100)
    reached = [n for p, n in MILESTONES if pct >= p]
    nxt = next(((p, n) for p, n in MILESTONES if p > pct), None)
    st.write(f"Current stage: **{reached[-1]}**" + (f"  |  Next: **{nxt[1]}** at {nxt[0]}%" if nxt else "  |  Project complete"))
    st.caption("Estimates use illustrative per-sq-ft planning rates and a 35% land share. Replace with local quotes "
               "and a registered valuer's report before financial decisions.")

    st.markdown("#### Conceptual 3D architectural rendering")
    r1, r2 = st.columns([2, 1])
    style = r2.selectbox("Style", ["Modern minimalist", "Contemporary Indian", "Industrial", "Eco-friendly green building"])
    floors = r2.slider("Floors", 1, 10, 2)
    extra = r2.text_input("Extra details", placeholder="rooftop garden, glass facade")
    prompt = (f"photorealistic 3D architectural rendering of a {style.lower()} {structure.lower()} building, "
              f"{floors} floors, approx {int(sqft)} sq ft, {tier_name.split(' (')[0]} Indian city, {extra}, "
              f"golden hour lighting, high detail")
    if r2.button("Generate rendering", type="primary"):
        st.session_state["render_seed"] = int(datetime.now().timestamp()) % 100000
    seed = st.session_state.get("render_seed")
    with r1:
        if seed is None:
            st.info("Choose a style and generate a concept image.")
        else:
            st.image(pollinations_url(prompt, seed), caption="Concept render via Pollinations AI", use_container_width=True)
    with st.expander("Prompt used"):
        st.code(prompt)


def tab_assistant(cfg: AIConfig) -> None:
    st.subheader("Daily site assistant and weather-aware advisory")
    weather = st.radio("Today's site condition", list(WEATHER), horizontal=True, index=0)
    info = WEATHER[weather]
    for title, text in info["alerts"]:
        color = {"ok": "#3E9B5F", "warn": "#E8A317", "bad": "#D9531E"}[info["level"]]
        st.markdown(f'<div class="alert" style="border-left:6px solid {color}"><b>{info["icon"]} {title}</b><br>{text}</div>',
                    unsafe_allow_html=True)

    st.markdown("#### Ask SiteMate")
    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant",
                                  "content": "Hi, I'm SiteMate. Ask me about concrete mix, curing, reinforcement, scheduling or site safety."}]
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.pop("chat")
        st.rerun()

    if user_msg := st.chat_input("e.g. What cover should I give a 230 mm slab?"):
        st.session_state.chat.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            try:
                if cfg.live:
                    with st.spinner("Thinking..."):
                        reply = gemini_chat(cfg, CHAT_SYSTEM.format(weather=weather), st.session_state.chat)
                else:
                    hit = next((v for k, v in DEMO_CHAT.items() if k in user_msg.lower()), None)
                    reply = (hit or "Demonstration mode: add a Gemini API key in the sidebar for full answers. "
                             "Try asking about slump, curing, cover or steel.") 
                    reply += f"\n\n*Site condition noted: {weather}.*"
            except Exception as exc:  # noqa: BLE001
                reply = f"Sorry, the assistant hit an error ({type(exc).__name__}): {exc}"
            st.markdown(reply)
        st.session_state.chat.append({"role": "assistant", "content": reply})


# --------------------------------------------------------------------------- #
# Sidebar and main
# --------------------------------------------------------------------------- #
def sidebar() -> AIConfig:
    with st.sidebar:
        st.markdown("### 🏗️ Construction Intelligence")
        secret_key = ""
        try:
            secret_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:  # noqa: BLE001 - no secrets file locally
            pass
        key = st.text_input("Google Gemini API key", type="password", value="",
                            placeholder="Paste key or leave blank for demo",
                            help="Kept only in this session's memory. Get a key at aistudio.google.com.") or secret_key
        model = st.selectbox("Model", MODEL_OPTIONS, index=MODEL_OPTIONS.index(DEFAULT_MODEL))
        if key:
            st.success("Live mode: Gemini connected")
        else:
            st.warning("Demonstration mode: sample outputs")
        st.divider()
        st.markdown("**Features**")
        st.markdown("- Site safety and PPE audit\n- Crack diagnostics\n- Planning and valuation\n- Weather advisory and assistant")
        with st.expander("Architecture overview"):
            st.markdown(
                "**Streamlit UI** → tabs per module\n\n"
                "**Service layer** → Gemini multimodal calls returning strict JSON; chat with system prompt\n\n"
                "**Domain logic** → valuation model and weather rules in pure Python\n\n"
                "**State** → `st.session_state` only, no database\n\n"
                "**Fallback** → demo data if no key or on API error")
        st.caption("AI output is advisory. A qualified engineer must verify safety and structural decisions.")
    return AIConfig(api_key=key.strip() if key else "", model=model)


def main() -> None:
    cfg = sidebar()
    st.markdown(f'<div class="cip-hero"><h1>{APP_TITLE}</h1>'
                '<p>Audit site safety, diagnose cracks, plan budgets and get weather-aware guidance from one workspace.</p></div>',
                unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["Site safety and PPE", "Crack diagnostics", "Planning and valuation", "Daily site assistant"])
    with t1:
        analysis_tab(cfg, "safety", "Site safety and PPE audit", "Upload a construction site photo",
                     SAFETY_PROMPT, DEMO_SAFETY, render_safety, "safety_report")
    with t2:
        analysis_tab(cfg, "crack", "Crack diagnostics and structural integrity", "Upload a concrete or wall surface photo",
                     CRACK_PROMPT, DEMO_CRACK, render_crack, "crack_report")
    with t3:
        tab_planning()
    with t4:
        tab_assistant(cfg)


if __name__ == "__main__":
    main()
