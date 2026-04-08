"""
PQ 평가서 웹 기반 작성 도구 (QBS Auto Draft Tool)
=================================================
Streamlit 기반 단계별 QBS 초안 작성 지원 도구
진입점: pq_tool/SRC/app.py
"""

import streamlit as st
import pdfplumber
import re
import json
import io
import pandas as pd
from datetime import datetime

# PyMuPDF (이미지 추출용) — 없으면 이미지 기능 비활성화
try:
    import fitz
    from PIL import Image
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

# ============================
# 페이지 기본 설정
# ============================
st.set_page_config(
    page_title="QBS 작성 도구",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================
# 1. PDF 파싱 함수
# ============================

def extract_text_from_pdf(uploaded_file):
    """업로드된 PDF에서 전체 텍스트 추출"""
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
        return all_text
    except Exception as e:
        st.error(f"PDF 읽기 실패: {e}")
        return ""


def extract_pages_from_pdf(uploaded_file):
    """업로드된 PDF에서 페이지별 텍스트 추출"""
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                pages.append(text if text else "")
        return pages
    except Exception as e:
        st.error(f"PDF 페이지 읽기 실패: {e}")
        return []


def extract_images_from_pdf(uploaded_file):
    """PDF에서 이미지 추출 (PyMuPDF 필요)"""
    if not HAS_FITZ:
        return []
    
    images = []
    try:
        uploaded_file.seek(0)
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page_idx, page in enumerate(doc):
            for img_idx, img in enumerate(page.get_images()):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_data = Image.open(io.BytesIO(pix.tobytes()))
                # 너무 작은 이미지 제외 (아이콘 등)
                if img_data.width > 50 and img_data.height > 50:
                    images.append({
                        "page": page_idx + 1,
                        "img": img_data,
                        "size": f"{img_data.width}x{img_data.height}"
                    })
        doc.close()
    except Exception as e:
        st.warning(f"이미지 추출 실패: {e}")
    return images


def parse_task_pdf(text):
    """과업지시서에서 핵심 정보 추출 (검증 완료된 로직)"""
    info = {}
    
    # 사업명: "본 과업의 명칭은 "ㅇㅇㅇ"" 패턴
    match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', text)
    if match:
        info["사업명"] = match.group(1).strip()
    else:
        # fallback: 사업명|용역명 패턴
        match2 = re.search(r'(?:사업명|용역명)[:\s]+([^\n]+)', text)
        info["사업명"] = match2.group(1).strip() if match2 else ""
    
    # 지자체명
    match = re.search(r'([가-힣]{1,4}(?:시|군))\s*전체\s*행정구역', text)
    if match:
        info["지자체명"] = match.group(1).strip()
    else:
        name = info.get("사업명", "")
        m2 = re.match(r'([가-힣]{1,4}(?:시|군))\s', name)
        info["지자체명"] = m2.group(1).strip() if m2 else ""
    
    # 과업기간
    match = re.search(r'과업기간은?\s*착수일로부터\s*(\d+)\s*개월', text)
    info["과업기간"] = f"착수일로부터 {match.group(1)}개월" if match else ""
    
    # 목표연도
    match = re.search(r'목표연도\s*[:：]?\s*(\d{4})\s*년', text)
    info["목표연도"] = f"{match.group(1)}년" if match else ""
    
    # 수행지침
    match = re.search(r'수도정비기본계획\s*수립지침\s*\(.*?\)', text)
    info["수행지침"] = match.group(0).strip() if match else ""
    
    # 과업목적
    purpose_match = re.search(
        r'(?:2|II)\s*[.\s]*\s*과업의\s*목적\s*\n(.*?)(?:3|III)\s*[.\s]*\s*과업의\s*개요',
        text, re.DOTALL
    )
    if purpose_match:
        p = purpose_match.group(1).strip()
        p = re.sub(r'[◦○●■◆▶]', '', p)
        info["과업목적"] = '\n'.join([l.strip() for l in p.split('\n') if l.strip()])
    else:
        info["과업목적"] = ""
    
    # 과업범위
    scope = []
    scope_matches = re.findall(r'[<＜]\s*제\s*(\d+)\s*편\s*(.*?)\s*[>＞]', text)
    seen = set()
    for num, name in scope_matches:
        key = f"제{num}편"
        if key not in seen and name.strip():
            scope.append(f"{key} {name.strip()}")
            seen.add(key)
    # fallback: 제N편 패턴
    if not scope:
        scope = re.findall(r'제\d+편\s+[^\n]+', text)
    info["과업범위"] = scope
    
    return info


def parse_eval_pdf(text, city=""):
    """평가기준서에서 발주처명, 분야 추출"""
    info = {}
    
    if city:
        client_match = re.search(
            r'(' + re.escape(city) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))', text
        )
        info["발주처"] = client_match.group(1).strip() if client_match else f"{city} (수동입력 필요)"
    else:
        info["발주처"] = "(지자체명 미감지 — 수동입력 필요)"
    
    fields = []
    for pattern in [r'상하수도', r'구조', r'토질\s*[·‧]\s*지질', r'수자원개발',
                    r'환경\s*[\(（]\s*수질\s*[\)）]', r'기계', r'전기']:
        match = re.search(pattern, text)
        if match:
            fields.append(match.group(0).strip())
    if not any('환경' in f for f in fields):
        if re.search(r'환경.*수질|수질.*환경', text):
            fields.append('환경(수질)')
    info["분야"] = fields
    
    return info


