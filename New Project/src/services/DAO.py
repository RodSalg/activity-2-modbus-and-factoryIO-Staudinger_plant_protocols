import json
import threading
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any


class OrderConfig(BaseModel):
    """Modelo de dados para configuração de pedidos com validação"""

    order_count: int = Field(default=1, ge=1, description="Quantos pedidos?")

    order_color: Literal["BLUE", "GREEN", "OTHER"] = Field(
        default="GREEN", description="Cor do pedido"
    )

    order_boxes: int = Field(default=1, ge=1, description="Quantidade de caixas")

    order_resource: int = Field(default=1, ge=1, description="Quantidade de recursos")

    order_client: str = Field(default="rafael_ltda", description="Nome do cliente")

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


class object(BaseModel):
    client: str
    color_box: str
    resources: int


class MES:
    """
    Singleton
    """

    _instance: Optional["MES"] = None
    _lock = threading.Lock()

    def __new__(
        cls,
    ):
        if cls._instance is None:
            with cls._lock:

                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
    ):

        # padrão: data.json na raiz do repositório (subindo 3 níveis: services->src->New Project->repo)
        config_path = Path(__file__).resolve().parents[3] / "./New Project/src/orders/orders.json"
        if self._initialized:
            return

        self._config_path = Path(config_path)
        self._config: OrderConfig = self._load_config()
        self._initialized = True

        self.queue_storage = []
        self.queue_orders = []

    def _load_config(self) -> OrderConfig:

        # Se existir, tente carregar a seção de configuração.
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Suporta formatos antigos (config top-level) e novo (chave 'config')
                if isinstance(data, dict):
                    if "config" in data and isinstance(data["config"], dict):
                        return OrderConfig(**data["config"])
                    # caso legado: tentar usar diretamente as chaves do model
                    try:
                        return OrderConfig(**data)
                    except Exception:
                        # não conseguiu criar a partir do topo, usar padrão
                        pass

                print(
                    f"[CONFIG] Formato inesperado em {self._config_path}; usando padrão"
                )
                return OrderConfig()
            except (json.JSONDecodeError, Exception) as e:
                print(f"[CONFIG] Erro ao carregar {self._config_path}: {e}")
                print("[CONFIG] Usando configuração padrão")
                return OrderConfig()

        # Se não existir, cria um arquivo mínimo contendo apenas 'orders' e retorna config padrão
        else:
            try:
                base: Dict[str, Any] = {"orders": {}}
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(base, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[CONFIG] Erro ao criar {self._config_path}: {e}")
            return OrderConfig()

    def _save_config(self, config: OrderConfig) -> None:
        """Salva configuração no arquivo JSON"""
        with self._lock:
            data: Dict[str, Any] = {}
            if self._config_path.exists():
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            # preserva orders se existirem; guarda as configurações sob a chave 'config'
            data["config"] = config.model_dump()

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def get_config(self) -> OrderConfig:
        """Retorna a configuração atual (thread-safe)"""
        with self._lock:
            return self._config.model_copy(deep=True)

    # ---------------- persistent orders helpers ----------------
    def add_persistent_order(
        self, client: str, color: str, boxes: int, resource: int
    ) -> str:
        """
        Adiciona uma entrada em `data.json` no formato:

        {
          "orders": {
               "client": {"boxes": 1, "color": "BLUE", "resource": 5},
               "client2": {...}
           }
        }

        Retorna a chave criada (p.ex. 'rafael_ltda' ou 'rafael_ltda2').
        """
        client = str(client)
        color = str(color).upper()
        boxes = int(boxes)
        resource = int(resource)

        # validações simples
        valid_clients = ["rafael_ltda", "maria_sa", "joao_corp", "ana_ind"]
        if client not in valid_clients:
            raise ValueError(
                f"Cliente inválido: {client}. Deve ser um de {valid_clients}"
            )
        if color not in ("BLUE", "GREEN", "OTHER"):
            raise ValueError("Color inválida: deve ser BLUE, GREEN ou OTHER")
        if not (1 <= resource <= 5):
            raise ValueError("resource deve ser entre 1 e 5")

        with self._lock:
            data: Dict[str, Any] = {}
            if self._config_path.exists():
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            orders_raw = data.get("orders") or {}

            # Normalize existing orders: if there are suffixed keys (client2, client3)
            # migrate them into the base client key, but keep a single object per client.
            normalized: Dict[str, Any] = {}
            for k, v in orders_raw.items():
                base_key = k
                # detect suffixed keys like 'rafael_ltda2' -> base 'rafael_ltda'
                for base in ("rafael_ltda", "maria_sa", "joao_corp", "ana_ind"):
                    if k == base or (k.startswith(base) and k[len(base) :].isdigit()):
                        base_key = base
                        break
                # prefer keeping the first seen entry for the base_key (do not store lists)
                if base_key not in normalized:
                    normalized[base_key] = v

            # create/overwrite the order for the requested client
            entry = {"boxes": boxes, "color": color, "resource": resource}
            normalized[client] = entry

            data["orders"] = normalized

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # return the client key (no numeric suffix)
        return client

    def consume_persistent_order_by_color(self, color: str) -> bool:
        """
        Decrementa 1 caixa de um pedido persistido que tenha a cor informada.
        Se o pedido atingir 0 caixas, remove o cliente do `orders`.
        Retorna True se uma ordem foi atualizada/removida, False caso nenhum pedido compatível exista.
        """
        color = str(color).upper()
        with self._lock:
            data: Dict[str, Any] = {}
            if self._config_path.exists():
                try:
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            orders = data.get("orders") or {}

            # procura o primeiro cliente com a cor solicitada e boxes > 0
            for client, info in list(orders.items()):
                try:
                    info_color = str(info.get("color", "")).upper()
                    boxes = int(info.get("boxes", 0))
                except Exception:
                    continue

                if info_color == color and boxes > 0:
                    # antes de decrementar/remover, adiciona na fila de orders (cliente)
                    try:
                        clt = {
                            "client": client,
                            "color_box": info_color,
                            "resources": (
                                int(info.get("resource", 0))
                                if info.get("resource") is not None
                                else None
                            ),
                        }
                        # garante que as filas existem
                        try:
                            self.queue_orders.append(clt)
                            # debug: imprimir estado das filas
                            try:
                                print(f"[MES] queue_orders appended: {clt}")
                                print(
                                    f"[MES] queue_orders (len)={len(self.queue_orders)} queue_storage (len)={len(self.queue_storage)}"
                                )
                            except Exception:
                                pass
                        except Exception:
                            # se a instância atual não tiver queues (incomum), ignore
                            pass
                    except Exception:
                        pass

                    boxes -= 1
                    if boxes <= 0:
                        # remove pedido do arquivo
                        del orders[client]
                    else:
                        orders[client]["boxes"] = boxes

                    data["orders"] = orders
                    try:
                        with open(self._config_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    return True

            return False

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

    @property
    def order_count(self) -> int:
        # Retorna sempre a configuração atual carregada (cópia segura)
        return self.get_config().order_count

    @property
    def order_color(self) -> str:
        return self.get_config().order_color

    @property
    def order_boxes(self) -> int:
        return self.get_config().order_boxes

    @property
    def order_resource(self) -> int:
        return self.get_config().order_resource

    @property
    def order_client(self) -> str:
        return self.get_config().order_client

    def __repr__(self) -> str:
        return f"MES({self._config})"

    def print_queues(self) -> None:
        """Imprime estado atual das filas `queue_orders` e `queue_storage` (debug)."""
        try:
            with self._lock:
                q_orders = (
                    list(self.queue_orders) if hasattr(self, "queue_orders") else []
                )
                q_storage = (
                    list(self.queue_storage) if hasattr(self, "queue_storage") else []
                )
            print(f"[MES] queue_orders (len)={len(q_orders)} -> {q_orders}")
            print(f"[MES] queue_storage (len)={len(q_storage)} -> {q_storage}")
        except Exception as e:
            try:
                print(f"[MES] erro ao imprimir filas: {e}")
            except Exception:
                pass
