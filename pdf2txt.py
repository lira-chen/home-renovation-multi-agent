# -*- coding: utf-8 -*-
"""
PDF 转文字：把装修国标 PDF 转成 sample.txt 能用的纯文本。

用法：
    python pdf2txt.py  国标.pdf  国标.txt
"""
import sys
import pdfplumber


def pdf_to_text(pdf_path, out_path):
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    full = "\n".join(text_parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"转换完成：共 {len(full)} 字 -> {out_path}")


if __name__ == "__main__":
    pdf_to_text(sys.argv[1], sys.argv[2])
