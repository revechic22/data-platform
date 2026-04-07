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
# 경로 설정
# ============================
base_dir = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool"
task_pdf = os.path.join(base_dir, r"data\과업지시서\완주군 수도정비 기본계획(변경) 수립 용역 과업지시서.pdf")
eval_pdf = os.path.join(base_dir, r"data\평가기준서\완주군 수도정비 기본계획(변경) 수립 용역 사업수행능력평가기준 및 작성안내서.pdf")
qbs_dir = os.path.join(base_dir, r"data\참고QBS\상수도")
output_dir = os.path.join(base_dir, "output")
os.makedirs(output_dir, exist_ok=True)

lines = []

# ============================================================
# PART 1: 과업지시서 파싱
# ============================================================
all_text = ""
page_texts = []
with pdfplumber.open(task_pdf) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"
            page_texts.append(text)
        else:
            page_texts.append("")

result = {}

# 사업명
match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', all_text)
if match:
    result["사업명"] = match.group(1).strip()

# 위치
for pattern in [
    r'(완주군)\s*전체\s*행정구역',
    r'위\s*치\s*[:：]?\s*(전\S*도\s*\S+[군시구])',
    r'(전북특별자치도\s*완주군)',
]:
    match = re.search(pattern, all_text)
    if match:
        loc = match.group(1).strip()
        if "전" not in loc:
            loc = "전북특별자치도 " + loc
        result["위치"] = loc
        break

# 과업목적
purpose_match = re.search(
    r'2\.\s*과업의\s*목적\s*\n(.*?)3\.\s*과업의\s*개요',
    all_text, re.DOTALL
)
if purpose_match:
    purpose_raw = purpose_match.group(1).strip()
    purpose_raw = re.sub(r'[◦○●■◆▶]', '', purpose_raw)
    purpose_lines = [line.strip() for line in purpose_raw.split('\n') if line.strip()]
    result["과업목적"] = '\n'.join(purpose_lines)

# 과업기간
match = re.search(r'과업기간은?\s*착수일로부터\s*(\d+)\s*개월', all_text)
if match:
    result["과업기간"] = f"착수일로부터 {match.group(1)}개월"

# 목표연도
match = re.search(r'목표연도\s*[:：]?\s*(\d{4})\s*년', all_text)
if match:
    result["목표연도"] = f"{match.group(1)}년"

# 수행지침
match = re.search(r'수도정비기본계획\s*수립지침\s*\(.*?\)', all_text)
if match:
    result["수행지침"] = match.group(0).strip()

# 관련법령
laws = []
law_patterns = [
    r'수도법시행규칙', r'수도법시행령', r'수도법',
    r'상수도\s*설계기준', r'하수도\s*설계기준',
    r'시설물의\s*안전관리에\s*관한\s*특별법',
]
found_laws = set()
for pattern in law_patterns:
    match = re.search(pattern, all_text)
    if match:
        law_name = match.group(0).strip()
        if law_name not in found_laws:
            laws.append(law_name)
            found_laws.add(law_name)
if laws:
    result["관련법령"] = laws

# 과업범위
scope = []
scope_matches = re.findall(r'[<＜]\s*제\s*(\d+)\s*편\s*(.*?)\s*[>＞]', all_text)
seen = set()
for num, name in scope_matches:
    clean_name = name.strip()
    key = f"제{num}편"
    if key not in seen and clean_name:
        scope.append(f"{key} {clean_name}")
        seen.add(key)
if scope:
    result["과업범위"] = scope

# 조사항목 (기본)
survey_base_patterns = [
    (r'2\.1\s*자연적\s*조건', "자연적 조건에 관한 조사"),
    (r'2\.2\s*사회적\s*특성', "사회적 특성에 관한 조사"),
    (r'2\.3\s*관련계획', "관련계획에 대한 조사"),
    (r'2\.4\s*급수량\s*산정', "급수량 산정을 위한 기초조사"),
    (r'2\.5\s*제한\s*및\s*운반급수', "제한 및 운반급수 현황 조사"),
    (r'2\.6\s*상수도\s*현황', "상수도 현황"),
    (r'2\.7\s*GIS', "GIS 구축에 관한 조사"),
    (r'2\.8\s*수도시설\s*운영', "수도시설 운영에 대한 조사"),
]
survey_items = []
for pattern, name in survey_base_patterns:
    if re.search(pattern, all_text):
        survey_items.append(name)
