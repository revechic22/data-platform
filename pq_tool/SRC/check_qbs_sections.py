import re
import fitz  # PyMuPDF

# 섹션 번호와 대표 키워드 (순서 보장용)
SECTION_DEFS = [
    ("1.1", ["당해 사업의 내용", "당해사업의 내용", "당해 사업"]),
    ("1.2", ["유사용역 수행실적", "유사용역수행실적", "유사용역"]),
    ("1.3", ["기술인력 보유현황", "기술인력보유현황", "기술인력"]),
    ("2.1", ["사업수행 기본방침", "사업수행기본방침", "기본방침"]),
    ("2.2", ["과업수행 조직", "과업수행조직", "수행조직"]),
    ("2.3", ["과업수행 일정", "과업수행일정", "수행일정", "세부공정"]),
    ("2.4", ["하자 관리", "하자관리", "품질 관리", "품질관리", "하자 및 품질"]),
]

def detect_section_from_page_text(text, top_n_chars=300):
    """
    페이지 텍스트의 앞부분(top_n_chars)에서 섹션 번호를 감지.
    '1.1' 같은 번호가 텍스트 앞쪽에 있고, 키워드도 매칭되면 해당 섹션으로 판정.
    """
    header = text[:top_n_chars]
    # 공백/줄바꿈 정규화
    header_clean = re.sub(r'\s+', ' ', header).strip()
    
    for sec_num, keywords in SECTION_DEFS:
        # 패턴: 섹션 번호가 헤더에 존재 (앞뒤 공백/마침표/괄호 등 허용)
        # 예: "1.1 당해 사업의 내용" 또는 "1.1당해 사업의 내용"
        num_pattern = re.escape(sec_num)
        if re.search(rf'(?:^|\s|\.|\(|\)|\n){num_pattern}(?:\s|\.|\(|:|)', header_clean):
            # 키워드도 있는지 확인 (오탐 방지)
            for kw in keywords:
                kw_clean = re.sub(r'\s+', '', kw)
                header_no_space = re.sub(r'\s+', '', header_clean)
                if kw_clean in header_no_space:
                    return sec_num
        
        # 번호 없이 키워드만으로도 판정 (일부 QBS는 번호 없이 시작)
        # -> 이건 오탐 위험이 높으므로 비활성화. 필요 시 활성화.
    
    return None


def extract_qbs_sections(pdf_path, skip_first_n_pages=1):
    """
    QBS PDF에서 1.1~2.4 섹션을 페이지 단위로 분리.
    
    Args:
        pdf_path: QBS PDF 파일 경로
        skip_first_n_pages: 앞에서 스킵할 페이지 수 (목차 등). 기본 1.
    
    Returns:
        dict: {"1.1": "텍스트...", "1.2": "텍스트...", ...}
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # 1단계: 각 페이지별 텍스트 추출 + 섹션 감지
    page_data = []  # [(page_idx, text, detected_section)]
    for i in range(total_pages):
        text = doc[i].get_text()
        if i < skip_first_n_pages:
            page_data.append((i, text, "__SKIP__"))
            continue
        detected = detect_section_from_page_text(text)
        page_data.append((i, text, detected))
    
    doc.close()
    
    # 2단계: 섹션별 페이지 텍스트 합치기
    # 섹션이 감지된 페이지부터 다음 섹션이 감지되는 페이지 직전까지가 해당 섹션
    sections = {}
    current_section = None
    current_texts = []
    
    for i, text, detected in page_data:
        if detected == "__SKIP__":
            continue
        
        if detected is not None:
            # 이전 섹션 저장
            if current_section is not None:
                sections[current_section] = "\n".join(current_texts)
            # 새 섹션 시작
            current_section = detected
            current_texts = [text]
        else:
            # 섹션 헤더가 없는 페이지 -> 현재 섹션에 이어붙이기
            if current_section is not None:
                current_texts.append(text)
            # else: 첫 섹션 전의 페이지는 무시
    
    # 마지막 섹션 저장
    if current_section is not None:
        sections[current_section] = "\n".join(current_texts)
    
    # 3단계: 빠진 섹션 체크
    all_section_nums = [s[0] for s in SECTION_DEFS]
    for sn in all_section_nums:
        if sn not in sections:
            sections[sn] = "[해당 섹션 없음]"
    
    return sections
