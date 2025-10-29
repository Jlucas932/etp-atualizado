"""
Unified Model Configuration for ETP Project
Centralized model and temperature settings - single source of truth
"""
import os
import logging

logger = logging.getLogger(__name__)

# Unified model configuration
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
TEMP = float(os.getenv("ETP_TEMP", "0.7"))

# Log configuration on import
logger.info(f"[MODELS] Unified configuration loaded: model={MODEL}, temp={TEMP}")

def get_model():
    """Returns the configured OpenAI model name"""
    return MODEL

def get_temperature():
    """Returns the configured temperature value"""
    return TEMP
