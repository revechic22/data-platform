import subprocess
import sys
import os
import re
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

# ============================
# 경로 설정 (범용화)
# ============================
base_dir = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool"
task_dir = os.path.join(base_dir, r"data\과업지시서")
eval_dir = os.path.join(base_dir, r"data\평가기준서")
qbs_dir = os.path.join(base_dir, r"data\참고QBS\상수도")
output_dir = os.path.join(base_dir, "output")
os.makedirs(output_dir, exist_ok=True)

def find_single_pdf(folder, label):
    """폴더 내 PDF 1개를 자동으로 찾음. 없거나 2개 이상이면 안내."""
    pdfs = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
    if len(pdfs) == 0:
        print(f"[오류] {label} 폴더에 PDF 파일이 없습니다: {folder}")
        input("엔터를 누르면 종료됩니다...")
        sys.exit()
    if len(pdfs) > 1:
        print(f"[안내] {label} 폴더에 PDF가 {len(pdfs)}개 있습니다.")
        for i, f in enumerate(pdfs):
            print(f"  [{i+1}] {f}")
        sel = input("사용할 파일 번호를 입력하세요: ").strip()
        try:
            sel = int(sel) - 1
            if sel < 0 or sel >= len(pdfs):
                raise ValueError
        except ValueError:
            print("잘못된 번호입니다.")
            input("엔터를 누르면 종료됩니다...")
            sys.exit()
        return os.path.join(folder, pdfs[sel])
    return os.path.join(folder, pdfs[0])

task_pdf = find_single_pdf(task_dir, "과업지시서")
eval_pdf = find_single_pdf(eval_dir, "평가기준서")

print(f"  과업지시서: {os.path.basename(task_pdf)}")
print(f"  평가기준서: {os.path.basename(eval_pdf)}")
print("")

# ============================
# 참고QBS 선택
# ============================
pdf_files = sorted([f for f in os.listdir(qbs_dir) if f.lower().endswith('.pdf')])
if not pdf_files:
    print("참고QBS 폴더에 PDF 파일이 없습니다.")
    input("엔터를 누르면 종료됩니다...")
    sys.exit()

print("=" * 60)
print("  참고QBS 목록")
print("=" * 60)
for i, f in enumerate(pdf_files):
    short = f[:50] + ".." if len(f) > 50 else f
    print(f"  [{i+1}] {short}")
print("")
main_idx = input("메인 샘플 번호를 입력하세요: ").strip()

try:
    main_idx = int(main_idx) - 1
    if main_idx < 0 or main_idx >= len(pdf_files):
        raise ValueError
except ValueError:
    print("잘못된 번호입니다.")
    input("엔터를 누르면 종료됩니다...")
    sys.exit()

main_file = pdf_files[main_idx]
ref_files = [f for i, f in enumerate(pdf_files) if i != main_idx]

print(f"\n  메인: {main_file}")
for i, f in enumerate(ref_files):
    print(f"  참고{i+1}: {f}")
print("")

# ============================
# PART 1: 과업지시서 파싱 (범용화)
# ============================
all_text = ""
with pdfplumber.open(task_pdf) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"

task_info = {}

# 사업명: "본 과업의 명칭은 "ㅇㅇㅇ"" 패턴
match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', all_text)
if match:
    task_info["사업명"] = match.group(1).strip()

# 지자체명: "ㅇㅇ시(군) 전체 행정구역" 또는 사업명에서 추출
match = re.search(r'([가-힣]{1,4}(?:시|군))\s*전체\s*행정구역', all_text)
if match:
    task_info["지자체명"] = match.group(1).strip()
else:
    # 사업명에서 추출 시도: "완주군 수도정비..." → "완주군"
    name = task_info.get("사업명", "")
    m2 = re.match(r'([가-힣]{1,4}(?:시|군))\s', name)
    if m2:
        task_info["지자체명"] = m2.group(1).strip()

