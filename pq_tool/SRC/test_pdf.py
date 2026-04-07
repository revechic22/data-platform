import subprocess
import sys

try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

import re

pdf_path = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\data\과업지시서\완주군 수도정비 기본계획(변경) 수립 용역 과업지시서.pdf"

# ① 전체 텍스트 추출
all_text = ""
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + "\n"

# ② 항목별 추출
result = {}

# 사업명
match = re.search(r'본\s*과업의\s*명칭은\s*["\u201c](.+?)["\u201d]', all_text)
if match:
    result["사업명"] = match.group(1).strip()

# 위치
match = re.search(r'위\s*치.*?전\s*북.*?완주군', all_text)
if match:
    result["위치"] = "전북특별자치도 완주군"

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
    r'수도법',
    r'수도법\s*시행령',
    r'수도법\s*시행규칙',
    r'상수도\s*설계기준',
    r'하수도\s*설계기준',
    r'시설물의\s*안전관리에\s*관한\s*특별법',
]
for pattern in law_patterns:
    if re.search(pattern, all_text):
        laws.append(re.search(pattern, all_text).group(0).strip())
if laws:
    result["관련법령"] = laws

# 과업범위 (제1편~제4편)
scope = []
scope_matches = re.findall(r'제\s*\d+\s*편\s*[:：]?\s*(.+?)(?:\n|$)', all_text)
for s in scope_matches:
    clean = s.strip()
    if clean and clean not in scope:
        scope.append(clean)
if scope:
    result["과업범위"] = scope

# ③ 결과 출력
print("=" * 60)
print("  과업지시서 파싱 결과")
print("=" * 60)

for key, value in result.items():
    if isinstance(value, list):
        print(f"\n[{key}]")
        for item in value:
            print(f"  - {item}")
    else:
        print(f"\n[{key}]")
        print(f"  {value}")

# 못 찾은 항목 표시
expected = ["사업명", "위치", "과업기간", "목표연도", "수행지침", "관련법령", "과업범위"]
missing = [item for item in expected if item not in result]
if missing:
    print(f"\n[추출 실패 항목]")
    for item in missing:
        print(f"  ※ {item} - 수동 확인 필요")

print("\n" + "=" * 60)
input("엔터를 누르면 종료됩니다...")
