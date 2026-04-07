import subprocess
import sys
import os

try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

import re

pdf_path = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\data\과업지시서\완주군 수도정비 기본계획(변경) 수립 용역 과업지시서.pdf"
output_dir = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\output"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "파싱결과.txt")

# ① 전체 텍스트 추출
all_text = ""
page_texts = []
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"
            page_texts.append(text)
        else:
            page_texts.append("")

# ② 항목별 추출
result = {}

# 사업명
match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', all_text)
if match:
    result["사업명"] = match.group(1).strip()

# 위치 - 계획구역에서 추출
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

# 과업 목적
purpose_match = re.search(
    r'2\.\s*과업의\s*목적\s*\n(.*?)3\.\s*과업의\s*개요',
    all_text,
    re.DOTALL
)
if purpose_match:
    purpose_raw = purpose_match.group(1).strip()
    purpose_raw = re.sub(r'[◦○●■◆▶]', '', purpose_raw)
    purpose_lines = [line.strip() for line in purpose_raw.split('\n') if line.strip()]
    result["과업목적(원문)"] = '\n'.join(purpose_lines)

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
    r'수도법시행규칙',
    r'수도법시행령',
    r'수도법',
    r'상수도\s*설계기준',
    r'하수도\s*설계기준',
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

# 조사항목
survey_items = []
survey_patterns = [
    (r'2\.1\s*자연적\s*조건', "자연적 조건에 관한 조사"),
    (r'2\.2\s*사회적\s*특성', "사회적 특성에 관한 조사"),
    (r'2\.3\s*관련계획', "관련계획에 대한 조사"),
    (r'2\.4\s*급수량\s*산정', "급수량 산정을 위한 기초조사"),
    (r'2\.5\s*제한\s*및\s*운반급수', "제한 및 운반급수 현황 조사"),
    (r'2\.6\s*상수도\s*현황', "상수도 현황"),
    (r'2\.7\s*GIS', "GIS 구축에 관한 조사"),
    (r'2\.8\s*수도시설\s*운영', "수도시설 운영에 대한 조사"),
]
for pattern, name in survey_patterns:
    if re.search(pattern, all_text):
        survey_items.append(name)
if survey_items:
    result["조사항목"] = survey_items

# ③ 결과 문자열 생성
lines = []
lines.append("=" * 60)
lines.append("  과업지시서 파싱 결과")
lines.append("=" * 60)

for key, value in result.items():
    if isinstance(value, list):
        lines.append(f"\n[{key}]")
        for item in value:
            lines.append(f"  - {item}")
    else:
        lines.append(f"\n[{key}]")
        lines.append(f"  {value}")

expected = ["사업명", "위치", "과업기간", "목표연도", "수행지침", "관련법령", "과업범위", "조사항목", "과업목적(원문)"]
missing = [item for item in expected if item not in result]
if missing:
    lines.append(f"\n[추출 실패 항목]")
    for item in missing:
        lines.append(f"  ※ {item} - 수동 확인 필요")

lines.append("\n" + "=" * 60)

output_text = "\n".join(lines)

# ④ 화면 출력 + 파일 저장
print(output_text)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_text)

print(f"\n결과 저장 완료: {output_path}")
input("엔터를 누르면 종료됩니다...")