# 도 단위: "전북특별자치도 완주군" 등에서 추출
province_list = [
    '전북특별자치도', '전라남도', '전라북도', '경상남도', '경상북도',
    '충청남도', '충청북도', '강원특별자치도', '강원도', '경기도',
    '제주특별자치도', '세종특별자치시'
]
task_info["도명"] = ""
city = task_info.get("지자체명", "")
for prov in province_list:
    if prov in all_text:
        # "도명 + 지자체명"이 같이 있는지 확인
        if re.search(re.escape(prov) + r'\s*' + re.escape(city), all_text):
            task_info["도명"] = prov
            break
# 못 찾았으면 단독으로라도
if not task_info["도명"]:
    for prov in province_list:
        if prov in all_text:
            task_info["도명"] = prov
            break

# ★ 여기에 추가 ★
if not task_info.get("도명"):
    print("")
    print("  [안내] 과업지시서에서 도 단위 명칭을 자동 감지하지 못했습니다.")
    print("  예시: 전북특별자치도, 전라남도, 경상남도, 충청남도 등")
    user_prov = input("  도명을 입력하세요 (없으면 엔터): ").strip()
    if user_prov:
        task_info["도명"] = user_prov

# 위치
if task_info.get("도명") and task_info.get("지자체명"):
    task_info["위치"] = f"{task_info['도명']} {task_info['지자체명']}"
elif task_info.get("지자체명"):
    task_info["위치"] = task_info["지자체명"]

# 과업목적
purpose_match = re.search(r'(?:2|II)\s*[.\s]*\s*과업의\s*목적\s*\n(.*?)(?:3|III)\s*[.\s]*\s*과업의\s*개요', all_text, re.DOTALL)
if purpose_match:
    p = purpose_match.group(1).strip()
    p = re.sub(r'[◦○●■◆▶]', '', p)
    task_info["과업목적"] = '\n'.join([l.strip() for l in p.split('\n') if l.strip()])

# 과업기간
match = re.search(r'과업기간은?\s*착수일로부터\s*(\d+)\s*개월', all_text)
if match:
    task_info["과업기간"] = f"착수일로부터 {match.group(1)}개월"

# 목표연도
match = re.search(r'목표연도\s*[:：]?\s*(\d{4})\s*년', all_text)
if match:
    task_info["목표연도"] = f"{match.group(1)}년"

# 수행지침
match = re.search(r'수도정비기본계획\s*수립지침\s*\(.*?\)', all_text)
if match:
    task_info["수행지침"] = match.group(0).strip()

# 조사항목 상세 파싱
# 과업지시서 내 "조사항목" ~ "과업범위" 또는 "공정표" 사이 영역에서 추출
survey_items = []

# 방법1: 과업지시서에서 조사 관련 섹션을 찾아서 항목 추출
# "기초조사", "시설현황 조사" 등 대분류 항목을 찾음
survey_categories = [
    "기초자료 조사", "기초조사", "시설현황 조사", "시설현황조사",
    "직접조사", "정수시설 조사", "GIS 구축에 관한 조사", "GIS구축에 관한 조사",
    "수질조사", "관망조사", "급수현황 조사", "급수현황조사",
    "수원현황 조사", "수원현황조사", "운영현황 조사", "운영현황조사",
]

for cat in survey_categories:
    cat_nospace = re.sub(r'\s+', '', cat)
    text_nospace = re.sub(r'\s+', '', all_text)
    if cat_nospace in text_nospace:
        if cat not in survey_items:
            survey_items.append(cat)

# 방법2: "ㅇㅇ 조사" 패턴 중 과업지시서 조사항목 테이블에서만 추출
# 테이블 영역 탐색 (보통 "조사항목" 과 "조사내용" 이라는 헤더가 있음)
table_match = re.search(
    r'조사\s*항목(.*?)(?:과업\s*(?:범위|기간)|공정표|제\s*\d+\s*편)',
    all_text, re.DOTALL
)
if table_match:
    table_text = table_match.group(1)
    # 테이블 내에서 "ㅇㅇ 조사" 또는 "ㅇㅇ 현황" 패턴 추출 (3글자 이상)
    table_items = re.findall(r'([가-힣]{2,8}\s?(?:조사|현황|측정|시험))', table_text)
    for ti in table_items:
        ti_clean = ti.strip()
        if ti_clean not in survey_items and len(ti_clean) >= 3:
            survey_items.append(ti_clean)

