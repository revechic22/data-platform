"""
PQ 평가서 웹 기반 작성 도구 (QBS Auto Draft Tool)
=================================================
Streamlit 기반 단계별 QBS 초안 작성 지원 도구
진입점: pq_tool/SRC/app.py
실행: streamlit run pq_tool/SRC/app.py
"""

import streamlit as st
import pdfplumber
import re
import json
import io
from datetime import datetime

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
# 1. 유틸리티 함수 (파싱/분석)
# ============================

def extract_text_from_pdf(uploaded_file):
    """업로드된 PDF에서 전체 텍스트 추출"""
    try:
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


def parse_task_pdf(text):
    """과업지시서에서 핵심 정보 추출"""
    info = {}
    
    # 사업명
    match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', text)
    if match:
        info["사업명"] = match.group(1).strip()
    else:
        info["사업명"] = ""
    
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
    info["과업범위"] = scope
    
    return info


def parse_eval_pdf(text, city=""):
    """평가기준서에서 발주처명, 분야 추출"""
    info = {}
    
    # 발주처
    if city:
        client_match = re.search(
            r'(' + re.escape(city) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))',
            text
        )
        info["발주처"] = client_match.group(1).strip() if client_match else f"{city} (수동입력 필요)"
    else:
        info["발주처"] = "(지자체명 미감지 — 수동입력 필요)"
    
    # 분야
    fields = []
    for pattern in [r'상하수도', r'구조', r'토질\s*[·‧]\s*지질', r'수자원개발',
                    r'환경\s*[\(（]\s*수질\s*[\)）]', r'기계', r'전기']:
        match = re.search(pattern, text)
        if match:
            fields.append(match.group(0).strip())
    # 환경(수질) fallback
    if not any('환경' in f for f in fields):
        if re.search(r'환경.*수질|수질.*환경', text):
            fields.append('환경(수질)')
    info["분야"] = fields
    
    return info


# ============================
# 2. QBS 섹션 분리 함수
# ============================

# 섹션 정의
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
    """페이지 텍스트 앞부분에서 섹션 번호 감지"""
    header = text[:top_n_chars]
    header_clean = re.sub(r'\s+', ' ', header).strip()
    header_nospace = re.sub(r'\s+', '', header_clean)
    for sec_num, keywords in SECTION_DEFS:
        num_escaped = re.escape(sec_num)
        num_found = re.search(
            rf'(?:^|\s|\.|\(|\)|:|;|,){num_escaped}(?:\s|\.|\(|:|,|[가-힣])',
            header_clean
        )
        if not num_found:
            continue
        for kw in keywords:
            kw_nospace = re.sub(r'\s+', '', kw)
            if kw_nospace in header_nospace:
                return sec_num
    return None


def _is_toc_page(text):
    """목차 페이지 판정"""
    text_clean = re.sub(r'\s+', ' ', text[:500]).strip()
    if re.search(r'목\s*차', text_clean):
        nums = re.findall(r'[12]\.[1-4]', text_clean)
        if len(nums) >= 3:
            return True
    return False


def extract_qbs_sections(pages_text):
    """QBS 페이지 텍스트 리스트에서 1.1~2.4 섹션 분리"""
    page_info = []
    for i, text in enumerate(pages_text):
        if _is_toc_page(text):
            page_info.append((i, text, "__SKIP__"))
            continue
        detected = _detect_section_from_page(text)
        page_info.append((i, text, detected))
    
    sections = {}
    current_section = None
    current_texts = []
    for i, text, detected in page_info:
        if detected == "__SKIP__":
            continue
        if detected is not None:
            if current_section is not None:
                sections[current_section] = "\n".join(current_texts)
            current_section = detected
            current_texts = [text]
        else:
            if current_section is not None:
                current_texts.append(text)
    if current_section is not None:
        sections[current_section] = "\n".join(current_texts)
    
    for sec_num, _ in SECTION_DEFS:
        if sec_num not in sections:
            sections[sec_num] = ""
    
    return sections