# ============================
# 2. QBS 섹션 분리
# ============================

SECTION_DEFS = [
    ("1.1", ["당해 사업의 내용", "당해사업의 내용", "당해 사업",
             "당해 용역의 내용", "당해용역의 내용", "당해 용역"]),
    ("1.2", ["유사사업 수행실적", "유사용역 수행실적", "유사사업", "유사용역"]),
    ("1.3", ["사업 성공을 위한", "사업성공을 위한", "성공을 위한",
             "용역 성공을 위한", "용역성공을 위한"]),
    ("2.1", ["업무 수행범위", "업무수행범위", "업무 수행 범위", "기본방침"]),
    ("2.2", ["작업계획서", "작업 계획서"]),
    ("2.3", ["품질보증", "품질 보증", "품질관리", "품질 관리"]),
    ("2.4", ["전문가 활용", "전문가활용"]),
]

SECTION_TITLES = {
    "1.1": "당해 사업의 내용 및 이해도",
    "1.2": "당해 사업 관련 유사사업 제시",
    "1.3": "사업 성공을 위한 요건 및 추가 제안사항",
    "2.1": "당해 사업 관련 업무 수행범위",
    "2.2": "작업계획서",
    "2.3": "품질보증체계 및 품질관리계획",
    "2.4": "전문가 활용계획 등 추가 업무관리사항",
}


def _detect_section_from_page(text, top_n_chars=400):
    header = text[:top_n_chars]
    header_clean = re.sub(r'\s+', ' ', header).strip()
    header_nospace = re.sub(r'\s+', '', header_clean)
    for sec_num, keywords in SECTION_DEFS:
        num_escaped = re.escape(sec_num)
        if not re.search(rf'(?:^|\s|\.|\(|\)|:|;|,){num_escaped}(?:\s|\.|\(|:|,|[가-힣])', header_clean):
            continue
        for kw in keywords:
            if re.sub(r'\s+', '', kw) in header_nospace:
                return sec_num
    return None


def _is_toc_page(text):
    text_clean = re.sub(r'\s+', ' ', text[:500]).strip()
    if re.search(r'목\s*차', text_clean):
        if len(re.findall(r'[12]\.[1-4]', text_clean)) >= 3:
            return True
    return False


def extract_qbs_sections(pages_text):
    page_info = []
    for i, text in enumerate(pages_text):
        if _is_toc_page(text):
            page_info.append((i, text, "__SKIP__"))
        else:
            page_info.append((i, text, _detect_section_from_page(text)))
    
    sections = {}
    current_section = None
    current_texts = []
    for i, text, detected in page_info:
        if detected == "__SKIP__":
            continue
        if detected is not None:
            if current_section:
                sections[current_section] = "\n".join(current_texts)
            current_section = detected
            current_texts = [text]
        elif current_section:
            current_texts.append(text)
    if current_section:
        sections[current_section] = "\n".join(current_texts)
    
    for sec_num, _ in SECTION_DEFS:
        if sec_num not in sections:
            sections[sec_num] = ""
    return sections


# ============================
# 3. QBS Identity + 치환
# ============================