if survey_items:
    result["조사항목"] = survey_items

# ============================================================
# PART 2: 공정표 추출 (도형 기반)
# ============================================================
schedule_data = []
with pdfplumber.open(task_pdf) as pdf:
    if len(pdf.pages) >= 9:
        page = pdf.pages[8]
        month_columns = [
            (268.7, 289.8, 1, 2), (289.8, 310.9, 3, 4),
            (310.9, 331.9, 5, 6), (331.9, 353.0, 7, 8),
            (353.0, 374.0, 9, 10), (374.0, 395.1, 11, 12),
            (395.1, 416.2, 13, 14), (416.2, 437.2, 15, 16),
            (437.2, 458.3, 17, 18), (458.3, 479.3, 19, 20),
            (479.3, 500.4, 21, 22), (500.4, 521.5, 23, 24),
        ]

        def x_to_months(x0, x1):
            start_month = None
            end_month = None
            for col_x0, col_x1, m_start, m_end in month_columns:
                if x0 < col_x1 and x1 > col_x0:
                    if start_month is None:
                        start_month = m_start
                    end_month = m_end
            return start_month, end_month

        task_y_map = [
            (191, "제1편", "1. 총설"),
            (213, "제1편", "2. 기초조사"),
            (234, "제1편", "3. 기본사항의결정"),
            (255, "제1편", "4. 시설확충계획"),
            (277, "제1편", "5. 시설개량계획"),
            (298, "제1편", "6. 상수도 수질관리계획"),
            (319, "제1편", "7. 상수도시설 유지관리계획"),
            (341, "제1편", "8. 상수도시설 정보화계획"),
            (380, "제2편", "1. 상수도 수요관리 목표설정"),
            (401, "제2편", "2. 상수도 수요관리 사업계획"),
            (422, "제2편", "3. 상수도 수요관리 재정계획"),
            (461, "제3편", "1. 생산시설의 안정화계획"),
            (482, "제3편", "2. 공급시설의 안정화계획"),
            (504, "제3편", "3. 수도시설 비상연계계획"),
            (525, "제3편", "4. 재해 및 위기관리 대책"),
            (546, "제3편", "5. 상수도시설 안정화 재정계획"),
            (585, "제4편", "1. 사업시행 및 재정계획"),
            (607, "제4편", "2. 수도사업 경영 개선계획"),
            (628, "", "Ⅴ. 성과품 작성 및 납품"),
        ]

        def y_to_task(y):
            for task_y, group, name in task_y_map:
                if abs(y - task_y) < 10:
                    return group, name
            return None, None

        rects = [r for r in page.rects if r['x0'] >= 260 and r['x1'] <= 520]
        y_groups = {}
        for r in rects:
            y_key = round(r['top'], 0)
            if y_key not in y_groups:
                y_groups[y_key] = []
            y_groups[y_key].append(r)

        for y_key in sorted(y_groups.keys()):
            group_rects = y_groups[y_key]
            min_x = min(r['x0'] for r in group_rects)
            max_x = max(r['x1'] for r in group_rects)
            start_m, _ = x_to_months(min_x, min_x + 1)
            _, end_m = x_to_months(max_x - 1, max_x)
            group, task_name = y_to_task(y_key)
            if task_name and start_m and end_m:
                x_sorted = sorted(group_rects, key=lambda r: r['x0'])
                gap = False
                for i in range(len(x_sorted) - 1):
                    if x_sorted[i+1]['x0'] - x_sorted[i]['x1'] > 25:
                        gap = True
                        break
                warning = " ※ 불연속 확인" if gap else ""
                schedule_data.append((group, task_name, start_m, end_m, end_m - start_m + 1, warning))

# ============================================================
# PART 3: 평가기준서 파싱
# ============================================================
eval_text = ""
with pdfplumber.open(eval_pdf) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            eval_text += text + "\n"