task_info["조사항목"] = survey_items if survey_items else ["[자동 추출 실패 — 과업지시서에서 수동 확인]"]


# 패턴1: "ㅇ. ㅇㅇ조사" 또는 "ㅇ) ㅇㅇ조사" 형태
survey_matches = re.findall(
    r'[가-힣\d①-⑳❶-❿ⓐ-ⓩ).\s]{0,5}'
    r'([가-힣]{1,20}(?:조사|검토|분석|측정|현황)\s*[가-힣]{0,10})',
    all_text
)
# 중복 제거 및 정리
seen_survey = set()
for item in survey_matches:
    item_clean = item.strip()
    item_nospace = re.sub(r'\s+', '', item_clean)
    if len(item_clean) >= 4 and item_nospace not in seen_survey:
        # "기본사항의결정" 같은 오탐 제외
        if not re.search(r'결정|수립|제시|계획$', item_clean):
            seen_survey.add(item_nospace)
            survey_items.append(item_clean)

# 패턴2: 과업지시서 내 조사항목 테이블에서 추출 (보통 "조사항목" / "조사내용" 헤더)
survey_section = re.search(
    r'조사\s*항목.*?(?:조사\s*내용|내\s*용)(.*?)(?:과업\s*범위|제\s*\d+\s*편|공정표)',
    all_text, re.DOTALL
)
if survey_section:
    survey_text = survey_section.group(1)
    # 테이블 내 주요 항목 추출
    table_items = re.findall(r'([가-힣]{2,15}(?:조사|현황|검토|분석))', survey_text)
    for ti in table_items:
        ti_nospace = re.sub(r'\s+', '', ti)
        if ti_nospace not in seen_survey:
            seen_survey.add(ti_nospace)
            survey_items.append(ti.strip())

task_info["조사항목"] = survey_items


# 과업범위
scope = []
scope_matches = re.findall(r'[<＜]\s*제\s*(\d+)\s*편\s*(.*?)\s*[>＞]', all_text)
seen = set()
for num, name in scope_matches:
    key = f"제{num}편"
    if key not in seen and name.strip():
        scope.append(f"{key} {name.strip()}")
        seen.add(key)
task_info["과업범위"] = scope

# 평가기준서 파싱
eval_text = ""
with pdfplumber.open(eval_pdf) as pdf:
    for page in pdf.pages:
        t = page.extract_text()
        if t:
            eval_text += t + "\n"

# 발주처: "ㅇㅇ시(군) + 부서명" 패턴
client_match = re.search(
    r'(' + re.escape(city) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))',
    eval_text
)
if client_match:
    task_info["발주처"] = client_match.group(1).strip()
else:
    # 못 찾으면 일반 패턴
    client_match2 = re.search(r'([가-힣]{1,4}(?:시|군)(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))', eval_text)
    if client_match2:
        task_info["발주처"] = client_match2.group(1).strip()
    else:
        task_info["발주처"] = f"{city} (발주처명 수동입력 필요)"

# 분야
fields = []
for pattern in [r'상하수도', r'구조', r'토질\s*[·‧]\s*지질', r'수자원개발', r'환경\s*\(\s*수질\s*\)']:
    match = re.search(pattern, eval_text)
    if match:
        fields.append(match.group(0).strip())
task_info["분야"] = fields

# ============================
# PART 2: QBS 섹션 추출 함수
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

def _detect_section_from_page(text, top_n_chars=400):
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
    text_clean = re.sub(r'\s+', ' ', text[:500]).strip()
    if re.search(r'목\s*차', text_clean):
        nums = re.findall(r'[12]\.[1-4]', text_clean)
        if len(nums) >= 3:
            return True
    return False