PROVINCE_LIST = [
    '전북특별자치도', '전라남도', '전라북도', '경상남도', '경상북도',
    '충청남도', '충청북도', '강원특별자치도', '강원도', '경기도',
    '제주특별자치도', '세종특별자치시'
]
PROVINCE_SHORT = {
    '전남': '전라남도', '전북': '전라북도', '경남': '경상남도',
    '경북': '경상북도', '충남': '충청남도', '충북': '충청북도',
}


def extract_qbs_identity(pages_text):
    result = {"city": None, "province": None, "client": None}
    body = "\n".join(pages_text[1:])[:3000] if len(pages_text) > 1 else pages_text[0][:3000]
    full = "\n".join(pages_text)
    
    m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도정비', body)
    if not m:
        m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도', body)
    if m:
        result["city"] = m.group(1)
    
    for prov in PROVINCE_LIST:
        if prov in full[:5000]:
            result["province"] = prov
            break
    if not result["province"]:
        for short, full_name in PROVINCE_SHORT.items():
            if re.search(re.escape(short) + r'[\s·,]', full[:5000]):
                result["province"] = full_name
                break
    
    later = "\n".join(pages_text[max(0, len(pages_text)-4):])
    if result["city"]:
        cm = re.search(r'(' + re.escape(result["city"]) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))', later)
        if cm:
            result["client"] = cm.group(1).strip()
    
    return result


def build_replacer(task_info, qbs_identity):
    tc = task_info.get("지자체명", "")
    tp = task_info.get("도명", "")
    tcl = task_info.get("발주처", "")
    sc = qbs_identity.get("city") or ""
    sp = qbs_identity.get("province") or ""
    scl = qbs_identity.get("client") or ""
    
    def do_replace(text):
        r = text
        if scl and tcl:
            r = r.replace(scl, tcl)
        if sc:
            r = re.sub(re.escape(sc) + r'청', tc, r)
        if sc and tc and sc != tc:
            r = r.replace(sc, tc)
        if sp and tp and sp != tp:
            r = r.replace(sp, tp)
        for short, full in PROVINCE_SHORT.items():
            if full == sp and tp:
                r = re.sub(r'(?<![가-힣])' + re.escape(short) + r'(?![가-힣])', tp, r)
        return r
    return do_replace


# ============================
# 4. 정합성 체크 엔진
# ============================

def check_consistency(text, task_info):
    """작성 내용의 정합성을 실시간 체크"""
    issues = []
    
    # 1. 용어 체크
    wrong_terms = {
        "사업책임기술자": "사업책임기술인",
        "책임기술자": "책임기술인",
    }
    for wrong, correct in wrong_terms.items():
        count = text.count(wrong)
        if count > 0:
            issues.append(("error", f"용어 수정 필요: '{wrong}' → '{correct}' ({count}건)"))
    
    # 2. 과업범위 반영 체크
    scopes = task_info.get("과업범위", [])
    for scope in scopes:
        core = re.sub(r'제\d+편\s*', '', scope).strip()
        if len(core) >= 2 and core[:2] not in text:
            issues.append(("info", f"과업범위 '{core}' 미반영 (참고)"))
    
    # 3. 필수 키워드 체크 (섹션별로 다르게 할 수 있음)
    if "발주처" in text or "감독관" in text:
        pass  # 정상
    
    return issues


# ============================
# 5. 상태 초기화
# ============================