# ============================
# 3. QBS Identity 추출 + 치환
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
    """QBS 페이지 텍스트에서 지자체명, 도명, 발주처명 추출"""
    result = {"city": None, "province": None, "client": None}
    
    body_text = "\n".join(pages_text[1:])[:3000] if len(pages_text) > 1 else pages_text[0][:3000]
    full_text = "\n".join(pages_text)
    
    # 지자체명
    m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도정비', body_text)
    if not m:
        m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도', body_text)
    if m:
        result["city"] = m.group(1)
    
    # 도명
    for prov in PROVINCE_LIST:
        if prov in full_text[:5000]:
            result["province"] = prov
            break
    if not result["province"]:
        for short, full_name in PROVINCE_SHORT.items():
            if re.search(re.escape(short) + r'[\s·,]', full_text[:5000]):
                result["province"] = full_name
                break
    
    # 발주처명
    later_text = "\n".join(pages_text[max(0, len(pages_text)-4):])
    if result["city"]:
        cm = re.search(
            r'(' + re.escape(result["city"]) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))',
            later_text
        )
        if cm:
            result["client"] = cm.group(1).strip()
    
    return result


def build_replacer(task_info, qbs_identity):
    """치환 함수 생성"""
    target_city = task_info.get("지자체명", "")
    target_province = task_info.get("도명", "")
    target_client = task_info.get("발주처", "")
    
    src_city = qbs_identity.get("city") or ""
    src_province = qbs_identity.get("province") or ""
    src_client = qbs_identity.get("client") or ""
    
    def do_replace(text):
        result = text
        if src_client and target_client:
            result = result.replace(src_client, target_client)
        if src_city:
            result = re.sub(re.escape(src_city) + r'청', target_city, result)
        if src_city and target_city and src_city != target_city:
            result = result.replace(src_city, target_city)
        if src_province and target_province and src_province != target_province:
            result = result.replace(src_province, target_province)
        for short, full in PROVINCE_SHORT.items():
            if full == src_province and target_province:
                result = re.sub(
                    r'(?<![가-힣])' + re.escape(short) + r'(?![가-힣])',
                    target_province, result
                )
        return result
    
    return do_replace


# ============================
# 4. 상태 초기화
# ============================

