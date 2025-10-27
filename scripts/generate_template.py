#!/usr/bin/env python3
"""
Script to generate the ETP template file.
Run this from the project root: python3 scripts/generate_template.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'main', 'python'))

from domain.services.docx_exporter import create_etp_template

if __name__ == '__main__':
    template_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'templates',
        'modelo-etp.docx'
    )
    
    print(f"Generating ETP template at: {template_path}")
    create_etp_template(template_path)
    print("✓ Template generated successfully!")
    print(f"  Location: {os.path.abspath(template_path)}")
    print("\nYou can now customize this template in Microsoft Word.")
    print("The following placeholders will be replaced during export:")
    print("  - {{titulo}}")
    print("  - {{orgao}}")
    print("  - {{objeto}}")
    print("  - {{necessidade}}")
    print("  - {{requisitos}}")
    print("  - {{estrategia}}")
    print("  - {{pca}}")
    print("  - {{normas}}")
    print("  - {{quantitativo_valor}}")
    print("  - {{parcelamento}}")
    print("  - {{justificativas}}")
    print("  - {{assinaturas}}")
