import subprocess
import sys

try:
    import pdfplumber
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

pdf_path = r"V:\상하수도부\신승민\AI 활용 업무 스마트화 단계별 수행방안\pq_tool\data\과업지시서\완주군 수도정비 기본계획(변경) 수립 용역 과업지시서.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # 3페이지 (과업 개요가 보통 여기에 있음)
    for page_num in [2, 3, 4]:  # 0부터 시작이라 실제 3, 4, 5페이지
        print(f"\n{'='*60}")
        print(f"  {page_num + 1}페이지 원문")
        print(f"{'='*60}")
        text = pdf.pages[page_num].extract_text()
        if text:
            print(text)
        else:
            print("(텍스트 없음)")

input("\n엔터를 누르면 종료됩니다...")