def init_session_state():
    """session_state 초기화"""
    defaults = {
        "current_step": 0,
        "task_info": {},
        "eval_info": {},
        "qbs_list": [],         # [{name, pages, sections, identity, replacer}, ...]
        "main_qbs_idx": 0,
        
        # 각 STEP 입력 결과
        "step1_data": {},       # 1.1
        "step2_data": {},       # 1.2
        "step3_data": {},       # 1.3
        "step4_data": {},       # 2.1
        "step5_data": {},       # 2.2
        "step6_data": {},       # 2.3
        "step7_data": {},       # 2.4
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================
# 5. UI 렌더링 함수
# ============================

def render_sidebar():
    """사이드바: 진행 상태 표시"""
    steps = [
        "📁 파일 업로드",
        "1.1 사업의 내용",
        "1.2 유사사업",
        "1.3 성공요건",
        "2.1 수행범위",
        "2.2 작업계획서",
        "2.3 품질관리",
        "2.4 전문가 활용",
        "📥 다운로드",
    ]
    
    st.sidebar.title("📋 QBS 작성 도구")
    st.sidebar.markdown("---")
    
    for i, step_name in enumerate(steps):
        if i == st.session_state.current_step:
            st.sidebar.markdown(f"**▶ {step_name}**")
        elif i < st.session_state.current_step:
            st.sidebar.markdown(f"✅ {step_name}")
        else:
            st.sidebar.markdown(f"⬜ {step_name}")
    
    st.sidebar.markdown("---")
    st.sidebar.caption(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}")


def render_step0():
    """STEP 0: 파일 업로드 + 기본 정보 확인"""
    st.header("📁 STEP 0: 파일 업로드 및 기본 정보 확인")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("파일 업로드")
        task_file = st.file_uploader("과업지시서 PDF", type="pdf", key="task_pdf")
        eval_file = st.file_uploader("평가기준서 PDF", type="pdf", key="eval_pdf")
        qbs_files = st.file_uploader(
            "참고QBS PDF (여러 개 가능)", 
            type="pdf", 
            accept_multiple_files=True, 
            key="qbs_pdfs"
        )
    
    with col2:
        st.subheader("자동 파싱 결과")
        
        # 과업지시서 파싱
        if task_file:
            task_file.seek(0)
            task_text = extract_text_from_pdf(task_file)
            if task_text:
                task_info = parse_task_pdf(task_text)
                st.session_state.task_info = task_info
                
                st.success("과업지시서 파싱 완료")
                st.text_input("사업명", value=task_info.get("사업명", ""), key="edit_사업명")
                st.text_input("지자체명", value=task_info.get("지자체명", ""), key="edit_지자체명")
                st.text_input("과업기간", value=task_info.get("과업기간", ""), key="edit_과업기간")
                st.text_input("목표연도", value=task_info.get("목표연도", ""), key="edit_목표연도")
        
        # 평가기준서 파싱
        if eval_file:
            eval_file.seek(0)
            eval_text = extract_text_from_pdf(eval_file)
            if eval_text:
                city = st.session_state.get("edit_지자체명", "") or st.session_state.task_info.get("지자체명", "")
                eval_info = parse_eval_pdf(eval_text, city)
                st.session_state.eval_info = eval_info
                
                st.success("평가기준서 파싱 완료")
                st.text_input("발주처", value=eval_info.get("발주처", ""), key="edit_발주처")
                st.text_input("분야", value=", ".join(eval_info.get("분야", [])), key="edit_분야")
        
        # 도명 입력 (자동 감지 안 될 때)
        st.text_input(
            "도명 (전북특별자치도, 전라남도 등)", 
            value="", 
            key="edit_도명",
            help="과업지시서에서 자동 감지 안 되면 직접 입력"
        )
    
    # QBS 파싱
    if qbs_files:
        st.markdown("---")
        st.subheader("참고QBS 분석")
        
        qbs_list = []
        for qf in qbs_files:
            qf.seek(0)
            pages = extract_pages_from_pdf(qf)
            if pages:
                sections = extract_qbs_sections(pages)
                identity = extract_qbs_identity(pages)
                qbs_list.append({
                    "name": qf.name[:30],
                    "pages": pages,
                    "sections": sections,
                    "identity": identity,
                })
                st.write(f"✅ {qf.name[:40]} → 지자체: {identity.get('city', '?')}, 발주처: {identity.get('client', '?')}")
        
        st.session_state.qbs_list = qbs_list
        
        if qbs_list:
            qbs_names = [q["name"] for q in qbs_list]
            main_idx = st.selectbox("메인 QBS 선택", range(len(qbs_names)), 
                                    format_func=lambda x: qbs_names[x], key="main_qbs_select")
            st.session_state.main_qbs_idx = main_idx
    
    # 다음 버튼
    st.markdown("---")
    if st.button("다음 단계로 →", type="primary", use_container_width=True):
        # 사용자 편집 내용을 task_info에 반영
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
        
        # QBS별 치환 함수 생성
        for q in st.session_state.qbs_list:
            q["replacer"] = build_replacer(ti, q["identity"])
        
        st.session_state.task_info = ti
        st.session_state.current_step = 1
        st.rerun()


def render_section_step(section_id):
    """공통 섹션 편집 화면"""
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
    
    # --- 기본 정보 표시 (1.1에서만) ---
    if section_id == "1.1":
        with st.expander("📋 과업지시서 기본 정보", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**사업명:** {task_info.get('사업명', '?')}")
                st.write(f"**위치:** {task_info.get('위치', '?')}")
                st.write(f"**과업기간:** {task_info.get('과업기간', '?')}")
            with col2:
                st.write(f"**목표연도:** {task_info.get('목표연도', '?')}")
                st.write(f"**발주처:** {task_info.get('발주처', '?')}")
                st.write(f"**분야:** {', '.join(task_info.get('분야', []))}")
            
            if task_info.get("과업범위"):
                st.write("**과업범위:**")
                for s in task_info["과업범위"]:
                    st.write(f"  - {s}")
    
    # --- 분야 대조 (2.1, 2.4에서) ---
    if section_id in ("2.1", "2.4"):
        with st.expander("🔍 분야 대조 (평가기준서 vs 메인 QBS)", expanded=True):
            eval_fields = task_info.get("분야", [])
            main_section_text = qbs_list[main_idx]["sections"].get(section_id, "")
            
            for field in eval_fields:
                field_nospace = re.sub(r'\s+', '', field)
                main_nospace = re.sub(r'\s+', '', main_section_text)
                
                if field_nospace in main_nospace:
                    st.write(f"✅ {field} — 메인 QBS에 있음")
                else:
                    # 참고QBS에서 찾기
                    found_in = None
                    for i, q in enumerate(qbs_list):
                        if i == main_idx:
                            continue
                        ref_text = q["sections"].get(section_id, "")
                        if field_nospace in re.sub(r'\s+', '', ref_text):
                            found_in = q["name"]
                            break
                    if found_in:
                        st.write(f"⚠️ {field} — 메인에 없음, **{found_in}**에서 발췌 필요")
                    else:
                        st.write(f"❌ {field} — 메인/참고 모두 없음, 수동 작성 필요")
    
    # --- 메인 QBS 원문 (치환) + 참고QBS 탭 ---
    st.subheader("참고 원문")
    
    tab_names = [f"메인: {qbs_list[main_idx]['name']}"]
    for i, q in enumerate(qbs_list):
        if i != main_idx:
            tab_names.append(f"참고: {q['name']}")
    
    tabs = st.tabs(tab_names)
    
    # 메인 탭
    with tabs[0]:
        main_text = qbs_list[main_idx]["sections"].get(section_id, "")
        replacer = qbs_list[main_idx].get("replacer")
        if replacer and main_text:
            main_text_replaced = replacer(main_text)
        else:
            main_text_replaced = main_text
        
        if main_text_replaced:
            st.text_area("메인 QBS 원문 (치환 완료)", main_text_replaced, height=400, 
                        key=f"main_view_{section_id}", disabled=True)
        else:
            st.info("해당 섹션 없음")
    
    # 참고 탭
    ref_tab_idx = 0
    for i, q in enumerate(qbs_list):
        if i == main_idx:
            continue
        ref_tab_idx += 1
        with tabs[ref_tab_idx]:
            ref_text = q["sections"].get(section_id, "")
            replacer = q.get("replacer")
            if replacer and ref_text:
                ref_text_replaced = replacer(ref_text)
            else:
                ref_text_replaced = ref_text
            
            if ref_text_replaced:
                st.text_area(f"참고 QBS 원문 (치환)", ref_text_replaced, height=400,
                            key=f"ref_view_{section_id}_{i}", disabled=True)
            else:
                st.info("해당 섹션 없음")
    
    # --- 사용자 편집 영역 ---
    st.subheader("✏️ 작성 내용")
    
    # 기존 입력 내용 복원
    existing = st.session_state.get(step_key, {})
    default_text = existing.get("content", "")
    
    # 처음 진입 시 메인 QBS 치환 텍스트를 기본값으로
    if not default_text and main_text_replaced:
        default_text = main_text_replaced
    
    user_content = st.text_area(
        f"{section_id} 내용 작성 (위 원문을 참고하여 편집)",
        value=default_text,
        height=500,
        key=f"edit_content_{section_id}"
    )
    
    # 메모/주의사항
    user_note = st.text_area(
        "메모 (선택)",
        value=existing.get("note", ""),
        height=100,
        key=f"edit_note_{section_id}"
    )
    
    # 네비게이션
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← 이전", use_container_width=True):
            # 현재 입력 저장
            st.session_state[step_key] = {"content": user_content, "note": user_note}
            st.session_state.current_step -= 1
            st.rerun()
    
    with col3:
        if st.button("다음 →", type="primary", use_container_width=True):
            # 현재 입력 저장
            st.session_state[step_key] = {"content": user_content, "note": user_note}
            st.session_state.current_step += 1
            st.rerun()


def render_download():
    """STEP 8: 최종 확인 + 다운로드"""
    st.header("📥 최종 확인 및 다운로드")
    
    task_info = st.session_state.task_info
    
    # 요약 표시
    st.subheader("기본 정보")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**사업명:** {task_info.get('사업명', '?')}")
        st.write(f"**위치:** {task_info.get('위치', '?')}")
        st.write(f"**발주처:** {task_info.get('발주처', '?')}")
    with col2:
        st.write(f"**과업기간:** {task_info.get('과업기간', '?')}")
        st.write(f"**목표연도:** {task_info.get('목표연도', '?')}")
        st.write(f"**분야:** {', '.join(task_info.get('분야', []))}")
    
    # 각 섹션 내용 요약
    st.markdown("---")
    st.subheader("섹션별 작성 현황")
    
    sections = ["1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "2.4"]
    all_data = {}
    
    for i, sec_id in enumerate(sections):
        step_key = f"step{i+1}_data"
        data = st.session_state.get(step_key, {})
        content = data.get("content", "")
        
        status = "✅" if content.strip() else "⬜ (비어있음)"
        title = SECTION_TITLES.get(sec_id, sec_id)
        
        with st.expander(f"{status} [{sec_id}] {title}"):
            if content.strip():
                st.text(content[:500] + ("..." if len(content) > 500 else ""))
            else:
                st.warning("내용이 없습니다. 해당 단계로 돌아가서 작성해 주세요.")
        
        all_data[sec_id] = {
            "title": title,
            "content": content,
            "note": data.get("note", ""),
        }
    
    # 다운로드 옵션
    st.markdown("---")
    st.subheader("다운로드")
    
    col1, col2 = st.columns(2)
    
    # JSON 다운로드
    with col1:
        json_output = {
            "생성일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "기본정보": {
                "사업명": task_info.get("사업명", ""),
                "위치": task_info.get("위치", ""),
                "발주처": task_info.get("발주처", ""),
                "과업기간": task_info.get("과업기간", ""),
                "목표연도": task_info.get("목표연도", ""),
                "분야": task_info.get("분야", []),
            },
            "섹션": all_data,
        }
        json_str = json.dumps(json_output, ensure_ascii=False, indent=2)
        st.download_button(
            "📄 JSON 다운로드 (HWPX 변환용)",
            json_str,
            file_name=f"QBS_{task_info.get('사업명', '초안')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # TXT 다운로드
    with col2:
        txt_lines = []
        txt_lines.append(f"PQ 평가서 초안")
        txt_lines.append(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        txt_lines.append(f"사업명: {task_info.get('사업명', '')}")
        txt_lines.append(f"위치: {task_info.get('위치', '')}")
        txt_lines.append(f"발주처: {task_info.get('발주처', '')}")
        txt_lines.append("=" * 60)
        
        for sec_id, data in all_data.items():
            txt_lines.append(f"\n[{sec_id}] {data['title']}")
            txt_lines.append("-" * 40)
            txt_lines.append(data["content"] if data["content"] else "(비어있음)")
            if data["note"]:
                txt_lines.append(f"\n※ 메모: {data['note']}")
        
        txt_output = "\n".join(txt_lines)
        st.download_button(
            "📝 TXT 다운로드 (붙여넣기용)",
            txt_output,
            file_name=f"QBS_{task_info.get('사업명', '초안')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    # 이전 버튼
    st.markdown("---")
    if st.button("← 이전 단계로", use_container_width=True):
        st.session_state.current_step -= 1
        st.rerun()


# ============================
# 6. 메인 라우터
# ============================

def main():
    """메인 실행"""
    init_session_state()
    render_sidebar()
    
    step = st.session_state.current_step
    
    if step == 0:
        render_step0()
    elif step == 1:
        render_section_step("1.1")
    elif step == 2:
        render_section_step("1.2")
    elif step == 3:
        render_section_step("1.3")
    elif step == 4:
        render_section_step("2.1")
    elif step == 5:
        render_section_step("2.2")
    elif step == 6:
        render_section_step("2.3")
    elif step == 7:
        render_section_step("2.4")
    elif step == 8:
        render_download()
    else:
        st.session_state.current_step = 0
        st.rerun()


if __name__ == "__main__":
    main()
