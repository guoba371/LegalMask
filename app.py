"""LegalMask — 律师文件脱敏助手"""

import io
import json
import os
import tempfile
import zipfile

import streamlit as st

from core.processor import (
    ProcessResult,
    batch_process,
    load_mapping,
    process_document,
    restore_text,
)

# ─── 页面配置（必须第一个 st 调用）───────────────────────────────────────────
st.set_page_config(
    page_title="LegalMask — 律师文件脱敏助手",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── 全局样式 ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC',
                 'Hiragino Sans GB', sans-serif !important;
}
.stApp { background: #eef2f7; }
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 0 !important;
    padding-bottom: 40px !important;
    max-width: 860px !important;
}

/* ── Hero Banner ── */
.hero {
    background: linear-gradient(140deg, #0b1f3a 0%, #163d6e 55%, #0d3060 100%);
    border-radius: 20px;
    padding: 52px 40px 44px;
    margin-bottom: 28px;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(11,31,58,0.35);
}
.hero::before {
    content: '';
    position: absolute; inset: 0;
    background-image: radial-gradient(circle, rgba(255,255,255,0.07) 1px, transparent 1px);
    background-size: 28px 28px;
    pointer-events: none;
}
.hero-logo {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 72px; height: 72px;
    background: rgba(255,255,255,0.1);
    border: 2px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    margin-bottom: 18px;
    font-size: 36px;
}
.hero-title {
    font-size: 42px;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 6px 0;
    letter-spacing: -1px;
}
.hero-title span { color: #60a5fa; }
.hero-sub {
    font-size: 15px;
    color: rgba(255,255,255,0.65);
    margin: 0 0 30px 0;
    line-height: 1.6;
}
.hero-badges {
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
}
.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 14px;
    border-radius: 100px;
    font-size: 12.5px;
    font-weight: 500;
    letter-spacing: 0.1px;
}
.badge-blue  { background:rgba(96,165,250,0.18); border:1px solid rgba(96,165,250,0.35); color:#93c5fd; }
.badge-gold  { background:rgba(251,191,36,0.15); border:1px solid rgba(251,191,36,0.3);  color:#fcd34d; }
.badge-green { background:rgba(52,211,153,0.15); border:1px solid rgba(52,211,153,0.3);  color:#6ee7b7; }
.badge-gray  { background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.18);color:rgba(255,255,255,0.7); }
.hero-notice {
    margin-top: 22px;
    font-size: 11.5px;
    color: rgba(255,255,255,0.35);
}

/* ── Card ── */
.card {
    background: white;
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: white !important;
    border-radius: 12px !important;
    padding: 5px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
    gap: 2px !important;
    margin-bottom: 20px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 10px 22px !important;
    color: #64748b !important;
    transition: all 0.2s !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #0b1f3a !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(11,31,58,0.3) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #0b1f3a !important;
    color: white !important;
    border: none !important;
    border-radius: 9px !important;
    font-size: 14.5px !important;
    font-weight: 600 !important;
    padding: 11px 26px !important;
    letter-spacing: 0.2px !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(11,31,58,0.28) !important;
}
.stButton > button:hover {
    background: #163d6e !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(11,31,58,0.4) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* download buttons get a softer look */
[data-testid="stDownloadButton"] > button {
    background: #f1f5f9 !important;
    color: #0b1f3a !important;
    box-shadow: none !important;
    border: 1px solid #e2e8f0 !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #e2e8f0 !important;
    transform: none !important;
    box-shadow: none !important;
}
[data-testid="stDownloadButton"][data-testid*="zip"] > button,
[data-testid="stDownloadButton"].primary > button {
    background: #0b1f3a !important;
    color: white !important;
}

/* ── File Uploader ── */
[data-testid="stFileUploader"] {
    background: #f8fafc !important;
    border: 2px dashed #c8d6e5 !important;
    border-radius: 12px !important;
    transition: border-color 0.2s !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #0b1f3a !important;
}
[data-testid="stFileUploaderDropzoneInput"] { cursor: pointer !important; }

/* ── Progress ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0b1f3a 0%, #3b82f6 100%) !important;
    border-radius: 6px !important;
}

/* ── Alerts ── */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: 10px !important;
    font-size: 14px !important;
}

/* ── Headings ── */
h2, h3 { color: #0b1f3a !important; font-weight: 600 !important; }
h4 { color: #1e293b !important; font-weight: 600 !important; font-size: 14px !important;
     text-transform: uppercase; letter-spacing: 0.5px; margin-top: 20px !important; }

/* ── Divider ── */
hr { border-color: #e2e8f0 !important; margin: 20px 0 !important; }

/* ── Dataframe ── */
.stDataFrame { border-radius: 10px !important; overflow: hidden !important; font-size: 13px !important; }

/* ── Radio ── */
.stRadio > div { gap: 12px !important; }
.stRadio > div > label { font-size: 14px !important; }

/* ── Text area ── */
.stTextArea > div > div > textarea {
    border-radius: 10px !important;
    border: 1.5px solid #e2e8f0 !important;
    font-size: 14px !important;
    font-family: 'Inter', monospace !important;
}
.stTextArea > div > div > textarea:focus {
    border-color: #0b1f3a !important;
    box-shadow: 0 0 0 3px rgba(11,31,58,0.1) !important;
}

/* ── Instruction step cards ── */
.step-card {
    display: flex;
    gap: 16px;
    padding: 16px 20px;
    background: #f8fafc;
    border-radius: 12px;
    border-left: 4px solid #0b1f3a;
    margin-bottom: 12px;
    align-items: flex-start;
}
.step-num {
    width: 28px; height: 28px;
    background: #0b1f3a;
    color: white;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
    flex-shrink: 0;
    margin-top: 2px;
}
.step-content h5 { margin: 0 0 4px 0; font-size: 14px; font-weight: 600; color: #0b1f3a; }
.step-content p  { margin: 0; font-size: 13px; color: #64748b; line-height: 1.5; }

/* ── Feature chips on instructions tab ── */
.feature-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin: 16px 0;
}
.feature-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: white;
    border-radius: 10px;
    border: 1px solid #e8edf3;
    font-size: 13px;
    color: #334155;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# ─── Hero Banner ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-logo">🛡️</div>
  <h1 class="hero-title">Legal<span>Mask</span></h1>
  <p class="hero-sub">律师文件智能脱敏工具<br>安全使用 AI 分析法律文件，数据始终在您手中</p>
  <div class="hero-badges">
    <span class="badge badge-blue">🔒 完全本地运行</span>
    <span class="badge badge-gold">⚖️ 法条自动保护</span>
    <span class="badge badge-green">🔄 支持反向还原</span>
    <span class="badge badge-gray">📄 Word &amp; PDF</span>
    <span class="badge badge-gray">批量处理</span>
  </div>
  <p class="hero-notice">⚠️ 扫描版 PDF 暂不支持，需含文字层的 PDF</p>
</div>
""", unsafe_allow_html=True)

# ─── Session State ────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state["results"] = []
if "restored_text" not in st.session_state:
    st.session_state["restored_text"] = ""

# ─── 工具函数 ─────────────────────────────────────────────────────────────────
def save_uploaded_files(uploaded_files):
    tmp_dir = tempfile.mkdtemp(prefix="legalmask_")
    paths = []
    for uf in uploaded_files:
        dest = os.path.join(tmp_dir, uf.name)
        with open(dest, "wb") as f:
            f.write(uf.getbuffer())
        paths.append(dest)
    return tmp_dir, paths


def build_zip(results: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            if not r.success:
                continue
            if r.output_file and os.path.exists(r.output_file):
                zf.write(r.output_file, arcname=os.path.basename(r.output_file))
            if r.mapping_file and os.path.exists(r.mapping_file):
                zf.write(r.mapping_file, arcname=os.path.basename(r.mapping_file))
    buf.seek(0)
    return buf.read()


def read_file_bytes(path: str) -> bytes:
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return b""


# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📄  批量脱敏", "🔄  还原分析", "ℹ️  使用说明"])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — 批量脱敏
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 上传文件")

    uploaded_files = st.file_uploader(
        "拖放或点击选择文件（支持 .docx / .pdf）",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        key="uploader_tab1",
        label_visibility="collapsed",
    )

    if uploaded_files:
        names = "、".join(f"`{f.name}`" for f in uploaded_files[:3])
        suffix = f" 等 **{len(uploaded_files)}** 个文件" if len(uploaded_files) > 3 else f" 共 **{len(uploaded_files)}** 个文件"
        st.info(f"已选择：{names}{suffix}")

    col_btn, _ = st.columns([2, 5])
    with col_btn:
        start_btn = st.button("🔒  开始脱敏", type="primary", key="start_btn")
    st.markdown("</div>", unsafe_allow_html=True)

    if start_btn:
        if not uploaded_files:
            st.warning("请先上传至少一个文件。")
        else:
            _, file_paths = save_uploaded_files(uploaded_files)
            output_dir = tempfile.mkdtemp(prefix="legalmask_out_")

            progress_bar = st.progress(0, text="准备中…")
            status_ph = st.empty()
            results: list = []
            total = len(file_paths)

            for i, fpath in enumerate(file_paths):
                fname = os.path.basename(fpath)
                status_ph.markdown(f"**正在处理：** `{fname}`")
                try:
                    result = process_document(fpath, output_dir)
                except Exception as exc:
                    result = ProcessResult(
                        success=False, input_file=fname,
                        error=str(exc), entity_count=0,
                    )
                results.append(result)
                progress_bar.progress((i + 1) / total, text=f"已处理 {i + 1} / {total}")

            st.session_state["results"] = results
            progress_bar.empty()
            status_ph.empty()

            ok = sum(1 for r in results if r.success)
            fail = total - ok
            if fail == 0:
                st.success(f"✅ 全部完成！{ok} 个文件脱敏成功。")
            else:
                st.warning(f"完成：{ok} 成功，{fail} 失败。")

    # 结果区
    results: list = st.session_state.get("results", [])
    if results:
        st.markdown("#### 处理结果")

        table_rows = [
            {
                "文件名": os.path.basename(r.input_file),
                "状态": "✅ 成功" if r.success else "❌ 失败",
                "脱敏实体数": r.entity_count if r.success else "—",
                "备注": r.error or "",
            }
            for r in results
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        st.markdown("#### 下载")
        for r in results:
            if not r.success:
                st.error(f"**{os.path.basename(r.input_file)}** 失败：{r.error}")
                continue
            c1, c2, c3 = st.columns([4, 2, 2])
            c1.markdown(f"`{os.path.basename(r.input_file)}`")
            if r.output_file:
                c2.download_button(
                    "⬇ 脱敏版", data=read_file_bytes(r.output_file),
                    file_name=os.path.basename(r.output_file),
                    mime="application/octet-stream",
                    key=f"dl_doc_{r.input_file}",
                )
            if r.mapping_file:
                c3.download_button(
                    "⬇ Mapping", data=read_file_bytes(r.mapping_file),
                    file_name=os.path.basename(r.mapping_file),
                    mime="application/json",
                    key=f"dl_map_{r.input_file}",
                )

        st.markdown("---")
        successful = [r for r in results if r.success]
        if successful:
            st.download_button(
                label="📦  打包下载全部（脱敏文件 + Mapping）",
                data=build_zip(successful),
                file_name="legalmask_output.zip",
                mime="application/zip",
                type="primary",
                key="dl_zip_all",
                use_container_width=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — 还原分析
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 第一步 — 加载 Mapping 文件")

    mapping_source = st.radio(
        "来源",
        ["上传 mapping.json 文件", "粘贴 JSON 文本"],
        horizontal=True,
        key="mapping_source",
        label_visibility="collapsed",
    )

    mapping_dict: dict = {}

    if mapping_source == "上传 mapping.json 文件":
        mf = st.file_uploader("上传 mapping.json", type=["json"],
                               key="mapping_uploader", label_visibility="collapsed")
        if mf:
            tmp_p = os.path.join(tempfile.mkdtemp(), mf.name)
            with open(tmp_p, "wb") as f:
                f.write(mf.getbuffer())
            try:
                mapping_dict = load_mapping(tmp_p)
                st.success(f"加载成功 — 共 {len(mapping_dict)} 条映射")
            except Exception as exc:
                st.error(f"解析失败：{exc}")
    else:
        mt = st.text_area(
            "粘贴 JSON",
            placeholder='{"{{PARTY_甲方}}": "王某某", "{{CASE_NUMBER_1}}": "（2024）京0105民初12345号"}',
            height=110,
            key="mapping_text_input",
            label_visibility="collapsed",
        )
        if mt.strip():
            try:
                mapping_dict = json.loads(mt.strip())
                st.success(f"解析成功 — 共 {len(mapping_dict)} 条映射")
            except json.JSONDecodeError as exc:
                st.error(f"JSON 格式错误：{exc}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 第二步 — 粘贴 AI 分析文本")
    ai_text = st.text_area(
        "AI 分析内容（含甲方、乙方等占位符）",
        placeholder="将 AI 返回的分析报告粘贴到此处…",
        height=180,
        key="ai_text_input",
        label_visibility="collapsed",
    )

    c_btn, _ = st.columns([2, 5])
    with c_btn:
        restore_btn = st.button("🔄  立即还原", type="primary", key="restore_btn")
    st.markdown("</div>", unsafe_allow_html=True)

    if restore_btn:
        if not mapping_dict:
            st.warning("请先加载 Mapping 文件。")
        elif not ai_text.strip():
            st.warning("请先粘贴 AI 分析文本。")
        else:
            try:
                st.session_state["restored_text"] = restore_text(ai_text, mapping_dict)
            except Exception as exc:
                st.error(f"还原失败：{exc}")
                st.session_state["restored_text"] = ""

    if st.session_state.get("restored_text"):
        rt = st.session_state["restored_text"]
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 还原结果")
        st.text_area("", value=rt, height=180, key="restored_output", disabled=True,
                     label_visibility="collapsed")
        c_copy, c_dl, _ = st.columns([2, 2, 3])
        c_copy.markdown(
            f"""<button onclick="navigator.clipboard.writeText({json.dumps(rt)}).then(()=>{{
                this.textContent='✅ 已复制';setTimeout(()=>this.textContent='📋  复制文本',1800)
            }})" style="width:100%;background:#f1f5f9;color:#0b1f3a;border:1px solid #e2e8f0;
            padding:8px 0;border-radius:9px;font-size:13px;font-weight:600;cursor:pointer;
            font-family:inherit;">📋  复制文本</button>""",
            unsafe_allow_html=True,
        )
        c_dl.download_button(
            "⬇ 下载 TXT", data=rt.encode("utf-8"),
            file_name="restored_result.txt", mime="text/plain",
            key="dl_restored_txt",
        )
        st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — 使用说明
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("""
<div class="card">
<h3 style="margin-top:0;font-size:18px;">三步完成安全 AI 法律分析</h3>

<div class="step-card">
  <div class="step-num">1</div>
  <div class="step-content">
    <h5>上传并脱敏</h5>
    <p>在「批量脱敏」页上传含真实姓名、案号、公司名的 Word 或 PDF 文件，点击「开始脱敏」。<br>
    系统将姓名替换为甲方/乙方/丙方…，生成脱敏文件和 Mapping 文件。</p>
  </div>
</div>

<div class="step-card">
  <div class="step-num">2</div>
  <div class="step-content">
    <h5>提交 AI 分析</h5>
    <p>下载脱敏文件，将内容粘贴到任意 AI（ChatGPT、Claude、Kimi 等）进行分析，获取分析报告。<br>
    因已脱敏，当事人隐私不会被 AI 服务器留存。</p>
  </div>
</div>

<div class="step-card">
  <div class="step-num">3</div>
  <div class="step-content">
    <h5>还原真实信息</h5>
    <p>在「还原分析」页加载 Mapping 文件，粘贴 AI 报告，点击「立即还原」，<br>
    即可得到含真实姓名的完整分析结论。</p>
  </div>
</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="feature-grid">
  <div class="feature-item">🔒 <span>完全本地运行，文件不出本机</span></div>
  <div class="feature-item">⚖️ <span>第X条法条引用自动保护</span></div>
  <div class="feature-item">🔄 <span>脱敏可逆，支持信息还原</span></div>
  <div class="feature-item">📄 <span>Word、PDF（含文字层）</span></div>
  <div class="feature-item">👥 <span>甲/乙/丙方跨文档一致</span></div>
  <div class="feature-item">📦 <span>批量处理，一键打包下载</span></div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="card" style="background:#fefce8;border:1px solid #fde68a;">
<strong>⚠️ 已知限制</strong><br>
<span style="font-size:13px;color:#78350f;">扫描版 PDF（图片型）暂不支持，需含可选中文字层的 PDF。<br>
建议处理后人工核查脱敏结果，确认无遗漏实体。</span>
</div>
""", unsafe_allow_html=True)
