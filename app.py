
import os, json, shutil
from pathlib import Path
import pandas as pd
import streamlit as st

try:
    from google import genai
except ImportError:
    genai = None

st.set_page_config(
    page_title="SortIQ — Smart File Organizer",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# Theme / CSS
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background:
        radial-gradient(circle at 10% 0%, rgba(99,102,241,.16), transparent 28%),
        radial-gradient(circle at 90% 10%, rgba(14,165,233,.10), transparent 25%),
        #070b14;
    color: #f8fafc;
}
.block-container {
    max-width: 1180px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
.hero {
    padding: 30px 34px;
    border: 1px solid rgba(148,163,184,.15);
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(17,24,39,.92), rgba(15,23,42,.78));
    box-shadow: 0 20px 60px rgba(0,0,0,.28);
    margin-bottom: 22px;
}
.brand {
    display:flex;
    align-items:center;
    gap:12px;
}
.logo {
    width:42px;height:42px;border-radius:13px;
    display:flex;align-items:center;justify-content:center;
    background: linear-gradient(135deg,#6366f1,#06b6d4);
    font-size:22px;font-weight:800;
    box-shadow:0 8px 30px rgba(99,102,241,.35);
}
.eyebrow {
    color:#94a3b8;
    font-size:12px;
    font-weight:700;
    letter-spacing:.12em;
    text-transform:uppercase;
}
h1 {
    font-size: 38px !important;
    line-height:1.1 !important;
    margin: 12px 0 8px !important;
    letter-spacing:-.04em;
}
.hero p {
    color:#94a3b8;
    font-size:15px;
    margin:0;
}
.section-title {
    font-size:20px;
    font-weight:750;
    margin:28px 0 12px;
}
.card {
    background:rgba(15,23,42,.76);
    border:1px solid rgba(148,163,184,.13);
    border-radius:18px;
    padding:20px;
    box-shadow:0 10px 35px rgba(0,0,0,.16);
}
.metric {
    background:rgba(15,23,42,.76);
    border:1px solid rgba(148,163,184,.13);
    border-radius:16px;
    padding:18px;
}
.metric-label {color:#94a3b8;font-size:12px;font-weight:600;}
.metric-value {font-size:25px;font-weight:800;margin-top:4px;}
.pill {
    display:inline-block;
    padding:5px 9px;
    border-radius:999px;
    background:rgba(99,102,241,.12);
    border:1px solid rgba(129,140,248,.18);
    color:#c7d2fe;
    font-size:11px;
    font-weight:700;
}
.ai-box {
    border:1px solid rgba(99,102,241,.28);
    background:linear-gradient(135deg,rgba(79,70,229,.12),rgba(6,182,212,.07));
    border-radius:18px;
    padding:18px 20px;
    margin:14px 0;
}
.ai-dot {
    display:inline-block;width:8px;height:8px;border-radius:50%;
    background:#22c55e;box-shadow:0 0 12px #22c55e;
    margin-right:7px;
}
.stButton > button {
    border-radius:12px !important;
    font-weight:700 !important;
    min-height:44px !important;
}
div[data-testid="stTextInput"] input {
    background:#0b1220 !important;
    border:1px solid rgba(148,163,184,.18) !important;
    border-radius:12px !important;
    color:#f8fafc !important;
}
div[data-testid="stDataFrame"] {
    border:1px solid rgba(148,163,184,.13);
    border-radius:14px;
}
footer {visibility:hidden;}
#MainMenu {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

CATEGORIES = [
    "Documents", "Images", "PDFs", "Presentations",
    "Spreadsheets", "Code", "Videos", "Audio", "Others"
]

EXTENSION_MAP = {
    "Images": {".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg"},
    "PDFs": {".pdf"},
    "Presentations": {".ppt",".pptx",".odp"},
    "Spreadsheets": {".xls",".xlsx",".csv",".ods"},
    "Code": {".py",".js",".java",".cpp",".c",".html",".css",".sql",".json"},
    "Videos": {".mp4",".mkv",".avi",".mov",".webm"},
    "Audio": {".mp3",".wav",".aac",".flac",".m4a"},
    "Documents": {".doc",".docx",".txt",".rtf",".md"}
}

def extension_category(path):
    ext = path.suffix.lower()
    for cat, exts in EXTENSION_MAP.items():
        if ext in exts:
            return cat
    return "Others"

def read_preview(path, max_chars=1500):
    try:
        if path.suffix.lower() in {".txt",".md",".py",".js",".java",".cpp",".c",".html",".css",".sql",".json",".csv"}:
            return path.read_text(errors="ignore")[:max_chars]
    except Exception:
        pass
    return ""

def classify_with_gemini(rows, api_key):
    if not genai or not api_key:
        return None
    client = genai.Client(api_key=api_key)
    payload = []
    for i, row in enumerate(rows):
        payload.append({
            "id": i,
            "filename": row["filename"],
            "extension": row["extension"],
            "preview": row["preview"]
        })
    prompt = f"""
You are SortIQ, an AI file organization assistant.
Classify every file into exactly one category:
{CATEGORIES}

Use filename, extension and preview. Return ONLY valid JSON:
[{{"id": 0, "category": "Documents", "reason": "brief reason"}}]
Do not invent categories.

Files:
{json.dumps(payload, ensure_ascii=False)}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)

def rule_classify(rows):
    results = []
    for i, row in enumerate(rows):
        cat = extension_category(Path(row["filename"]))
        results.append({
            "id": i,
            "category": cat,
            "reason": f"Detected from {row['extension'] or 'file type'}"
        })
    return results

# -----------------------------
# Header
# -----------------------------
st.markdown("""
<div class="hero">
    <div class="brand">
        <div class="logo">✦</div>
        <div>
            <div style="font-weight:800;font-size:18px;">SortIQ</div>
            <div class="eyebrow">AI File Intelligence</div>
        </div>
    </div>
    <h1>Turn digital clutter into order.</h1>
    <p>Analyze, intelligently classify, and organize your files — with a human approval step before anything moves.</p>
    <div style="margin-top:16px;">
        <span class="pill">AI-POWERED</span>
        &nbsp;
        <span class="pill">SAFE BY DESIGN</span>
        &nbsp;
        <span class="pill">REVERSIBLE</span>
    </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ✦ SortIQ Settings")
    api_key = st.text_input("Gemini API Key (optional)", type="password")
    st.caption("If no key is supplied, the app automatically uses its local fallback classifier.")
    st.divider()
    st.caption("SortIQ MVP • Mini Project Demo")

# -----------------------------
# Folder selection
# -----------------------------
st.markdown('<div class="section-title">01 · Choose workspace</div>', unsafe_allow_html=True)

folder = st.text_input(
    "Folder path",
    value=str(Path.home() / "Downloads"),
    label_visibility="collapsed",
)

c1, c2 = st.columns([3,1])
with c1:
    st.markdown(
        '<div class="card"><span style="color:#94a3b8;">Workspace</span><br>'
        '<strong style="font-size:16px;">📂 ' + folder + '</strong></div>',
        unsafe_allow_html=True
    )
with c2:
    analyze = st.button("🔍 Analyze with AI", use_container_width=True, type="primary")

if "plan" not in st.session_state:
    st.session_state.plan = None
if "history" not in st.session_state:
    st.session_state.history = []

# -----------------------------
# Analyze
# -----------------------------
if analyze:
    base = Path(folder)
    if not base.exists() or not base.is_dir():
        st.error("Please enter a valid folder path.")
        st.stop()

    paths = [p for p in base.iterdir() if p.is_file()]
    if not paths:
        st.warning("No files found in this folder.")
        st.stop()

    rows = []
    for p in paths:
        rows.append({
            "filename": p.name,
            "extension": p.suffix.lower(),
            "size_kb": round(p.stat().st_size / 1024, 2),
            "preview": read_preview(p)
        })

    with st.spinner("SortIQ is analyzing your workspace..."):
        try:
            results = classify_with_gemini(rows, api_key) if api_key else None
        except Exception:
            results = None

        if not results:
            results = rule_classify(rows)

    for row, result in zip(rows, results):
        category = result.get("category", "Others")
        if category not in CATEGORIES:
            category = "Others"
        row["category"] = category
        row["reason"] = result.get("reason", "Classified by SortIQ")
        row.pop("preview", None)

    st.session_state.plan = pd.DataFrame(rows)

# -----------------------------
# Results
# -----------------------------
if st.session_state.plan is not None:
    df = st.session_state.plan.copy()

    st.markdown('<div class="section-title">02 · Intelligence report</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="ai-box">
        <span class="ai-dot"></span>
        <strong>SortIQ analysis complete</strong>
        <span style="color:#94a3b8;"> — review the proposed organization before applying changes.</span>
    </div>
    """, unsafe_allow_html=True)

    total_mb = df["size_kb"].sum() / 1024

    cols = st.columns(4)
    metrics = [
        ("FILES SCANNED", str(len(df))),
        ("CATEGORIES", str(df["category"].nunique())),
        ("TOTAL SIZE", f"{total_mb:.1f} MB"),
        ("AI DECISIONS", str(len(df))),
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{value}</div></div>',
                unsafe_allow_html=True
            )

    left, right = st.columns([1.25, 1])
    with left:
        st.markdown('<div class="section-title">Classification overview</div>', unsafe_allow_html=True)
        counts = df["category"].value_counts().rename_axis("Category").reset_index(name="Files")
        st.bar_chart(counts.set_index("Category"))
    with right:
        st.markdown('<div class="section-title">Proposed folders</div>', unsafe_allow_html=True)
        for _, r in counts.iterrows():
            st.markdown(
                f'<div style="padding:9px 0;border-bottom:1px solid rgba(148,163,184,.09);">'
                f'<strong>{r["Category"]}</strong>'
                f'<span style="float:right;color:#94a3b8;">{r["Files"]} files</span></div>',
                unsafe_allow_html=True
            )

    st.markdown('<div class="section-title">File-level AI decisions</div>', unsafe_allow_html=True)

    display_df = df[["filename","category","size_kb","reason"]].copy()
    display_df.columns = ["File", "AI Category", "Size (KB)", "Reason"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">03 · Apply organization</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="card"><strong>Human approval required</strong><br>'
        '<span style="color:#94a3b8;">Nothing has been moved yet. Click below to create the '
        '<code>Organized/</code> structure and move the selected files.</span></div>',
        unsafe_allow_html=True
    )

    a, b = st.columns([3,1])
    with a:
        organize = st.button("✨ Organize Files", use_container_width=True, type="primary")
    with b:
        clear = st.button("Clear Analysis", use_container_width=True)
        if clear:
            st.session_state.plan = None
            st.rerun()

    if organize:
        base = Path(folder)
        moved = []
        errors = []

        for _, row in df.iterrows():
            src = base / row["filename"]
            dest_dir = base / "Organized" / row["category"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name

            if not src.exists():
                errors.append(f"{src.name}: source no longer exists")
                continue

            if dest.exists():
                stem, suffix = dest.stem, dest.suffix
                n = 1
                while (dest_dir / f"{stem}_{n}{suffix}").exists():
                    n += 1
                dest = dest_dir / f"{stem}_{n}{suffix}"

            try:
                shutil.move(str(src), str(dest))
                moved.append((str(dest), str(src)))
            except Exception as e:
                errors.append(f"{src.name}: {e}")
        st.session_state.history = moved
        st.session_state.history = moved
        st.session_state.plan = None
        st.success(f"Organization complete — {len(moved)} files moved.")

        if errors:
            st.warning("\n".join(errors))

# -----------------------------
# Undo
# -----------------------------
if st.session_state.history:
    st.markdown('<div class="section-title">Recovery</div>', unsafe_allow_html=True)
    if st.button("↩️ Undo Last Organization", use_container_width=True):
        restored = 0
        cleanup_errors = []
        history = st.session_state.history
        for dest, original in reversed(history):
            try:
                Path(original).parent.mkdir(parents=True, exist_ok=True)
                if Path(dest).exists():
                    shutil.move(dest, original)
                    restored += 1
            except Exception:
                pass
        organized_roots = {Path(dest).parent.parent for dest, _ in history}
        for root in organized_roots:
            if root.name != "Organized" or not root.is_dir():
                continue
            for current, _, _ in os.walk(root, topdown=False):
                path = Path(current)
                try:
                    if not any(path.iterdir()):
                        path.rmdir()
                except OSError as e:
                    cleanup_errors.append(f"{path}: {e}")
        st.session_state.history = []
        st.success(f"Restored {restored} files to their original locations.")
        if cleanup_errors:
            st.warning("Could not remove some empty folders:\n" + "\n".join(cleanup_errors))