def init_session_state():
    defaults = {
        "current_step": 0,
        "task_info": {"과업범위": []},
        "eval_info": {},
        "qbs_list": [],
        "main_qbs_idx": 0,
        "extracted_images": [],
        # 각 STEP 입력 결과
        "step1_data": {}, "step2_data": {}, "step3_data": {},
        "step4_data": {}, "step5_data": {}, "step6_data": {}, "step7_data": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================
# 6. UI 렌더링
# ============================

def render_sidebar():
    steps = [
        "📁 파일 업로드", "1.1 사업의 내용", "1.2 유사사업", "1.3 성공요건",
        "2.1 수행범위", "2.2 작업계획서", "2.3 품질관리", "2.4 전문가 활용", "📥 다운로드",
    ]
    st.sidebar.title("📋 QBS 작성 도구")
    st.sidebar.markdown("---")
    for i, name in enumerate(steps):
        if i == st.session_state.current_step:
            st.sidebar.markdown(f"**▶ {name}**")
        elif i < st.session_state.current_step:
            st.sidebar.markdown(f"✅ {name}")
        else:
            st.sidebar.markdown(f"⬜ {name}")
    st.sidebar.markdown("---")
    
    # 단계 점프 (디버깅/편의용)
    jump = st.sidebar.selectbox("단계 이동", range(len(steps)),
                                 format_func=lambda x: steps[x],
                                 index=st.session_state.current_step,
                                 key="sidebar_jump")
    if jump != st.session_state.current_step:
        st.session_state.current_step = jump
        st.rerun()


def render_step0():
    """STEP 0: 파일 업로드"""
    st.header("📁 파일 업로드 및 기본 정보 확인")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📂 파일 업로드")
        task_file = st.file_uploader("과업지시서 PDF", type="pdf", key="task_pdf")
        eval_file = st.file_uploader("평가기준서 PDF", type="pdf", key="eval_pdf")
        qbs_files = st.file_uploader("참고QBS PDF (여러 개)", type="pdf",
                                      accept_multiple_files=True, key="qbs_pdfs")
    
    with col2:
        st.subheader("📊 파싱 결과")
        
        if task_file:
            task_text = extract_text_from_pdf(task_file)
            if task_text:
                info = parse_task_pdf(task_text)
                st.session_state.task_info.update(info)
                st.success("✅ 과업지시서 파싱 완료")
                st.text_input("사업명", value=info.get("사업명", ""), key="edit_사업명")
                st.text_input("지자체명", value=info.get("지자체명", ""), key="edit_지자체명")
                st.text_input("과업기간", value=info.get("과업기간", ""), key="edit_과업기간")
                st.text_input("목표연도", value=info.get("목표연도", ""), key="edit_목표연도")
        
        if eval_file:
            eval_text = extract_text_from_pdf(eval_file)
            if eval_text:
                city = st.session_state.get("edit_지자체명", "") or st.session_state.task_info.get("지자체명", "")
                eval_info = parse_eval_pdf(eval_text, city)
                st.session_state.eval_info = eval_info
                st.success("✅ 평가기준서 파싱 완료")
                st.text_input("발주처", value=eval_info.get("발주처", ""), key="edit_발주처")
                st.text_input("분야", value=", ".join(eval_info.get("분야", [])), key="edit_분야")
        
        st.text_input("도명 (전북특별자치도 등)", value="", key="edit_도명",
                      help="자동 감지 안 되면 직접 입력")
    
    # QBS 분석
    if qbs_files:
        st.markdown("---")
        st.subheader("📚 참고QBS 분석")
        qbs_list = []
        for qf in qbs_files:
            pages = extract_pages_from_pdf(qf)
            if pages:
                sections = extract_qbs_sections(pages)
                identity = extract_qbs_identity(pages)
                
                # 이미지 추출
                images = extract_images_from_pdf(qf)
                
                qbs_list.append({
                    "name": qf.name[:30],
                    "pages": pages, "sections": sections,
                    "identity": identity, "images": images,
                })
                
                col_a, col_b, col_c = st.columns([2, 1, 1])
                with col_a:
                    st.write(f"✅ {qf.name[:40]}")
                with col_b:
                    st.caption(f"지자체: {identity.get('city', '?')}")
                with col_c:
                    st.caption(f"이미지: {len(images)}개")
        
        st.session_state.qbs_list = qbs_list
        
        if qbs_list:
            names = [q["name"] for q in qbs_list]
            st.session_state.main_qbs_idx = st.selectbox(
                "메인 QBS 선택", range(len(names)),
                format_func=lambda x: names[x], key="main_select"
            )
    
    # 다음 버튼
    st.markdown("---")
    if st.button("다음 단계로 →", type="primary", use_container_width=True):
        ti = st.session_state.task_info
        ti["사업명"] = st.session_state.get("edit_사업명", ti.get("사업명", ""))
        ti["지자체명"] = st.session_state.get("edit_지자체명", ti.get("지자체명", ""))
        ti["과업기간"] = st.session_state.get("edit_과업기간", ti.get("과업기간", ""))
        ti["목표연도"] = st.session_state.get("edit_목표연도", ti.get("목표연도", ""))
        ti["도명"] = st.session_state.get("edit_도명", "")
        ti["발주처"] = st.session_state.get("edit_발주처", st.session_state.eval_info.get("발주처", ""))
        ti["분야"] = [f.strip() for f in st.session_state.get("edit_분야", "").split(",") if f.strip()]
        
        if ti.get("도명") and ti.get("지자체명"):
            ti["위치"] = f"{ti['도명']} {ti['지자체명']}"
        elif ti.get("지자체명"):
            ti["위치"] = ti["지자체명"]
        
        for q in st.session_state.qbs_list:
            q["replacer"] = build_replacer(ti, q["identity"])
        
        st.session_state.task_info = ti
        st.session_state.current_step = 1
        st.rerun()


def render_section_step(section_id):
    """2단 레이아웃: 왼쪽(참고/검증) + 오른쪽(작성)"""
    title = SECTION_TITLES.get(section_id, section_id)
    step_num = ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "2.4"].index(section_id) + 1
    step_key = f"step{step_num}_data"
    
    st.header(f"[{section_id}] {title}")
    
    qbs_list = st.session_state.qbs_list
    main_idx = st.session_state.main_qbs_idx
    task_info = st.session_state.task_info
    
    if not qbs_list:
        st.warning("참고QBS가 없습니다. STEP 0으로 돌아가세요.")
        return
    
    # 메인 QBS 치환 텍스트 준비
    main_text = qbs_list[main_idx]["sections"].get(section_id, "")
    replacer = qbs_list[main_idx].get("replacer")
    main_replaced = replacer(main_text) if replacer and main_text else main_text
    
    # === 2단 레이아웃 ===
    col_ref, col_edit = st.columns([1, 1])
    
    # --- 왼쪽: 참고 + 검증 ---
    with col_ref:
        # 기본 정보 (1.1에서만)
        if section_id == "1.1":
            with st.expander("📋 과업 기본 정보", expanded=True):
                st.markdown(f"""
                | 항목 | 내용 |
                |------|------|
                | 사업명 | {task_info.get('사업명', '?')} |
                | 위치 | {task_info.get('위치', '?')} |
                | 과업기간 | {task_info.get('과업기간', '?')} |
                | 목표연도 | {task_info.get('목표연도', '?')} |
                | 발주처 | {task_info.get('발주처', '?')} |
                | 분야 | {', '.join(task_info.get('분야', []))} |
                """)
        
        # 분야 대조 (2.1, 2.4)
        if section_id in ("2.1", "2.4"):
            with st.expander("🔍 분야 대조", expanded=True):
                for field in task_info.get("분야", []):
                    fn = re.sub(r'\s+', '', field)
                    mn = re.sub(r'\s+', '', main_text)
                    if fn in mn:
                        st.success(f"✅ {field}")
                    else:
                        found = None
                        for i, q in enumerate(qbs_list):
                            if i != main_idx and fn in re.sub(r'\s+', '', q["sections"].get(section_id, "")):
                                found = q["name"]
                                break
                        if found:
                            st.warning(f"⚠️ {field} — **{found}**에서 발췌")
                        else:
                            st.error(f"❌ {field} — 수동 작성 필요")
        
        # 참고 원문 탭
        st.subheader("📖 참고 원문")
        tab_names = [f"메인: {qbs_list[main_idx]['name']}"]
        for i, q in enumerate(qbs_list):
            if i != main_idx:
                tab_names.append(f"참고: {q['name']}")
        
        tabs = st.tabs(tab_names)
        with tabs[0]:
            if main_replaced:
                st.text_area("치환 완료", main_replaced, height=300,
                            key=f"ref_main_{section_id}", disabled=True)
            else:
                st.info("해당 섹션 없음")
        
        ref_idx = 0
        for i, q in enumerate(qbs_list):
            if i == main_idx:
                continue
            ref_idx += 1
            with tabs[ref_idx]:
                rt = q["sections"].get(section_id, "")
                rp = q.get("replacer")
                if rp and rt:
                    rt = rp(rt)
                st.text_area("치환 완료", rt if rt else "(없음)", height=300,
                            key=f"ref_{section_id}_{i}", disabled=True)
        
        # 참고 이미지 (해당 QBS에서 추출된 이미지)
        all_images = []
        for q in qbs_list:
            for img in q.get("images", []):
                all_images.append({"source": q["name"], **img})
        
        if all_images:
            with st.expander(f"🖼️ 참고 이미지 ({len(all_images)}개)"):
                for img_obj in all_images[:8]:
                    st.image(img_obj["img"], caption=f"{img_obj['source']} p.{img_obj['page']}",
                            use_container_width=True)
    
    # --- 오른쪽: 작성 ---
    with col_edit:
        st.subheader("✍️ 작성")
        
        existing = st.session_state.get(step_key, {})
        default = existing.get("content", "")
        if not default and main_replaced:
            default = main_replaced
        
        user_content = st.text_area(
            "내용 작성 (왼쪽 원문을 참고하여 편집)",
            value=default, height=500,
            key=f"edit_{section_id}"
        )
        
        # 실시간 정합성 체크
        if user_content.strip():
            issues = check_consistency(user_content, task_info)
            if issues:
                st.markdown("---")
                st.subheader("🔍 정합성 체크")
                for level, msg in issues:
                    if level == "error":
                        st.error(f"⚠️ {msg}")
                    elif level == "info":
                        st.info(f"💡 {msg}")
            else:
                st.success("✅ 정합성 체크 통과")
        
        # 메모
        user_note = st.text_area("메모 (선택)", value=existing.get("note", ""),
                                  height=80, key=f"note_{section_id}")
    
    # 네비게이션
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← 이전", use_container_width=True):
            st.session_state[step_key] = {"content": user_content, "note": user_note}
            st.session_state.current_step -= 1
            st.rerun()
    with col3:
        if st.button("다음 →", type="primary", use_container_width=True):
            st.session_state[step_key] = {"content": user_content, "note": user_note}
            st.session_state.current_step += 1
            st.rerun()


