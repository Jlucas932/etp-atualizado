#!/usr/bin/env python3
"""
Script to add _ensure_initialized() calls to EtpDynamicController.py functions
"""

import re

def fix_controller_initialization():
    file_path = '/home/joao.pinheiro/Documentos/projeto-etp/autodoc-ia/src/main/python/adapter/entrypoint/etp/EtpDynamicController.py'
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find functions that use etp_generator, prompt_generator, or rag_system
    # and don't already have _ensure_initialized()
    pattern = r'(@etp_dynamic_bp\.route.*?\n@cross_origin\(\)\ndef [^:]+:\n    """[^"]*"""\n    try:\n)(?!        _ensure_initialized\(\))'
    
    def add_initialization(match):
        return match.group(1) + '        _ensure_initialized()\n'
    
    # Apply the replacement
    new_content = re.sub(pattern, add_initialization, content, flags=re.MULTILINE | re.DOTALL)
    
    # Also handle functions without try block
    pattern2 = r'(@etp_dynamic_bp\.route.*?\n@cross_origin\(\)\ndef [^:]+:\n    """[^"]*"""\n)(?!    _ensure_initialized\(\))(?!    try:)'
    
    def add_initialization2(match):
        return match.group(1) + '    _ensure_initialized()\n'
    
    new_content = re.sub(pattern2, add_initialization2, new_content, flags=re.MULTILINE | re.DOTALL)
    
    # Write the updated content back
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print("Fixed initialization calls in EtpDynamicController.py")

if __name__ == "__main__":
    fix_controller_initialization()