fields = []
field_patterns = [
    r'상하수도', r'구조', r'토질\s*[·‧]\s*지질',
    r'수자원개발', r'환경\s*\(\s*수질관리\s*\)', r'환경\s*\(\s*수질\s*\)',
]
found_fields = set()
for pattern in field_patterns:
    match = re.search(pattern, eval_text)
    if match:
        field_name = match.group(0).strip()
        if field_name not in found_fields:
            fields.append(field_name)
            found_fields.add(field_name)

client_match = re.search(r'(완주군\s*\S*사업소)', eval_text)
client = client_match.group(1).strip() if client_match else ""

# ============================================================
# PART 4: 참고QBS 비교
# ============================================================
survey_compare_patterns = [
    (r'자연적\s*조건', "자연적 조건에 관한 조사"),
    (r'사회적\s*특성', "사회적 특성에 관한 조사"),
    (r'관련계획', "관련계획에 대한 조사"),
    (r'급수량\s*산정', "급수량 산정을 위한 기초조사"),
    (r'제한\s*및\s*운반급수', "제한 및 운반급수 현황 조사"),
    (r'상수도\s*현황', "상수도 현황"),
    (r'GIS', "GIS 구축에 관한 조사"),
    (r'수도시설\s*운영', "수도시설 운영에 대한 조사"),
    (r'온실가스', "온실가스 저감"),
    (r'수질관리', "수질관리"),
    (r'유지관리', "유지관리"),
    (r'정보화', "정보화 계획"),
    (r'내진', "내진대책"),
    (r'비상연계', "비상연계 계획"),
    (r'수요관리', "수요관리"),
    (r'마을상수도', "마을상수도/소규모급수시설"),
    (r'소규모\s*급수', "마을상수도/소규모급수시설"),
    (r'블록시스템', "블록시스템"),
    (r'관망', "관망 관련"),
]

def extract_survey_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        return []
    found = []
    for pattern, name in survey_compare_patterns:
        if re.search(pattern, text):
            if name not in found:
                found.append(name)
    return found

# 과업지시서 확장 조사항목 (비교용)
task_survey_full = extract_survey_from_pdf(task_pdf)

# 참고QBS 전부 읽기
qbs_results = {}
if os.path.exists(qbs_dir):
    pdf_files = [f for f in os.listdir(qbs_dir) if f.lower().endswith('.pdf')]
    for pdf_file in pdf_files:
        pdf_path = os.path.join(qbs_dir, pdf_file)
        items = extract_survey_from_pdf(pdf_path)
        short_name = pdf_file.replace('.pdf', '').replace('.PDF', '')
        if len(short_name) > 25:
            short_name = short_name[:25] + ".."
        qbs_results[short_name] = items

# ============================================================
# PART 5: 작업 패키지 출력
# ============================================================
now = datetime.now().strftime("%Y-%m-%d %H:%M")

lines.append("╔" + "═" * 58 + "╗")
lines.append("║  PQ 작업 패키지 (통합)                                   ║")
lines.append("║  " + f"생성일시: {now}" + " " * (56 - len(f"생성일시: {now}")) + "║")
lines.append("╚" + "═" * 58 + "╝")

# --- 치환 항목 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [치환 항목] — 2.3, 2.4에서 찾아바꾸기 할 값")
lines.append("=" * 60)
lines.append(f"  사업명  : {result.get('사업명', '?')}")
lines.append(f"  위  치  : {result.get('위치', '?')}")
lines.append(f"  발주처  : {client if client else '? (수동 확인)'}")
lines.append(f"  과업기간: {result.get('과업기간', '?')}")
lines.append(f"  목표연도: {result.get('목표연도', '?')}")
if fields:
    lines.append(f"  분야    : {', '.join(fields)}")

# --- 1.1 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [1.1] 사업의 특성 / 내용 및 범위")
lines.append("=" * 60)
lines.append("")
lines.append("  ▶ 과업 목적 (원문 — 3줄 요약용):")
if result.get("과업목적"):
    for line in result["과업목적"].split('\n'):
        lines.append(f"    {line}")
lines.append("")
lines.append("  ▶ 과업범위:")
if result.get("과업범위"):
    for item in result["과업범위"]:
        lines.append(f"    - {item}")
