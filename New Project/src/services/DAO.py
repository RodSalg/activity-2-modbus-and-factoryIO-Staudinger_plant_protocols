import json
import threading
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class OrderConfig(BaseModel):
    """Modelo de dados para configuração de pedidos com validação"""
    
    order_count: int = Field(
        default=1,
        ge=1,
        description="Quantos pedidos?"
    )
    
    order_color: Literal["BLUE", "GREEN", "EMPTY"] = Field(
        default="GREEN",
        description="Cor do pedido"
    )
    
    order_boxes: int = Field(
        default=5,
        ge=1,
        description="Quantidade de caixas"
    )
    
    order_resource: int = Field(
        default=5,
        ge=1,
        description="Quantidade de recursos"
    )
    
    order_client: str = Field(
        default="rafael_ltda",
        description="Nome do cliente"
    )
    
    @field_validator("order_client")
    @classmethod
    def validate_client(cls, v: str) -> str:
        """Valida que o cliente está na lista permitida"""
        valid_clients = ["rafael_ltda", "maria_sa", "joao_corp", "ana_ind"]
        if v not in valid_clients:
            raise ValueError(f"Cliente deve ser um de: {valid_clients}")
        return v
    
    @field_validator("order_color", mode="before")
    @classmethod
    def normalize_color(cls, v: str) -> str:
        """Normaliza a cor para uppercase"""
        if isinstance(v, str):
            return v.upper()
        return v


class ConfigManager:
    """
    Singleton
    """
    
    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, ):
        if cls._instance is None:
            with cls._lock:

                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, ):

        config_path = r"C:\Users\mnstsalg\Documents\04 - personal\modbus - ufam\activity-2-modbus-and-factoryIO-Staudinger_plant_protocols\New Project\src\services\data.json"

        if self._initialized:
            return
        
        self._config_path = Path(config_path)
        self._config: OrderConfig = self._load_config()
        self._initialized = True
    
    def _load_config(self) -> OrderConfig:

        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return OrderConfig(**data)
            except (json.JSONDecodeError, Exception) as e:
                print(f"[CONFIG] Erro ao carregar {self._config_path}: {e}")
                print("[CONFIG] Usando configuração padrão")
                return OrderConfig()
        else:

            config = OrderConfig()
            self._save_config(config)
            return config
    
    def _save_config(self, config: OrderConfig) -> None:
        """Salva configuração no arquivo JSON"""
        with self._lock:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
    
    def get_config(self) -> OrderConfig:
        """Retorna a configuração atual (thread-safe)"""
        with self._lock:
            return self._config.model_copy(deep=True)
    
    def update_config(self, **kwargs) -> OrderConfig:
        """
        Atualiza a configuração com novos valores e persiste no JSON.
        
        Args:
            **kwargs: Campos para atualizar (order_count, order_color, etc.)
        
        Returns:
            Configuração atualizada
        
        Raises:
            ValidationError: Se os valores não passarem na validação
        """
        with self._lock:

            current_data = self._config.model_dump()
            current_data.update(kwargs)
            
            new_config = OrderConfig(**current_data)
            
            self._save_config(new_config)
            
            self._config = new_config
            
            return new_config.model_copy(deep=True)
    
    def reset_to_defaults(self) -> OrderConfig:
        """Reseta configuração para valores padrão"""
        return self.update_config(
            order_count=1,
            order_color="GREEN",
            order_boxes=5,
            order_resource=5,
            order_client="rafael_ltda"
        )
    
    @property
    def order_count(self) -> int:
        return self._config.order_count
    
    @property
    def order_color(self) -> str:
        return self._config.order_color
    
    @property
    def order_boxes(self) -> int:
        return self._config.order_boxes
    
    @property
    def order_resource(self) -> int:
        return self._config.order_resource
    
    @property
    def order_client(self) -> str:
        return self._config.order_client
    
    def __repr__(self) -> str:
        return f"ConfigManager({self._config})"