def render_download():
    """STEP 8: 최종 확인 + 다운로드"""
    st.header("📥 최종 확인 및 다운로드")
    
    task_info = st.session_state.task_info
    
    st.markdown(f"""
    | 항목 | 내용 |
    |------|------|
    | 사업명 | {task_info.get('사업명', '?')} |
    | 위치 | {task_info.get('위치', '?')} |
    | 발주처 | {task_info.get('발주처', '?')} |
    | 과업기간 | {task_info.get('과업기간', '?')} |
    | 분야 | {', '.join(task_info.get('분야', []))} |
    """)
    
    st.markdown("---")
    sections = ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "2.4"]
    all_data = {}
    
    for i, sid in enumerate(sections):
        data = st.session_state.get(f"step{i+1}_data", {})
        content = data.get("content", "")
        status = "✅" if content.strip() else "⬜"
        title = SECTION_TITLES.get(sid, sid)
        
        with st.expander(f"{status} [{sid}] {title}"):
            if content.strip():
                st.text(content[:500] + ("..." if len(content) > 500 else ""))
            else:
                st.warning("비어있음")
        
        all_data[sid] = {"title": title, "content": content, "note": data.get("note", "")}
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        json_out = {
            "생성일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "기본정보": {k: task_info.get(k, "") for k in ["사업명", "위치", "발주처", "과업기간", "목표연도"]},
            "섹션": all_data,
        }
        json_out["기본정보"]["분야"] = task_info.get("분야", [])
        st.download_button("📄 JSON 다운로드", json.dumps(json_out, ensure_ascii=False, indent=2),
                          f"QBS_{task_info.get('사업명', '초안')}.json", "application/json",
                          use_container_width=True)
    
    with col2:
        lines = [f"PQ 평가서 초안 — {datetime.now().strftime('%Y-%m-%d')}",
                 f"사업명: {task_info.get('사업명', '')}", "=" * 50]
        for sid, d in all_data.items():
            lines.extend([f"\n[{sid}] {d['title']}", "-" * 40, d["content"] or "(비어있음)"])
        st.download_button("📝 TXT 다운로드", "\n".join(lines),
                          f"QBS_{task_info.get('사업명', '초안')}.txt", "text/plain",
                          use_container_width=True)
    
    st.markdown("---")
    if st.button("← 이전 단계로", use_container_width=True):
        st.session_state.current_step -= 1
        st.rerun()


# ============================
# 7. 메인 라우터
# ============================

def main():
    init_session_state()
    render_sidebar()
    
    step = st.session_state.current_step
    section_map = {1: "1.1", 2: "1.2", 3: "1.3", 4: "2.1", 5: "2.2", 6: "2.3", 7: "2.4"}
    
    if step == 0:
        render_step0()
    elif step in section_map:
        render_section_step(section_map[step])
    elif step == 8:
        render_download()
    else:
        st.session_state.current_step = 0
        st.rerun()


if __name__ == "__main__":
    main()
