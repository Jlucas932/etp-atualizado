from datetime import datetime
from typing import Optional, Dict


class EtpTemplate:
    """Pure domain entity for EtpTemplate without ORM dependencies"""
    
    def __init__(self,
                 name: str,
                 description: Optional[str] = None,
                 template_structure: Optional[Dict] = None,
                 default_content: Optional[str] = None,
                 is_active: bool = True,
                 version: str = '1.0',
                 template_id: Optional[int] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = template_id
        self.name = name
        self.description = description
        self.template_structure = template_structure or {}
        self.default_content = default_content
        self.is_active = is_active
        self.version = version
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def get_template_structure(self) -> Dict:
        """Retorna a estrutura do template como dicionário"""
        return self.template_structure or {}
    
    def set_template_structure(self, structure_dict: Dict) -> None:
        """Define a estrutura do template a partir de um dicionário"""
        self.template_structure = structure_dict
        self.updated_at = datetime.utcnow()

    def update_description(self, description: str) -> None:
        """Atualiza a descrição do template"""
        self.description = description
        self.updated_at = datetime.utcnow()

    def set_default_content(self, content: str) -> None:
        """Define o conteúdo padrão do template"""
        self.default_content = content
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        """Ativa o template"""
        self.is_active = True
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """Desativa o template"""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def update_version(self, version: str) -> None:
        """Atualiza a versão do template"""
        self.version = version
        self.updated_at = datetime.utcnow()

    def increment_version(self) -> None:
        """Incrementa a versão do template automaticamente"""
        try:
            # Tenta converter para float e incrementar
            current_version = float(self.version)
            new_version = current_version + 0.1
            self.version = f"{new_version:.1f}"
        except ValueError:
            # Se não conseguir converter, adiciona sufixo
            self.version = f"{self.version}.1"
        self.updated_at = datetime.utcnow()

    def add_structure_section(self, section_name: str, section_config: Dict) -> None:
        """Adiciona uma seção à estrutura do template"""
        if not self.template_structure:
            self.template_structure = {}
        self.template_structure[section_name] = section_config
        self.updated_at = datetime.utcnow()

    def remove_structure_section(self, section_name: str) -> None:
        """Remove uma seção da estrutura do template"""
        if self.template_structure and section_name in self.template_structure:
            del self.template_structure[section_name]
            self.updated_at = datetime.utcnow()

    def has_structure(self) -> bool:
        """Verifica se o template possui estrutura definida"""
        return bool(self.template_structure)

    def has_default_content(self) -> bool:
        """Verifica se o template possui conteúdo padrão"""
        return bool(self.default_content)

    def is_template_active(self) -> bool:
        """Verifica se o template está ativo"""
        return self.is_active

    def clone(self, new_name: str) -> 'EtpTemplate':
        """Cria uma cópia do template com novo nome"""
        return EtpTemplate(
            name=new_name,
            description=f"Cópia de {self.name}",
            template_structure=self.template_structure.copy() if self.template_structure else None,
            default_content=self.default_content,
            is_active=False,  # Nova cópia inicia inativa
            version="1.0"  # Nova cópia inicia na versão 1.0
        )

    def to_dict(self) -> Dict:
        """Converte a entidade para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'template_structure': self.get_template_structure(),
            'default_content': self.default_content,
            'is_active': self.is_active,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        status = "ativo" if self.is_active else "inativo"
        return f'<EtpTemplate {self.name} v{self.version} ({status})>'