"""
Utilitários de segurança para mascaramento de credenciais e segredos.
"""

def mask_secret(secret: str, visible_start: int = 4, visible_end: int = 4, mask_char: str = "*") -> str:
    """
    Mascara um segredo exibindo apenas os primeiros e últimos caracteres.
    
    Args:
        secret: String contendo o segredo a ser mascarado
        visible_start: Número de caracteres visíveis no início
        visible_end: Número de caracteres visíveis no final
        mask_char: Caractere usado para mascarar
        
    Returns:
        String mascarada no formato: "abcd****xyz"
        
    Examples:
        >>> mask_secret("sk-1234567890abcdef")
        'sk-1****cdef'
        >>> mask_secret("postgresql://user:pass@host:5432/db")
        'post****2/db'
    """
    if not secret or not isinstance(secret, str):
        return "****"
    
    if len(secret) <= (visible_start + visible_end):
        # Se o segredo for muito curto, mascarar tudo
        return mask_char * min(len(secret), 8)
    
    start = secret[:visible_start]
    end = secret[-visible_end:]
    masked_middle = mask_char * min(len(secret) - visible_start - visible_end, 8)
    
    return f"{start}{masked_middle}{end}"


def mask_database_url(url: str) -> str:
    """
    Mascara especificamente URLs de banco de dados, ocultando senha.
    
    Args:
        url: URL de conexão do banco (formato SQLAlchemy)
        
    Returns:
        URL mascarada com senha oculta
        
    Examples:
        >>> mask_database_url("postgresql://user:secret123@localhost:5432/mydb")
        'postgresql://user:****@localhost:5432/mydb'
    """
    if not url or not isinstance(url, str):
        return "****"
    
    # Padrão: dialect://user:password@host:port/database
    import re
    pattern = r'(://[^:]+:)([^@]+)(@.+)'
    
    def replacer(match):
        return f"{match.group(1)}****{match.group(3)}"
    
    masked = re.sub(pattern, replacer, url)
    return masked


def mask_key(key: str) -> str:
    """
    Alias para mask_secret com parâmetros padrão para chaves de API.
    
    Args:
        key: Chave de API a ser mascarada
        
    Returns:
        Chave mascarada
        
    Examples:
        >>> mask_key("sk-1234567890abcdef")
        'sk-1****cdef'
    """
    return mask_secret(key, visible_start=4, visible_end=4)


def safe_log_config(config_dict: dict) -> dict:
    """
    Retorna uma cópia do dicionário de configuração com segredos mascarados.
    
    Args:
        config_dict: Dicionário com configurações (pode conter segredos)
        
    Returns:
        Dicionário com valores sensíveis mascarados
        
    Examples:
        >>> safe_log_config({"API_KEY": "secret", "DEBUG": True})
        {'API_KEY': '****', 'DEBUG': True}
    """
    sensitive_keys = {
        'api_key', 'openai_api_key', 'secret_key', 'password', 
        'database_url', 'db_url', 'token', 'metrics_token',
        'admin_pass', 'jwt_secret', 'encryption_key'
    }
    
    safe_dict = {}
    for key, value in config_dict.items():
        key_lower = key.lower()
        
        # Verificar se a chave contém termos sensíveis
        is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)
        
        if is_sensitive:
            if isinstance(value, str):
                if 'url' in key_lower:
                    safe_dict[key] = mask_database_url(value)
                else:
                    safe_dict[key] = mask_key(value)
            else:
                safe_dict[key] = "****"
        else:
            safe_dict[key] = value
    
    return safe_dict