lines.append("")
lines.append(f"  ▶ 수행지침: {result.get('수행지침', '?')}")

# --- 1.3 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [1.3] 제안사항 — 관련법령 검토 참고")
lines.append("=" * 60)
if result.get("관련법령"):
    for law in result["관련법령"]:
        lines.append(f"    - {law}")

# --- 2.1 조사항목 + 비교 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.1] 업무수행범위 — 조사항목")
lines.append("=" * 60)
lines.append("")
lines.append("  ▶ 과업지시서 기본 조사항목:")
if result.get("조사항목"):
    for item in result["조사항목"]:
        lines.append(f"    - {item}")

lines.append("")
lines.append("  ▶ 분야 구성 (평가기준서 기준):")
if fields:
    for f in fields:
        lines.append(f"    - {f}")

# 비교 매트릭스
if qbs_results:
    lines.append("")
    lines.append("  ▶ 조사항목 비교 매트릭스:")
    lines.append("")

    all_items = list(task_survey_full)
    for items in qbs_results.values():
        for item in items:
            if item not in all_items:
                all_items.append(item)

    header = f"    {'항목':<25} {'과업':>4}"
    for name in qbs_results.keys():
        short = name[:6] + ".."
        header += f" {short:>8}"
    lines.append(header)
    lines.append("    " + "-" * (25 + 4 + 10 * len(qbs_results)))

    for item in all_items:
        row = f"    {item:<25}"
        row += f" {'●' if item in task_survey_full else '—':>4}"
        for name, items in qbs_results.items():
            row += f" {'●' if item in items else '—':>8}"
        lines.append(row)

    # 차이점 요약
    lines.append("")
    lines.append("  ▶ 차이점 요약:")
    for name, items in qbs_results.items():
        only_task = [i for i in task_survey_full if i not in items]
        only_qbs = [i for i in items if i not in task_survey_full]
        if only_task or only_qbs:
            lines.append(f"")
            lines.append(f"    vs {name}:")
            if only_task:
                for item in only_task:
                    lines.append(f"      [과업만] {item}")
            if only_qbs:
                for item in only_qbs:
                    lines.append(f"      [QBS만] {item} ← 검토 필요")

# --- 2.2 공정표 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.2] 작업계획서 — 과업지시서 공정표")
lines.append("=" * 60)
lines.append(f"  ※ 전체 과업기간: {result.get('과업기간', '?')}")
lines.append(f"  ※ 각 공종은 아래 범위 이하로 설정할 것")
lines.append("")
lines.append(f"  {'구분':<8} {'공종명':<28} {'시작':>4} {'종료':>4} {'기간':>6} {'비고'}")
lines.append("  " + "-" * 58)

current_group = ""
for group, task_name, start_m, end_m, duration, warning in schedule_data:
    if group and group != current_group:
        lines.append("")
        current_group = group
    lines.append(f"  {group:<8} {task_name:<28} {start_m:>4} {end_m:>4} {duration:>4}개월{warning}")

# --- 2.3 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.3] 품질보증체계 — 치환 항목")
lines.append("=" * 60)
lines.append(f"  과업명 → {result.get('사업명', '?')}")
lines.append(f"  발주처 → {client if client else '?'}")

# --- 2.4 ---
lines.append("")
lines.append("=" * 60)
lines.append("  [2.4] 전문가 활용계획 — 치환 항목")
lines.append("=" * 60)
lines.append(f"  발주처 → {client if client else '?'}")
lines.append("  분야별 자문내용:")
if fields:
    for f in fields:
        lines.append(f"    - {f}: (샘플에서 가져오기)")

lines.append("")
lines.append("=" * 60)
lines.append("  END")
lines.append("=" * 60)

# ============================================================
# 저장
# ============================================================
output_text = "\n".join(lines)
safe_name = result.get("사업명", "작업패키지").replace(" ", "_")
output_filename = f"{safe_name}_작업패키지.txt"
output_path = os.path.join(output_dir, output_filename)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_text)

print(output_text)
print(f"\n결과 저장 완료: {output_path}")
input("\n엔터를 누르면 종료됩니다...")
