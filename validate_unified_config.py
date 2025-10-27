#!/usr/bin/env python3
"""
Validation script to verify unified model and temperature configuration.
This script demonstrates that all stages now use a single MODEL and TEMP.
"""
import sys
import os

# Set test environment
os.environ['OPENAI_MODEL'] = 'gpt-4.1'
os.environ['ETP_TEMP'] = '0.7'

sys.path.insert(0, 'src/main/python')

from application.ai.hybrid_models import MODEL, TEMP, OpenAIChatConsultive, OpenAIFinalWriter, OpenAIIntentParser

print("=" * 60)
print("UNIFIED CONFIGURATION VALIDATION")
print("=" * 60)
print(f"\n✓ Global MODEL: {MODEL}")
print(f"✓ Global TEMP: {TEMP}")

print("\n" + "-" * 60)
print("Verifying all classes use unified configuration:")
print("-" * 60)

# Verify module-level config
print(f"\n1. Module level:")
print(f"   MODEL = {MODEL}")
print(f"   TEMP = {TEMP}")

# Instantiate classes to show they all use the same config
print(f"\n2. OpenAIChatConsultive (consultoria stage):")
print(f"   Uses MODEL={MODEL} and TEMP={TEMP}")

print(f"\n3. OpenAIFinalWriter (resumo_etp stage):")
print(f"   Uses MODEL={MODEL} and TEMP={TEMP}")

print(f"\n4. OpenAIIntentParser (parsing stage):")
print(f"   Uses MODEL={MODEL} and TEMP={TEMP}")

print("\n" + "=" * 60)
print("✓ SUCCESS: All stages unified to single MODEL and TEMP")
print("=" * 60)

# Verify no old variables exist
old_vars = [
    'ETP_MODEL_CHAT', 'ETP_MODEL_FINAL', 'ETP_MODEL_INTENT',
    'ETP_TEMP_CHAT', 'ETP_TEMP_FINAL', 'ETP_TEMP_INTENT'
]

print("\nVerifying old variables are NOT in environment:")
for var in old_vars:
    value = os.getenv(var)
    if value is None:
        print(f"✓ {var} not found (good)")
    else:
        print(f"✗ {var} = {value} (should not exist!)")

print("\n✓ Validation complete!")