def extract_qbs_sections(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            pages.append(text if text else "")
    page_info = []
    for i, text in enumerate(pages):
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

def get_short_name(filename):
    name = filename.replace('.pdf', '').replace('.PDF', '')
    if len(name) > 20:
        return name[:20] + ".."
    return name

# ============================
# PART 3: 치환 함수 (범용화)
# ============================

# 도명 약칭 → 정식명칭 매핑
PROVINCE_SHORT = {
    '전남': '전라남도', '전북': '전라북도', '경남': '경상남도',
    '경북': '경상북도', '충남': '충청남도', '충북': '충청북도',
}

def extract_qbs_identity(pdf_path):
    """
    QBS PDF에서 지자체명, 도명, 발주처명을 자동 추출.
    목차(1p)를 건너뛰고 본문에서 탐색.
    """
    result = {"city": None, "province": None, "client": None}
    
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            pages_text.append(t if t else "")
    
    # 본문 텍스트 (목차 제외 — 2페이지부터, 앞쪽 3000자)
    body_text = "\n".join(pages_text[1:])[:3000] if len(pages_text) > 1 else pages_text[0][:3000]
    full_text = "\n".join(pages_text)
    
    # 지자체명: 본문에서 "ㅇㅇ시(군) 수도정비" 패턴
    m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도정비', body_text)
    if not m:
        m = re.search(r'([가-힣]{1,4}(?:시|군))\s*수도', body_text)
    if not m:
        # 파일명에서 추출
        fname = os.path.basename(pdf_path)
        m = re.search(r'([가-힣]{1,4}(?:시|군))', fname)
    if m:
        result["city"] = m.group(1)
    
    # 도명: 본문에서 탐색
    for prov in province_list:
        if prov in full_text[:5000]:
            result["province"] = prov
            break
    if not result["province"]:
        for short, full_name in PROVINCE_SHORT.items():
            if re.search(re.escape(short) + r'[\s·,]', full_text[:5000]):
                result["province"] = full_name
                break
    
    # 발주처명: 뒤쪽 페이지(2.3~2.4)에서 탐색
    later_text = "\n".join(pages_text[max(0, len(pages_text)-4):])
    if result["city"]:
        cm = re.search(
            r'(' + re.escape(result["city"]) + r'(?:청\s*)?\s*\S{1,10}(?:사업소|센터|과))',
            later_text
        )
        if cm:
            result["client"] = cm.group(1).strip()
    
    return result


def build_replace_func(task_info, qbs_identity):
    target_city = task_info.get("지자체명", "")
    target_province = task_info.get("도명", "")
    target_client = task_info.get("발주처", "")
    
    src_city = qbs_identity.get("city") or ""
    src_province = qbs_identity.get("province") or ""
    src_client = qbs_identity.get("client") or ""
    
    def do_replace(text):
        result = text
        
        # 1단계: 발주처명 정확히 치환 (가장 먼저, 가장 긴 문자열)
        if src_client and target_client:
            result = result.replace(src_client, target_client)
        
        # 2단계: "ㅇㅇ시(군)청" → 지자체명
        if src_city:
            result = re.sub(re.escape(src_city) + r'청', target_city, result)
        
        # 3단계: 지자체명 치환
        if src_city and target_city and src_city != target_city:
            result = result.replace(src_city, target_city)
        
        # 4단계: 도명 치환
        if src_province and target_province and src_province != target_province:
            result = result.replace(src_province, target_province)
        
        # 5단계: 도명 약칭 치환
        for short, full in PROVINCE_SHORT.items():
            if full == src_province and target_province:
                result = re.sub(
                    r'(?<![가-힣])' + re.escape(short) + r'(?![가-힣])',
                    target_province, result
                )
        
        # 6단계 삭제 — 패턴 기반 부서명 치환은 오치환 위험이 큼
        # 발주처명은 1단계에서 정확한 문자열로만 치환
        
        return result
    
    return do_replace

# ============================
# PART 4: 모든 QBS 섹션 추출 + identity 추출
# ============================
print("QBS 섹션 및 identity 추출 중...")

main_path = os.path.join(qbs_dir, main_file)
main_sections = extract_qbs_sections(main_path)
main_identity = extract_qbs_identity(main_path)
main_replace = build_replace_func(task_info, main_identity)
main_name = get_short_name(main_file)

print(f"  메인 identity: {main_identity}")

ref_data = []
for f in ref_files:
    fpath = os.path.join(qbs_dir, f)
    try:
        sections = extract_qbs_sections(fpath)
        identity = extract_qbs_identity(fpath)
        replacer = build_replace_func(task_info, identity)
        print(f"  참고 identity: {identity}")
        ref_data.append({
            "name": get_short_name(f),
            "sections": sections,
            "replace": replacer
        })
    except Exception as e:
        print(f"  [경고] {f} 처리 실패: {e}")
        ref_data.append({
            "name": get_short_name(f),
            "sections": {},
            "replace": lambda t: t
        })

# ============================
# PART 5: 공정표 추출 (현재 완주군 전용 — 4순위에서 범용화 예정)
# ============================
schedule_data = []
try:
    with pdfplumber.open(task_pdf) as pdf:
        if len(pdf.pages) >= 9:
            page = pdf.pages[8]
            month_columns = [
                (268.7,289.8,1,2),(289.8,310.9,3,4),(310.9,331.9,5,6),
                (331.9,353.0,7,8),(353.0,374.0,9,10),(374.0,395.1,11,12),
                (395.1,416.2,13,14),(416.2,437.2,15,16),(437.2,458.3,17,18),
                (458.3,479.3,19,20),(479.3,500.4,21,22),(500.4,521.5,23,24),
            ]
            def x_to_months(x0,x1):
                sm,em=None,None
                for cx0,cx1,ms,me in month_columns:
                    if x0<cx1 and x1>cx0:
                        if sm is None:sm=ms
                        em=me
                return sm,em
            task_y_map = [
                (191,"제1편","1. 총설"),(213,"제1편","2. 기초조사"),
                (234,"제1편","3. 기본사항의결정"),(255,"제1편","4. 시설확충계획"),
                (277,"제1편","5. 시설개량계획"),(298,"제1편","6. 상수도 수질관리계획"),
                (319,"제1편","7. 상수도시설 유지관리계획"),(341,"제1편","8. 상수도시설 정보화계획"),
                (380,"제2편","1. 상수도 수요관리 목표설정"),(401,"제2편","2. 상수도 수요관리 사업계획"),
                (422,"제2편","3. 상수도 수요관리 재정계획"),
                (461,"제3편","1. 생산시설의 안정화계획"),(482,"제3편","2. 공급시설의 안정화계획"),
                (504,"제3편","3. 수도시설 비상연계계획"),(525,"제3편","4. 재해 및 위기관리 대책"),
                (546,"제3편","5. 상수도시설 안정화 재정계획"),
                (585,"제4편","1. 사업시행 및 재정계획"),(607,"제4편","2. 수도사업 경영 개선계획"),
                (628,"","Ⅴ. 성과품 작성 및 납품"),
            ]
            def y_to_task(y):
                for ty,g,n in task_y_map:
                    if abs(y-ty)<10:return g,n
                return None,None
            rects=[r for r in page.rects if r['x0']>=260 and r['x1']<=520]
            yg={}
            for r in rects:
                yk=round(r['top'],0)
                if yk not in yg:yg[yk]=[]
                yg[yk].append(r)
            for yk in sorted(yg.keys()):
                gr=yg[yk]
                mnx,mxx=min(r['x0'] for r in gr),max(r['x1'] for r in gr)
                sm,_=x_to_months(mnx,mnx+1)
                _,em=x_to_months(mxx-1,mxx)
                g,tn=y_to_task(yk)
                if tn and sm and em:
                    xs=sorted(gr,key=lambda r:r['x0'])
                    gap=any(xs[i+1]['x0']-xs[i]['x1']>25 for i in range(len(xs)-1))
                    w=" ※불연속" if gap else ""
                    schedule_data.append((g,tn,sm,em,em-sm+1,w))
except Exception as e:
    print(f"  [경고] 공정표 추출 실패 (4순위 범용화 필요): {e}")

if not schedule_data:
    print("  [안내] 공정표 데이터 없음 — 초안에 공정표 없이 생성됩니다.")

# ============================
# PART 6: 초안 생성
# ============================
lines = []
now = datetime.now().strftime("%Y-%m-%d %H:%M")

lines.append("╔" + "═"*58 + "╗")
lines.append("║  PQ 평가서 초안 (자동 생성)                              ║")
lines.append("║  " + f"생성일시: {now}" + " "*(56-len(f"생성일시: {now}")) + "║")
lines.append("║  " + f"메인: {main_name}" + " "*(56-len(f"메인: {main_name}")) + "║")
lines.append("╚" + "═"*58 + "╝")

lines.append("")
lines.append("=" * 60)
lines.append("  [치환 정보]")
lines.append("=" * 60)
lines.append(f"  사업명  : {task_info.get('사업명', '?')}")
lines.append(f"  위  치  : {task_info.get('위치', '?')}")
lines.append(f"  발주처  : {task_info.get('발주처', '?')}")
lines.append(f"  과업기간: {task_info.get('과업기간', '?')}")
lines.append(f"  목표연도: {task_info.get('목표연도', '?')}")
lines.append(f"  분야    : {', '.join(task_info.get('분야', []))}")
lines.append("")
lines.append("  [자동 감지된 치환 매핑]")
lines.append(f"  메인: {main_identity.get('city','?')} → {task_info.get('지자체명','?')}  |  "
             f"{main_identity.get('province','?')} → {task_info.get('도명','?')}  |  "
             f"{main_identity.get('client','?')} → {task_info.get('발주처','?')}")
for i, rd in enumerate(ref_data):
    if hasattr(rd.get('replace', None), '__self__'):
        continue
    # ref_data에서 identity를 별도로 저장하지 않았으므로 재추출
    pass

# 섹션별 출력 함수 (범용화 — 각 QBS별 개별 치환 함수 사용)
def write_section(section_id, title, notes=None):
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"  [{section_id}] {title}")
    lines.append("=" * 60)
    
    # 메인
    lines.append("")
    lines.append(f"  ▶ 메인 ({main_name}):")
    lines.append("  " + "-" * 40)
    main_text = main_sections.get(section_id, "")
    if main_text:
        replaced = main_replace(main_text)
        for l in replaced.split('\n'):
            if l.strip():
                lines.append(f"  {l.strip()}")
    else:
        lines.append("  [해당 섹션 없음]")
    
    # 참고
    for i, rd in enumerate(ref_data):
        lines.append("")
        lines.append(f"  ▶ 참고{i+1} ({rd['name']}):")
        lines.append("  " + "-" * 40)
        ref_text = rd["sections"].get(section_id, "")
        if ref_text:
            replaced = rd["replace"](ref_text)
            for l in replaced.split('\n'):
                if l.strip():
                    lines.append(f"  {l.strip()}")
        else:
            lines.append("  [해당 섹션 없음]")
    
    if notes:
        lines.append("")
        for note in notes:
            lines.append(f"  [※ {note}]")

