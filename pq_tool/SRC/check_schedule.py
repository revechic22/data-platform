import subprocess
import sys
import os

try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

pdf_path = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\data\과업지시서\완주군 수도정비 기본계획(변경) 수립 용역 과업지시서.pdf"
output_dir = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\output"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "공정표_결과.txt")

lines = []

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[8]

    # 개월 칸 x좌표 범위 → 개월 매핑
    # 각 칸의 x0~x1 범위로 매핑 (칸 폭 약 21)
    month_columns = [
        (268.7, 289.8, 1, 2),
        (289.8, 310.9, 3, 4),
        (310.9, 331.9, 5, 6),
        (331.9, 353.0, 7, 8),
        (353.0, 374.0, 9, 10),
        (374.0, 395.1, 11, 12),
        (395.1, 416.2, 13, 14),
        (416.2, 437.2, 15, 16),
        (437.2, 458.3, 17, 18),
        (458.3, 479.3, 19, 20),
        (479.3, 500.4, 21, 22),
        (500.4, 521.5, 23, 24),
    ]

    def x_to_months(x0, x1):
        start_month = None
        end_month = None
        for col_x0, col_x1, m_start, m_end in month_columns:
            if x0 < col_x1 and x1 > col_x0:  # 겹치는 칸
                if start_month is None:
                    start_month = m_start
                end_month = m_end
        return start_month, end_month

    # 공종명 y좌표 매핑 (접근2에서 확인한 값, 허용 오차 ±10)
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

    # 사각형 추출 (기간 영역 내, fill=True)
    rects = [r for r in page.rects if r['x0'] >= 260 and r['x1'] <= 520]

    # y좌표별로 사각형 그룹핑
    y_groups = {}
    for r in rects:
        y_key = round(r['top'], 0)
        if y_key not in y_groups:
            y_groups[y_key] = []
        y_groups[y_key].append(r)

    # 결과 생성
    lines.append("=" * 60)
    lines.append("  과업지시서 공정표 추출 결과")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'구분':<8} {'공종명':<30} {'시작월':>6} {'종료월':>6} {'기간':>6}")
    lines.append("-" * 60)

    current_group = ""
    for y_key in sorted(y_groups.keys()):
        group_rects = y_groups[y_key]
        
        # 전체 x 범위
        min_x = min(r['x0'] for r in group_rects)
        max_x = max(r['x1'] for r in group_rects)
        
        start_m, _ = x_to_months(min_x, min_x + 1)
        _, end_m = x_to_months(max_x - 1, max_x)
        
        group, task_name = y_to_task(y_key)
        
        if group and group != current_group:
            lines.append("")
            current_group = group
        
        if task_name:
            duration = f"{end_m - start_m + 1}개월" if start_m and end_m else "?"
            lines.append(f"{group if group else ''::<8} {task_name:<30} {start_m if start_m else '?':>6} {end_m if end_m else '?':>6} {duration:>6}")
        else:
            lines.append(f"{'?':<8} {'(미매핑 y=' + str(y_key) + ')':<30} {start_m if start_m else '?':>6} {end_m if end_m else '?':>6}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("※ 각 공종의 기간은 이 범위 이하로만 설정할 것")
    lines.append("=" * 60)

output_text = "\n".join(lines)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_text)

print(output_text)
print(f"\n결과 저장 완료: {output_path}")
input("\n엔터를 누르면 종료됩니다...")
