#!/usr/bin/env python3
"""
Script para processar ETPs da pasta raw/ e gerar arquivos JSONL na pasta parsed/

Formato esperado para cada linha do JSONL:
{
    "doc": "etp-001.docx",
    "section_type": "requisito",
    "objective_slug": "manutencao_computadores", 
    "content": "...",
    "citations": ["Lei 14.133/2021", "Decreto 10.024/2019"]  # opcional
}
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
import docx
from PyPDF2 import PdfReader

def extract_text_from_docx(file_path: str) -> str:
    """Extrai texto de arquivo DOCX"""
    try:
        doc = docx.Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text.strip())
        return "\n".join(text)
    except Exception as e:
        print(f"Erro ao processar {file_path}: {e}")
        return ""

def extract_text_from_pdf(file_path: str) -> str:
    """Extrai texto de arquivo PDF"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            text = []
            for page in pdf_reader.pages:
                text.append(page.extract_text())
        return "\n".join(text)
    except Exception as e:
        print(f"Erro ao processar {file_path}: {e}")
        return ""

def extract_text_from_txt(file_path: str) -> str:
    """Extrai texto de arquivo TXT"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Erro ao processar {file_path}: {e}")
        return ""

def extract_citations(text: str) -> List[str]:
    """Extrai citações de normas legais do texto"""
    citations = []
    
    # Padrões para identificar normas legais
    patterns = [
        r'Lei\s+(?:Federal\s+)?(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})',
        r'Decreto\s+(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})',
        r'Portaria\s+(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})',
        r'Resolução\s+(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})',
        r'Instrução\s+Normativa\s+(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})'
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            full_match = match.group(0)
            if full_match not in citations:
                citations.append(full_match)
    
    return citations

def identify_section_type(content: str) -> str:
    """Identifica o tipo de seção baseado no conteúdo"""
    content_lower = content.lower()
    
    if any(keyword in content_lower for keyword in ['requisito', 'especificação', 'critério']):
        return 'requisito'
    elif any(keyword in content_lower for keyword in ['lei', 'decreto', 'portaria', 'norma', 'regulament']):
        return 'norma_legal'
    elif any(keyword in content_lower for keyword in ['justificativa', 'fundamentação']):
        return 'justificativa'
    elif any(keyword in content_lower for keyword in ['objetivo', 'finalidade', 'propósito']):
        return 'objetivo'
    else:
        return 'geral'

def generate_objective_slug(filename: str, content: str) -> str:
    """Gera slug do objetivo baseado no nome do arquivo e conteúdo"""
    # Extrair base do nome do arquivo
    base_name = Path(filename).stem.lower()
    
    # Palavras-chave comuns em ETPs
    keywords = {
        'manutencao': ['manutenção', 'manut', 'conservação'],
        'computadores': ['computador', 'informatica', 'ti', 'tecnologia'],
        'limpeza': ['limpeza', 'higienização', 'sanitização'],
        'seguranca': ['segurança', 'vigilância', 'monitoramento'],
        'transporte': ['transporte', 'veículo', 'condução'],
        'consultoria': ['consultoria', 'assessoria', 'especializada'],
        'software': ['software', 'sistema', 'aplicativo'],
        'hardware': ['hardware', 'equipamento', 'dispositivo']
    }
    
    # Verificar palavras-chave no conteúdo
    content_lower = content.lower()
    for slug, terms in keywords.items():
        if any(term in content_lower for term in terms):
            return slug
    
    # Fallback: usar base do nome do arquivo
    return re.sub(r'[^a-z0-9_]', '_', base_name)

def parse_etp_document(file_path: str) -> List[Dict]:
    """Processa um documento ETP e retorna lista de seções"""
    filename = os.path.basename(file_path)
    file_ext = Path(file_path).suffix.lower()
    
    # Extrair texto baseado na extensão
    if file_ext == '.docx':
        text = extract_text_from_docx(file_path)
    elif file_ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif file_ext == '.txt':
        text = extract_text_from_txt(file_path)
    else:
        print(f"Formato não suportado: {file_ext}")
        return []
    
    if not text.strip():
        print(f"Nenhum texto extraído de {filename}")
        return []
    
    # Dividir em seções (por parágrafo ou seção)
    sections = []
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    objective_slug = generate_objective_slug(filename, text)
    
    for paragraph in paragraphs:
        if len(paragraph) < 50:  # Ignorar parágrafos muito curtos
            continue
            
        section_type = identify_section_type(paragraph)
        citations = extract_citations(paragraph)
        
        section_data = {
            "doc": filename,
            "section_type": section_type,
            "objective_slug": objective_slug,
            "content": paragraph
        }
        
        if citations:
            section_data["citations"] = citations
            
        sections.append(section_data)
    
    return sections

def process_all_etps():
    """Processa todos os ETPs da pasta raw/ e gera arquivos JSONL em parsed/"""
    raw_dir = Path("knowledge/etps/raw")
    parsed_dir = Path("knowledge/etps/parsed")
    
    if not raw_dir.exists():
        print("Pasta raw/ não encontrada. Criando...")
        raw_dir.mkdir(parents=True, exist_ok=True)
        print("Coloque seus arquivos ETP na pasta knowledge/etps/raw/")
        return
    
    parsed_dir.mkdir(parents=True, exist_ok=True)
    
    # Limpar pasta parsed/
    for file in parsed_dir.glob("*.jsonl"):
        file.unlink()
    
    processed_count = 0
    total_sections = 0
    
    # Processar arquivos na pasta raw/
    for file_path in raw_dir.glob("*"):
        if file_path.is_file() and file_path.suffix.lower() in ['.docx', '.pdf', '.txt']:
            print(f"Processando: {file_path.name}")
            
            sections = parse_etp_document(str(file_path))
            if sections:
                # Gerar arquivo JSONL
                output_file = parsed_dir / f"{file_path.stem}.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for section in sections:
                        f.write(json.dumps(section, ensure_ascii=False) + '\n')
                
                processed_count += 1
                total_sections += len(sections)
                print(f"  ✓ {len(sections)} seções extraídas -> {output_file.name}")
            else:
                print(f"  ⚠️ Nenhuma seção extraída de {file_path.name}")
    
    print(f"\n✅ Processamento concluído:")
    print(f"   - {processed_count} documentos processados")
    print(f"   - {total_sections} seções extraídas")
    print(f"   - Arquivos JSONL salvos em: {parsed_dir}")

if __name__ == "__main__":
    process_all_etps()