# --- 1.1 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [1.1] 당해 사업의 내용 및 이해도")
lines.append("=" * 60)
lines.append("")
lines.append("  ▶ 과업지시서에서 추출한 기본 정보:")
lines.append(f"    과업목적:")
if task_info.get("과업목적"):
    for l in task_info["과업목적"].split('\n'):
        lines.append(f"      {l}")
lines.append(f"    위치: {task_info.get('위치', '?')}")
lines.append(f"    과업기간: {task_info.get('과업기간', '?')}")
lines.append(f"    목표연도: {task_info.get('목표연도', '?')}")
lines.append(f"    수행지침: {task_info.get('수행지침', '?')}")
lines.append("    과업범위:")
for s in task_info.get("과업범위", []):
    lines.append(f"      - {s}")
lines.append("")
city_name = task_info.get('지자체명', '해당 지자체')
lines.append(f"    [※ 삽도: {city_name} 위치도 삽입 필요]")

write_section("1.1", "1.1 원문 참고 (주안점 등)", [
    "1) 사업의 특성: 과업지시서 내용을 공간에 맞게 편집",
    "2) 내용 및 범위: 위 기본 정보 활용",
    "3) 주안점: 메인 원문 기반, 필요시 참고에서 발췌",
])

write_section("1.2", "당해 사업 관련 유사사업 제시", [
    "유사사업별 '금회용역 착안사항' 이미지 중복 여부 확인",
    "환산점수 낮은 과업은 교체 검토",
    "5건간 이미지가 동일하면 안 됨",
])

