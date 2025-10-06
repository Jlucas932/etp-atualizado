#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import fitz  # PyMuPDF
import json
import os
import re
import unicodedata
from datetime import datetime

def normalize_text(text):
    """Normalize text to UTF-8 NFC and clean up artifacts."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'(\w)-(\s*\n\s*)', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_heading(span):
    """Heuristic to determine if a span is a heading."""
    return span['size'] > 12 or "bold" in span['font'].lower()

def extract_content(pdf_path):
    """Extracts structured content from a PDF."""
    doc = fitz.open(pdf_path)
    sections = []
    current_section = {
        "id": "0",
        "titulo": "Introduction",
        "paginas": [],
        "texto": ""
    }

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        text = normalize_text(span['text'])
                        if is_heading(span):
                            if current_section['texto'] or current_section['id'] == "0":
                                if current_section['id'] != "0" or current_section['texto']:
                                    sections.append(current_section)
                            current_section = {
                                "id": str(len(sections) + 1),
                                "titulo": text,
                                "paginas": [page_num + 1],
                                "texto": ""
                            }
                        else:
                            current_section['texto'] += text + " "
                            if page_num + 1 not in current_section['paginas']:
                                current_section['paginas'].append(page_num + 1)
    
    if current_section['texto']:
        sections.append(current_section)

    # Clean up page numbers
    for section in sections:
        section['paginas'] = sorted(list(set(section['paginas'])))

    doc.close()
    return sections

def convert_pdf_to_json(pdf_path, output_dir):
    """Convert a single PDF to a structured JSON file."""
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        doc.close()
    except Exception as e:
        print(f"Error opening PDF {pdf_path}: {e}")
        return

    title = normalize_text(metadata.get('title', os.path.basename(pdf_path).replace('.pdf', '')))
    doc_id = f"etp-{re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-'))[:50]}"

    sections = extract_content(pdf_path)

    json_data = {
        "doc_id": doc_id,
        "titulo": title,
        "data": datetime.now().strftime("%Y-%m-%d"),
        "secoes": sections,
        "metadados": {
            "origem": "pdf",
            "arquivo_original": os.path.basename(pdf_path)
        }
    }

    if not json_data['titulo'] or not json_data['secoes']:
        print(f"Warning: Could not extract title or sections from {pdf_path}")

    output_filename = os.path.join(output_dir, f"{doc_id}.json")
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully converted {pdf_path} to {output_filename}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert PDF documents to structured JSON files.")
    parser.add_argument("input_dir", help="Directory containing PDF files.")
    parser.add_argument("output_dir", help="Directory to save the JSON files.")
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    for filename in os.listdir(args.input_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(args.input_dir, filename)
            convert_pdf_to_json(pdf_path, args.output_dir)

