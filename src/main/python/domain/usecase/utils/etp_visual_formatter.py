import os
from datetime import datetime
from typing import Dict, Optional
import base64

class EtpVisualFormatter:
    """Formatador visual para ETP baseado no modelo da concorrência"""
    
    def __init__(self):
        self.css_styles = self._get_etp_styles()
        self.html_template = self._get_html_template()
    
    def format_etp_with_borders(self, etp_content: str, session_data: Dict = None) -> str:
        """Formata ETP com bordas e visual profissional baseado no modelo da concorrência"""
        
        # Extrair informações da sessão
        answers = session_data.get('answers', {}) if session_data else {}
        
        # Processar conteúdo para HTML
        html_content = self._convert_to_html(etp_content)
        
        # Gerar cabeçalho
        header_html = self._generate_header(answers)
        
        # Montar documento final
        formatted_html = self.html_template.format(
            css_styles=self.css_styles,
            header_content=header_html,
            main_content=html_content,
            footer_content=self._generate_footer()
        )
        
        return formatted_html
    
    def _get_etp_styles(self) -> str:
        """Retorna CSS baseado no modelo da concorrência"""
        return """
        <style>
        @page {
            margin: 2cm;
            size: A4;
        }
        
        body {
            font-family: 'Times New Roman', serif;
            font-size: 12pt;
            line-height: 1.4;
            color: #000;
            margin: 0;
            padding: 0;
            background: white;
        }
        
        .documento-etp {
            border: 2px solid #333;
            margin: 20px auto;
            padding: 30px;
            max-width: 210mm;
            min-height: 297mm;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        
        .cabecalho {
            text-align: center;
            border-bottom: 1px solid #ccc;
            padding-bottom: 20px;
            margin-bottom: 30px;
            position: relative;
        }
        
        .logo-governo {
            width: 60px;
            height: 60px;
            margin: 0 auto 10px;
        }
        
        .orgao-info {
            font-size: 11pt;
            font-weight: bold;
            line-height: 1.2;
            margin-bottom: 15px;
        }
        
        .protocolo-box {
            position: absolute;
            top: 0;
            right: 0;
            border: 1px solid #333;
            padding: 8px;
            font-size: 9pt;
            width: 120px;
            text-align: left;
        }
        
        .titulo-principal {
            background-color: #1f4e79;
            color: white;
            padding: 15px;
            margin: 20px 0;
            font-size: 16pt;
            font-weight: bold;
            text-align: center;
        }
        
        .introducao-box {
            border: 1px solid #1f4e79;
            padding: 15px;
            margin: 20px 0;
            background-color: #f8f9fa;
        }
        
        .secao-titulo {
            background-color: #1f4e79;
            color: white;
            padding: 12px 18px;
            margin: 30px 0 20px 0;
            font-size: 14pt;
            font-weight: bold;
            border-left: 4px solid #0d2a4a;
        }
        
        .subsecao-titulo {
            font-weight: bold;
            margin: 15px 0 8px 0;
            font-size: 12pt;
        }
        
        .paragrafo {
            text-align: justify;
            margin-bottom: 16px;
            text-indent: 1.5em;
            line-height: 1.6;
            padding: 4px 0;
            font-size: 12pt;
        }
        
        .lista-item {
            margin: 8px 0;
            padding-left: 20px;
        }
        
        .lista-item::before {
            content: "• ";
            font-weight: bold;
            margin-right: 8px;
        }
        
        .tabela {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 11pt;
        }
        
        .tabela th {
            background-color: #1f4e79;
            color: white;
            padding: 10px;
            text-align: center;
            border: 1px solid #333;
            font-weight: bold;
        }
        
        .tabela td {
            padding: 8px;
            border: 1px solid #333;
            text-align: center;
        }
        
        .tabela tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .valor-destaque {
            font-weight: bold;
            background-color: #e8f4f8;
        }
        
        .rodape {
            border-top: 1px solid #ccc;
            padding-top: 15px;
            margin-top: 30px;
            text-align: center;
            font-size: 10pt;
            color: #666;
        }
        
        .numero-pagina {
            text-align: center;
            margin-top: 20px;
            font-size: 10pt;
        }
        
        @media print {
            .documento-etp {
                border: 2px solid #333;
                margin: 0;
                box-shadow: none;
            }
            
            body {
                margin: 0;
            }
        }
        
        /* Responsividade para telas menores */
        @media screen and (max-width: 768px) {
            .documento-etp {
                margin: 10px;
                padding: 20px;
            }
            
            .protocolo-box {
                position: static;
                margin: 10px auto;
                width: auto;
                text-align: center;
            }
            
            .tabela {
                font-size: 10pt;
            }
            
            .tabela th,
            .tabela td {
                padding: 6px;
            }
        }
        </style>
        """
    
    def _get_html_template(self) -> str:
        """Retorna template HTML base"""
        return """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Estudo Técnico Preliminar</title>
            {css_styles}
        </head>
        <body>
            <div class="documento-etp">
                {header_content}
                {main_content}
                {footer_content}
            </div>
        </body>
        </html>
        """
    
    def _generate_header(self, answers: Dict) -> str:
        """Gera cabeçalho baseado no modelo da concorrência"""
        return f"""
        <div class="cabecalho">
            <div class="protocolo-box">
                <strong>SEAD/SEGOV</strong><br>
                Nº: ___________<br>
                Proc.: ________<br>
                Rub.: _________
            </div>
            
            <div class="logo-governo">
                🏛️
            </div>
            
            <div class="orgao-info">
                Governo do Estado<br>
                SECRETARIA EXECUTIVA DE COMUNICAÇÃO<br>
                SECRETARIA DO ESTADO DE GOVERNO E GESTÃO ESTRATÉGICA
            </div>
        </div>
        
        <div class="titulo-principal">
            ESTUDO TÉCNICO PRELIMINAR
        </div>
        
        <div class="introducao-box">
            <p><strong>O presente documento caracteriza a primeira etapa da fase de planejamento e apresenta os devidos estudos para a contratação de solução que melhor atenderá à necessidade descrita abaixo.</strong></p>
            
            <p><strong>O objetivo principal é identificar a necessidade e identificar a melhor solução para supri-la, em observância às normas vigentes e aos princípios que regem a Administração Pública.</strong></p>
        </div>
        """
    
    def _generate_footer(self) -> str:
        """Gera rodapé do documento"""
        return f"""
        <div class="rodape">
            <hr>
            <p><strong>Documento elaborado em conformidade com a Lei nº 14.133/2021</strong></p>
            <p>Data de elaboração: {datetime.now().strftime('%d/%m/%Y')}</p>
        </div>
        """
    
    def _convert_to_html(self, etp_content: str) -> str:
        """Converte conteúdo ETP para HTML formatado"""
        lines = etp_content.split('\n')
        html_lines = []
        current_section = None
        in_table = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if not in_table:
                    html_lines.append('<br>')
                continue
            
            # Detectar títulos de seção (1., 2., etc.)
            if self._is_section_title(line):
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                html_lines.append(f'<div class="secao-titulo">{line}</div>')
                current_section = line
                continue
            
            # Detectar subtítulos (1.1, 1.2, etc.)
            if self._is_subsection_title(line):
                if in_table:
                    html_lines.append('</table>')
                    in_table = False
                html_lines.append(f'<div class="subsecao-titulo">{line}</div>')
                continue
            
            # Detectar início de tabela
            if '|' in line and not in_table:
                html_lines.append('<table class="tabela">')
                in_table = True
            
            # Processar linha de tabela
            if '|' in line and in_table:
                html_lines.append(self._format_table_row(line))
                continue
            
            # Fim de tabela
            if in_table and '|' not in line:
                html_lines.append('</table>')
                in_table = False
            
            # Detectar lista com bullet points
            if line.startswith('•') or line.startswith('-'):
                html_lines.append(f'<div class="lista-item">{line[1:].strip()}</div>')
                continue
            
            # Parágrafo normal
            if line and not line.startswith('---'):
                html_lines.append(f'<p class="paragrafo">{line}</p>')
        
        # Fechar tabela se ainda estiver aberta
        if in_table:
            html_lines.append('</table>')
        
        return '\n'.join(html_lines)
    
    def _is_section_title(self, line: str) -> bool:
        """Verifica se é título de seção principal"""
        import re
        return bool(re.match(r'^\d+\.\s+[A-ZÁÊÇÕ]', line))
    
    def _is_subsection_title(self, line: str) -> bool:
        """Verifica se é título de subseção"""
        import re
        return bool(re.match(r'^\d+\.\d+\.?\s+[A-Za-z]', line))
    
    def _format_table_row(self, line: str) -> str:
        """Formata linha de tabela"""
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        
        # Detectar cabeçalho (primeira linha ou linha com texto em maiúsculas)
        is_header = any(cell.isupper() or 'Item' in cell or 'Risco' in cell for cell in cells)
        
        if is_header:
            formatted_cells = ''.join(f'<th>{cell}</th>' for cell in cells)
            return f'<tr>{formatted_cells}</tr>'
        else:
            # Destacar valores monetários e totais
            formatted_cells = []
            for cell in cells:
                if 'R$' in cell or 'TOTAL' in cell.upper():
                    formatted_cells.append(f'<td class="valor-destaque">{cell}</td>')
                else:
                    formatted_cells.append(f'<td>{cell}</td>')
            return f'<tr>{"".join(formatted_cells)}</tr>'
    
    def save_formatted_etp(self, formatted_html: str, filename: str = None) -> str:
        """Salva ETP formatado em arquivo HTML"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'etp_formatado_{timestamp}.html'
        
        filepath = os.path.join('/home/ubuntu/etp_ultra_otimizado', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_html)
        
        return filepath
    
    def convert_to_pdf_ready(self, formatted_html: str) -> str:
        """Prepara HTML para conversão em PDF"""
        # Adicionar estilos específicos para PDF
        pdf_styles = """
        <style>
        @media print {
            .documento-etp {
                border: 2px solid #333 !important;
                margin: 0 !important;
                padding: 20mm !important;
                box-shadow: none !important;
            }
            
            .secao-titulo {
                page-break-after: avoid;
            }
            
            .tabela {
                page-break-inside: avoid;
            }
            
            .paragrafo {
                orphans: 3;
                widows: 3;
            }
        }
        </style>
        """
        
        # Inserir estilos PDF antes do </head>
        return formatted_html.replace('</head>', pdf_styles + '</head>')