write_section("1.3", "사업 성공을 위한 요건 및 추가 제안사항", [
    "1), 3), 4)는 확인 후 문제 없으면 유지",
    "2) 설계방법, 5) 사업효과: 이미지가 1.2와 중복되면 교체",
    "관련 없는 내용이 들어가 있는지 확인",
])

# --- 2.1 (강화) ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.1] 당해 사업 관련 업무 수행범위 — 과업지시서 기반 보강")
lines.append("=" * 60)

# A. 조사항목 상세
lines.append("")
lines.append("  ▶ 과업지시서에서 추출한 조사항목:")
if task_info.get("조사항목"):
    for idx, item in enumerate(task_info["조사항목"], 1):
        lines.append(f"    {idx}. {item}")
else:
    lines.append("    [자동 추출 실패 — 과업지시서에서 수동 확인 필요]")

# B. 분야 대조 경고
lines.append("")
lines.append("  ▶ 분야 대조 (평가기준서 vs 메인 QBS):")
eval_fields = task_info.get("분야", [])
main_21_text = main_sections.get("2.1", "")
for field in eval_fields:
    field_nospace = re.sub(r'\s+', '', field)
    main_21_nospace = re.sub(r'\s+', '', main_21_text)
    if field_nospace in main_21_nospace:
        lines.append(f"    ✔ {field} — 메인 QBS에 있음")
    else:
        # 참고QBS에서 찾기
        found_in_ref = None
        for i, rd in enumerate(ref_data):
            ref_21 = rd["sections"].get("2.1", "")
            ref_21_nospace = re.sub(r'\s+', '', ref_21)
            if field_nospace in ref_21_nospace:
                found_in_ref = rd["name"]
                break
        if found_in_ref:
            lines.append(f"    ※ {field} — 메인에 없음, 참고({found_in_ref})에서 발췌 필요")
        else:
            lines.append(f"    ❌ {field} — 메인/참고 모두 없음, 수동 작성 필요")

