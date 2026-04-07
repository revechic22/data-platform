import subprocess
import sys
import os
import re

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
qbs_dir = os.path.join(base_dir, r"data\참고QBS\상수도")
output_dir = os.path.join(base_dir, "output")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "조사항목_비교.txt")

# ============================
# 조사항목 추출 함수
# ============================
survey_patterns = [
    (r'자연적\s*조건', "자연적 조건에 관한 조사"),
    (r'사회적\s*특성', "사회적 특성에 관한 조사"),
    (r'관련계획', "관련계획에 대한 조사"),
    (r'급수량\s*산정', "급수량 산정을 위한 기초조사"),
    (r'제한\s*및\s*운반급수', "제한 및 운반급수 현황 조사"),
    (r'상수도\s*현황', "상수도 현황"),
    (r'GIS', "GIS 구축에 관한 조사"),
    (r'수도시설\s*운영', "수도시설 운영에 대한 조사"),
    (r'하수도\s*현황', "하수도 현황"),
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

def extract_survey_items(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        return [], str(e)
    
    found = []
    for pattern, name in survey_patterns:
        if re.search(pattern, text):
            if name not in found:
                found.append(name)
    return found, None

# ============================
# 과업지시서 조사항목 추출
# ============================
task_items, task_err = extract_survey_items(task_pdf)

# ============================
# 참고QBS 전부 읽기
# ============================
qbs_results = {}
pdf_files = [f for f in os.listdir(qbs_dir) if f.lower().endswith('.pdf')]

for pdf_file in pdf_files:
    pdf_path = os.path.join(qbs_dir, pdf_file)
    items, err = extract_survey_items(pdf_path)
    short_name = pdf_file.replace('.pdf', '').replace('.PDF', '')
    if len(short_name) > 30:
        short_name = short_name[:30] + "..."
    qbs_results[short_name] = {"items": items, "error": err}

# ============================
# 비교 결과 생성
# ============================
lines = []
lines.append("=" * 70)
lines.append("  조사항목 비교 (과업지시서 vs 참고QBS)")
lines.append("=" * 70)

# 과업지시서 항목
lines.append("")
lines.append(f"  ▶ 과업지시서: 완주군 수도정비 기본계획(변경)")
lines.append(f"    항목 {len(task_items)}개:")
for item in task_items:
    lines.append(f"      - {item}")

# 각 QBS 항목
for name, data in qbs_results.items():
    lines.append("")
    lines.append(f"  ▶ 참고QBS: {name}")
    if data["error"]:
        lines.append(f"    ※ 읽기 실패: {data['error']}")
        continue
    lines.append(f"    항목 {len(data['items'])}개:")
    for item in data["items"]:
        lines.append(f"      - {item}")

# 비교 매트릭스
lines.append("")
lines.append("=" * 70)
lines.append("  비교 매트릭스")
lines.append("=" * 70)
lines.append("")

# 모든 항목 수집
all_items = list(task_items)
for data in qbs_results.values():
    for item in data["items"]:
        if item not in all_items:
            all_items.append(item)

# 헤더
header = f"  {'조사항목':<25} {'과업지시서':>10}"
for name in qbs_results.keys():
    short = name[:8] + ".." if len(name) > 10 else name
    header += f" {short:>10}"
lines.append(header)
lines.append("  " + "-" * (25 + 10 + 12 * len(qbs_results)))

for item in all_items:
    row = f"  {item:<25}"
    
    in_task = "●" if item in task_items else "—"
    row += f" {in_task:>10}"
    
    for name, data in qbs_results.items():
        in_qbs = "●" if item in data["items"] else "—"
        row += f" {in_qbs:>10}"
    
    lines.append(row)

# 차이점 요약
lines.append("")
lines.append("=" * 70)
lines.append("  차이점 요약")
lines.append("=" * 70)

# 과업지시서에만 있는 항목
for name, data in qbs_results.items():
    only_task = [i for i in task_items if i not in data["items"]]
    only_qbs = [i for i in data["items"] if i not in task_items]
    
    if only_task or only_qbs:
        lines.append(f"\n  vs {name}:")
        if only_task:
            lines.append(f"    과업지시서에만 있음:")
            for item in only_task:
                lines.append(f"      + {item}")
        if only_qbs:
            lines.append(f"    참고QBS에만 있음 (추가 검토):")
            for item in only_qbs:
                lines.append(f"      → {item}")

lines.append("")
lines.append("=" * 70)

output_text = "\n".join(lines)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_text)

print(output_text)
print(f"\n결과 저장 완료: {output_path}")
input("\n엔터를 누르면 종료됩니다...")