# C. 공정표 기간 → 특이사항 기간 참고
lines.append("")
lines.append("  ▶ 공정표 기반 작업기간 참고 (2.1 ③ 특이사항에 반영):")
if schedule_data:
    # 편별로 그룹핑하여 최소 시작 ~ 최대 종료
    group_range = {}
    for g, tn, sm, em, d, w in schedule_data:
        label = g if g else "기타"
        if label not in group_range:
            group_range[label] = [sm, em]
        else:
            group_range[label][0] = min(group_range[label][0], sm)
            group_range[label][1] = max(group_range[label][1], em)
    
    for label, (s, e) in group_range.items():
        lines.append(f"    {label}: {s}개월 ~ {e}개월")
    
    # 성과품 작성 기간
    for g, tn, sm, em, d, w in schedule_data:
        if "성과품" in tn:
            lines.append(f"    성과품 작성 및 납품: {sm}개월 ~ {em}개월")
            break
else:
    lines.append("    [공정표 데이터 없음]")

# 기존 메인/참고 원문 출력
write_section("2.1", "당해 사업 관련 업무 수행범위 — 원문 참고", [
    "위 조사항목을 과업지시서 원문과 대조하여 누락 항목 확인",
    "분야 대조에서 ※/❌ 표시된 항목은 참고QBS에서 발췌하거나 수동 작성",
    "특이사항 기간은 위 공정표 기간을 초과하면 안 됨",
])


# --- 2.2 공정표 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.2] 작업계획서 — 과업지시서 공정표 기준")
lines.append("=" * 60)
lines.append(f"  ※ 전체 과업기간: {task_info.get('과업기간', '?')}")
lines.append(f"  ※ 각 공종은 아래 범위 이하로 설정할 것")
lines.append("")
if schedule_data:
    lines.append(f"  {'구분':<8} {'공종명':<28} {'시작':>4} {'종료':>4} {'기간':>6} {'비고'}")
    lines.append("  " + "-"*58)
    cg=""
    for g,tn,sm,em,d,w in schedule_data:
        if g and g!=cg:
            lines.append("")
            cg=g
        lines.append(f"  {g:<8} {tn:<28} {sm:>4} {em:>4} {d:>4}개월{w}")
else:
    lines.append("  [공정표 자동 추출 실패 — 수동 입력 또는 4순위 범용화 후 재시도]")
lines.append("")

write_section("2.2", "2.2 원문 참고 (배점/공종 조정용)", [
    "과업지시서 공정표 기간 초과 불가",
    "배점은 참고QBS를 참고하여 조정",
])

write_section("2.3", "품질보증체계 및 품질관리계획", [
    f"과업명 → {task_info.get('사업명', '?')}",
    f"발주처 → {task_info.get('발주처', '?')}",
    "위 두 가지 치환 외에는 거의 동일",
])

# --- 2.4 (분야 대조 추가) ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.4] 전문가 활용 — 분야 대조")
lines.append("=" * 60)
lines.append("")
lines.append("  ▶ 분야 대조 (평가기준서 vs 메인 QBS 2.4):")
main_24_text = main_sections.get("2.4", "")
for field in eval_fields:
    field_nospace = re.sub(r'\s+', '', field)
    main_24_nospace = re.sub(r'\s+', '', main_24_text)
    if field_nospace in main_24_nospace:
        lines.append(f"    ✔ {field} — 메인 QBS에 있음")
    else:
        found_in_ref = None
        for i, rd in enumerate(ref_data):
            ref_24 = rd["sections"].get("2.4", "")
            ref_24_nospace = re.sub(r'\s+', '', ref_24)
            if field_nospace in ref_24_nospace:
                found_in_ref = rd["name"]
                break
        if found_in_ref:
            lines.append(f"    ※ {field} — 메인에 없음, 참고({found_in_ref})에서 발췌 필요")
        else:
            lines.append(f"    ❌ {field} — 메인/참고 모두 없음, 수동 작성 필요")

write_section("2.4", "전문가 활용계획 등 추가 업무관리사항 — 원문 참고", [
    f"발주처 → {task_info.get('발주처', '?')}",
    f"분야 확인: {', '.join(task_info.get('분야', []))}",
    "위 분야 대조에서 ※/❌ 표시된 분야는 참고QBS에서 발췌하거나 수동 추가",
    "이미지 내 발주처명 수동 변경 필요",
])

lines.append("")
lines.append("=" * 60)
lines.append("  END")
lines.append("=" * 60)

# ============================
# 저장
# ============================
output_text = "\n".join(lines)
safe_name = task_info.get("사업명", "초안").replace(" ", "_")
output_path = os.path.join(output_dir, f"{safe_name}_초안.txt")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"\n결과 저장 완료: {output_path}")
input("\n엔터를 누르면 종료됩니다...")
