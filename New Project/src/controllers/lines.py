import threading
import time
from addresses import Coils, Inputs, Holding_Registers
from typing import TYPE_CHECKING
from typing import Optional, Dict, Tuple
from services.DAO import MES, OrderConfig

if TYPE_CHECKING:
    from server import FactoryModbusEventServer


class WarehouseExtension():
    
    def __init__(self, verbose: bool):
        
        self._warehouse_lock = threading.Lock()
        self.verbose = verbose

        self.client_columns = {
            "rafael_ltda": 1,   
            "maria_sa": 2,
            "joao_corp": 3,
            "ana_ind": 4
        }
        
        self.client_column_number = 1
        self.storage_column_number = 8

        self.storage_columns = [5, 6, 7, 8, 9]
        
        self.warehouse = {}
        for col in range(1, 10):
            self.warehouse[col] = {}
            for row in range(1, 7):
                self.warehouse[col][row] = {
                    "occupied": False,
                    "product_type": None,
                    "timestamp": None,
                    "order_id": None
                }


    # ================= WAREHOUSE MANAGEMENT METHODS =================
    
    def _calculate_position_address(self, column: int, row: int) -> int:
        """
        Calcula o endereço Modbus para uma posição no warehouse.
        
        ORIENTAÇÃO FÍSICA:
        - Coluna 1 = mais à DIREITA
        - Linha 1 = mais EMBAIXO
        
        A fórmula permanece a mesma: address = column + ((row - 1) * 9)
        O que muda é apenas a interpretação visual.
        
        Args:
            column: Número da coluna (1-9, onde 1 é a mais à direita)
            row: Número da linha (1-6, onde 1 é a mais embaixo)
        
        Returns:
            Endereço Modbus calculado
        
        Example:
            >>> _calculate_position_address(1, 1)  # Direita-Baixo
            1
            >>> _calculate_position_address(1, 2)  # Direita-Segunda de baixo
            10
            >>> _calculate_position_address(9, 6)  # Esquerda-Topo
            54
        """
        if not (1 <= column <= 9):
            raise ValueError(f"Coluna deve estar entre 1 e 9, recebido: {column}")
        
        if not (1 <= row <= 6):
            raise ValueError(f"Linha deve estar entre 1 e 6, recebido: {row}")
        
        address = column + ((row - 1) * 9)
        
        if self.verbose:
            position_desc = self._get_position_description(column, row)
            print(f"[WAREHOUSE] Posição calculada: {position_desc} -> endereço={address}")
        
        return address
    
    def _get_position_description(self, column: int, row: int) -> str:
        """
        Retorna descrição legível da posição física.
        
        Args:
            column: Número da coluna (1-9)
            row: Número da linha (1-6)
        
        Returns:
            Descrição da posição (ex: "Coluna 1 (direita), Linha 1 (embaixo)")
        """
        if column == 1:
            col_desc = "Coluna 1 (extrema direita)"
        elif column == 9:
            col_desc = "Coluna 9 (extrema esquerda)"
        else:
            col_desc = f"Coluna {column}"
        
        if row == 1:
            row_desc = "Linha 1 (embaixo)"
        elif row == 6:
            row_desc = "Linha 6 (topo)"
        else:
            row_desc = f"Linha {row}"
        
        return f"{col_desc}, {row_desc}"
    
    def _find_next_available_position_in_column(self, column: int) -> Optional[int]:
        """
        Encontra a próxima linha disponível em uma coluna específica.
        Começa pela Linha 1 (embaixo) e sobe.
        
        Args:
            column: Número da coluna (1-9)
        
        Returns:
            Número da linha disponível (1-6) ou None se coluna estiver cheia
        """
        for row in range(1, 7):  
            if not self.warehouse[column][row]["occupied"]:
                return row
        return None
    
    def _find_next_available_storage_column(self) -> Optional[Tuple[int, int]]:
        """
        Encontra a próxima posição disponível nas colunas de storage (5-9).
        Storage fica do lado ESQUERDO do warehouse.
        
        Returns:
            Tupla (column, row) com próxima posição disponível ou None se storage estiver cheio
        """
        for col in self.storage_columns: 
            row = self._find_next_available_position_in_column(col)
            if row is not None:
                return (col, row)
        return None
    
    def _occupy_position(self, column: int, row: int, product_type: str, order_id: Optional[str] = None) -> bool:
        """
        Marca uma posição como ocupada no warehouse.
        
        Args:
            column: Número da coluna (1-9, onde 1 é a mais à direita)
            row: Número da linha (1-6, onde 1 é a mais embaixo)
            product_type: Tipo do produto ("BLUE" | "GREEN")
            order_id: ID do pedido (opcional)
        
        Returns:
            True se posição foi ocupada com sucesso, False se já estava ocupada
        """
        if product_type not in ["BLUE", "GREEN"]:
            raise ValueError(f"Tipo de produto inválido: {product_type}. Deve ser 'BLUE' ou 'GREEN'")
        
        if not (1 <= column <= 9) or not (1 <= row <= 6):
            raise ValueError(f"Posição inválida: coluna={column}, linha={row}")
        
        with self._warehouse_lock:
            if self.warehouse[column][row]["occupied"]:
                if self.verbose:
                    print(f"[WAREHOUSE] AVISO: Posição coluna={column} linha={row} já está ocupada")
                return False
            
            self.warehouse[column][row] = {
                "occupied": True,
                "product_type": product_type,
                "timestamp": time.time(),
                "order_id": order_id
            }
            
            if self.verbose:
                pos_desc = self._get_position_description(column, row)
                print(f"[WAREHOUSE] Posição ocupada: {pos_desc}, produto={product_type}")
            
            return True
        
    def _find_next_available_client_position(self, client_name: str) -> Optional[Tuple[int, int]]:
        """
        Encontra a próxima posição disponível na coluna de um cliente específico.
        
        Args:
            client_name: Nome do cliente (ex: "rafael_ltda", "maria_sa", "joao_corp", "ana_ind")
        
        Returns:
            Tupla (column, row) com próxima posição disponível ou None se:
            - Cliente não existir
            - Coluna do cliente estiver cheia
        
        Example:
            >>> _find_next_available_client_position("rafael_ltda")
            (1, 3)  # Coluna 1 (rafael_ltda), Linha 3 disponível
            
            >>> _find_next_available_client_position("cliente_invalido")
            None  # Cliente não encontrado
        """

        if client_name not in self.client_columns:
            if self.verbose:
                print(f"[WAREHOUSE] ERRO: Cliente '{client_name}' não encontrado no mapeamento")
                print(f"[WAREHOUSE] Clientes disponíveis: {list(self.client_columns.keys())}")
            return None
        
        client_column = self.client_columns[client_name]
        row = self._find_next_available_position_in_column(client_column)
        
        if row is None:
            if self.verbose:
                print(f"[WAREHOUSE] AVISO: Coluna do cliente '{client_name}' (col {client_column}) está cheia!")
            return None
        
        if self.verbose:
            pos_desc = self._get_position_description(client_column, row)
            print(f"[WAREHOUSE] Próxima posição disponível para '{client_name}': {pos_desc}")
        
        return (client_column, row)
    
    def _free_position(self, address: int) -> bool:
        """
        Libera uma posição no warehouse a partir do endereço Modbus.
        
        Args:
            address: Endereço Modbus da posição (1-54)
        
        Returns:
            True se posição foi liberada, False se já estava livre
        """
        
        if not (1 <= address <= 54):
            if self.verbose:
                print(f"[WAREHOUSE] ERRO: Endereço inválido: {address}. Deve estar entre 1 e 54.")
            return False
        
        column = ((address - 1) % 9) + 1
        row = ((address - 1) // 9) + 1
        
        with self._warehouse_lock:
            if not self.warehouse[column][row]["occupied"]:
                if self.verbose:
                    print(f"[WAREHOUSE] AVISO: Posição endereço={address} (coluna={column} linha={row}) já está livre")
                return False
            
            self.warehouse[column][row] = {
                "occupied": False,
                "product_type": None,
                "timestamp": None,
                "order_id": None
            }
            
            if self.verbose:
                pos_desc = self._get_position_description(column, row)
                print(f"[WAREHOUSE] Posição liberada: endereço={address} ({pos_desc})")
            
            return True
        
    def _find_available_product(self, product: str) -> int:
        """
        Busca um produto disponível no storage (colunas 5-9).
        
        Args:
            product: Tipo do produto a buscar ("green" ou "blue")
        
        Returns:
            Endereço Modbus da posição encontrada ou -1 se não houver produto disponível
        """
        product_type = product.upper()
        
        if product_type not in ["GREEN", "BLUE"]:
            if self.verbose:
                print(f"[WAREHOUSE] ERRO: Tipo de produto inválido: {product}")
            return -1
        
        with self._warehouse_lock:
            for col in self.storage_columns:

                for row in range(1, 7):
                    position = self.warehouse[col][row]
                    
                    if position["occupied"] and position["product_type"] == product_type:
                        address = self._calculate_position_address(col, row)
                        
                        if self.verbose:
                            pos_desc = self._get_position_description(col, row)
                            print(f"[WAREHOUSE] Produto {product_type} encontrado em {pos_desc} (endereço {address})")

                        return address
        
        # Se chegou aqui, não encontrou o produto
        if self.verbose:
            print(f"[WAREHOUSE] Produto {product_type} não disponível no storage")
        
        return -1

    
    
    def print_warehouse_map(self) -> None:
        """
        Imprime um mapa visual do warehouse com orientação correta.
        
        VISTA FRONTAL:
        - Esquerda do mapa = Coluna 9 (esquerda física)
        - Direita do mapa = Coluna 1 (direita física)
        - Topo do mapa = Linha 6 (topo físico)
        - Base do mapa = Linha 1 (base física)
        """
        print("\n" + "="*95)
        print(" WAREHOUSE MAP - VISTA FRONTAL ".center(95, "="))
        print("="*95)
        
        print(f"{'Posição':>10} | ", end="")
        for c in range(9, 0, -1):
            print(f" Col {c} ", end=" | ")
        print()
        
        print(f"{'':>10} | ", end="")
        for c in range(9, 0, -1):
            if c in self.storage_columns:
                print(" (Stor)", end=" | ")
            else:
                client_name = ""
                for name, col_num in self.client_columns.items():
                    if col_num == c:
                        client_name = name[:6] 
                        break
                print(f" ({client_name:^6})", end=" | ")
        print()
        
        print("-" * 95)
        
        for row in range(6, 0, -1):

            if row == 6:
                row_label = f"L{row} (topo)"
            elif row == 1:
                row_label = f"L{row} (base)"
            else:
                row_label = f"L{row}"
            
            print(f"{row_label:>10} | ", end="")
            
            for col in range(9, 0, -1):
                pos = self.warehouse[col][row]
                if pos["occupied"]:
                    symbol = "B" if pos["product_type"] == "BLUE" else "G"
                    print(f"  [{symbol}]  ", end=" | ")
                else:
                    print(f"  [ ]  ", end=" | ")
            print()
        
        print("-" * 95)
        
        # Legenda
        print("\nLEGENDA:")
        print("  [B] = Produto BLUE  |  [G] = Produto GREEN  |  [ ] = Vazio")
        print("\nCLIENTES (Colunas 1-4, lado DIREITO):")
        for name, col in sorted(self.client_columns.items(), key=lambda x: x[1]):
            print(f"  • {name:15} = Coluna {col}")
        print(f"\nSTORAGE (Colunas 5-9, lado ESQUERDO): {self.storage_columns}")
        print("\nORIENTAÇÃO:")
        print("  • Coluna 1 = Extrema DIREITA")
        print("  • Coluna 9 = Extrema ESQUERDA")
        print("  • Linha 1 = BASE (embaixo)")
        print("  • Linha 6 = TOPO (em cima)")
        print("="*95 + "\n")


class LineController:
    def __init__(self, server: "FactoryModbusEventServer", verbose: bool = True):
        self.server = server
        self.verbose = verbose
        self._blue_running = False
        self._green_running = False
        self._empty_running = False
        self._production_running = False

        self.turntable3_busy = False


        self._lock = threading.Lock()

        self.config = MES()

        # self.DEFAULT_ORDER_COUNT  = 1
        # self.DEFAULT_ORDER_COLOR  = "GREEN"
        # self.DEFAULT_ORDER_BOXES  = 5
        # self.DEFAULT_ORDER_RESOURCE  = 5
        # self.DEFAULT_ORDER_CLIENT = "rafael_ltda"

        # --- construção da classe de controle da warehouse
        self.warehouse_data_structure = WarehouseExtension(verbose=verbose)

            # -- definindo algumas caixas alocadas no cliente 1 e 2
        self.warehouse_data_structure._occupy_position(1, 2, 'BLUE', f'column_free_row_free_order')
        self.warehouse_data_structure._occupy_position(2, 2, 'BLUE', f'column_free_row_free_order')

            # -- definindo algumas caixas alocadas no estoque
        self.warehouse_data_structure._occupy_position(9, 1, 'BLUE', f'column_free_row_free_order')
        self.warehouse_data_structure._occupy_position(9, 2, 'BLUE', f'column_free_row_free_order')
        self.warehouse_data_structure._occupy_position(8, 2, 'BLUE', f'column_free_row_free_order')
        self.warehouse_data_structure._occupy_position(9, 4, 'BLUE', f'column_free_row_free_order')


        # --- Estados da mesa ---
        self._turntable_turn = False  # False = giro OFF/centro
        self._turntable_belt = "stop"  # "forward" | "backward" | "stop"
        self._belt_watch_th = None  # thread do watcher
        self._belt_watching = False  # flag do watcher
        self.turntable_busy = False
        self.active_job = None
        self.turntable1_busy = False

        self.is_warehouse_free = True

    def whichProductIs(self):
        if(self.config.get_config().order_color == 'BLUE'):
            return 'GREEN'
        
        return 'BLUE'
    
    # ================= Client conveyor =====================

    # Adicione estes métodos na classe LineController em lines.py:

    def pick_and_place(self):
        """Aciona o sistema de pick and place"""
        if self.server.machine_state != "running":
            return
        
        threading.Thread(
            target=self._t_pick_and_place, 
            name="T_PickPlace", 
            daemon=True
        ).start()

    def _t_pick_and_place(self):
        """Thread que executa o pick and place"""
        if self.verbose:
            print("Acionando pick/place...")
        
        try:
            print('acionando o pick')
            self.server.set_actuator(Inputs.PICK_PLACE, True)
            time.sleep(2.0)
            self.server.set_actuator(Inputs.PICK_PLACE, False)
            
            if self.verbose:
                print("Pick/place concluído")
        except Exception as e:
            if self.verbose:
                print(f"[ERRO] Pick/place falhou: {e}")


    def ciclo_turntable3(self):
        """Inicia o ciclo completo da turntable 3"""
        # if self.server.machine_state != "running":
        #     return

        self._t_ciclo_turntable3()
        
        # threading.Thread(
        #     target=self._t_ciclo_turntable3, 
        #     name="T_CicloTT3", 
        #     daemon=True
        # ).start()

    def _t_ciclo_turntable3(self):
        """Thread que executa o ciclo completo da turntable 3"""
        print('entrei na thread')
        # Marca mesa como ocupada
        with self._lock:
            if self.turntable3_busy:
                if self.verbose:
                    print("[TT3] Mesa já ocupada, ignorando novo ciclo")
                return
            self.turntable3_busy = True
        
        try:
            if self.verbose:
                print("📦 Iniciando ciclo da Turntable 3")
            
            # Para a esteira forward
            self.server.set_actuator(Inputs.Turntable3_forward, False)
            time.sleep(1.5)
            
            # Gira 90°
            if self.verbose:
                print("Girando 90°...")
            self.server.set_actuator(Inputs.Turntable3_turn, True)
            time.sleep(2.5)
            
            # Liga esteira forward e esteira de pedido
            if self.verbose:
                print("Ligando esteiras...")
            self.server.set_actuator(Inputs.Turntable3_forward, True)
            self.server.set_actuator(Inputs.ESTEIRA_PEDIDO, True)
            time.sleep(2.5)
            
            # Desliga esteira forward
            self.server.set_actuator(Inputs.Turntable3_forward, False)
            time.sleep(2.5)
            
            # Volta turntable para posição original
            self.server.set_actuator(Inputs.Turntable3_turn, False)
            self.server.set_actuator(Inputs.ESTEIRA_PEDIDO, False)
            
            if self.verbose:
                print("✅ Ciclo da Turntable 3 concluído")
                
        except Exception as e:
            if self.verbose:
                print(f"[ERRO] Ciclo TT3 falhou: {e}")
        finally:
            with self._lock:
                self.turntable3_busy = False


    def start_esteira_carregamento(self):
        """Liga a esteira de carregamento"""
        if self.server.machine_state != "running":
            return
        
        if self.verbose:
            print("Ligando esteira de carregamento")
        self.server.set_actuator(Inputs.ESTEIRA_CARREGAMENTO, True)


    def stop_esteira_carregamento(self):
        """Para a esteira de carregamento"""
        if self.verbose:
            print("Parando esteira de carregamento")
        self.server.set_actuator(Inputs.ESTEIRA_CARREGAMENTO, False)

    # ================= warehouse space =====================

    # ------------ storage ------------
    def save_on_storage_warehouse(self):
        # if self.server.machine_state != "running":
        #     if(self.verbose):
        #         print('\n\n \t\t [LOG STORAGE WAREHOUSE] === Impossível executar este evento pois a máquina não está em execução. \n\n')
        #     return

        threading.Thread(target=self._t_save_on_storage_warehouse, name="T_save_on_storage_warehouse", daemon=True).start()

    def _t_save_on_storage_warehouse(self):
        if(self.is_warehouse_free == False):
            return

        if(self.verbose):
            print('\n\n \t\t [LOG storage WAREHOUSE] === writing in target position. \n\n')
        
        self.is_warehouse_free = False

        try:
        
            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = self.warehouse_data_structure.storage_column_number)
            time.sleep(2)
            print('\t\t', Coils.sensor_move_warehouse)
            
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.server.set_actuator(Inputs.manejador_fora, True)
            time.sleep(2)
            
            self.server.set_actuator(Inputs.manejador_levantar, True)
            time.sleep(2)
            
            self.server.set_actuator(Inputs.manejador_fora, False)
            time.sleep(1)

            print('momento de mandar para a proxima coluna disponível')
            storage_position = self.warehouse_data_structure._find_next_available_storage_column()

            if storage_position is None:
                print('[ERRO] Storage está completamente cheio! Impossível armazenar.')
                return
            
            column_free, row_free = storage_position

            print(column_free, row_free)

            free_position = column_free + (9 * (row_free - 1))
            print('\t\tposição disponível atualmente: ', free_position)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = free_position)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.server.set_actuator(Inputs.manejador_dentro, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_levantar, False)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_dentro, False)
            time.sleep(1)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = 300)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.warehouse_data_structure._occupy_position(column_free, row_free, self.config.get_config().order_color, f'{column_free}_{row_free}_order')
            time.sleep(0.1)
            self.warehouse_data_structure.print_warehouse_map()

        except ValueError as e:
            print('[ERRO ao executar a função write_input_register - posicao_alvo]: ', e)

        self.is_warehouse_free = True

    def remove_from_storage_warehouse(self):
        # if self.server.machine_state != "running":
        #     if(self.verbose):
        #         print('\n\n \t\t [LOG STORAGE WAREHOUSE] === Impossível executar este evento pois a máquina não está em execução. \n\n')
        #     return

        threading.Thread(target=self._t_remove_from_storage_warehouse, name="T_remove_from_storage_warehouse", daemon=True).start()

    def _t_remove_from_storage_warehouse(self,):
        if(self.is_warehouse_free == False):
            print('A thread de remoção do estoque não foi executada pois o robô não está livre!')
            return

        if(self.verbose):
            print('\n\n \t\t [LOG storage WAREHOUSE] === writing in target position. \n\n')
        
        self.is_warehouse_free = False

        self.server.set_actuator(Inputs.light_button_box_from_storage, True)
        
        try:
        
            #como é uma retirada, garanto que o Z está baixo
            self.server.set_actuator(Inputs.manejador_levantar, False)

            #encontrando onde tem um produto disponível
            
            order_color = self.config.get_config().order_color 
            position_of_item = self.warehouse_data_structure._find_available_product(order_color)

            if(position_of_item == -1):
                if(self.verbose):
                    print('Não foi encontrado nada no estoque!')
                    self.server.set_actuator(Inputs.light_not_in_store, True)

                    time.sleep(3)

                    self.server.set_actuator(Inputs.light_not_in_store, False)
                    self.is_warehouse_free = True

                    return
            self.server.set_actuator(Inputs.light_have_in_store, True)
            
            
            #vou ate a coluna a qual eu quero remover
            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = position_of_item)

            time.sleep(2)
            print('\t\t', Coils.sensor_move_warehouse)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.server.set_actuator(Inputs.manejador_dentro, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_levantar, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_dentro, False)
            time.sleep(1)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = 8)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.server.set_actuator(Inputs.manejador_fora, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_levantar, False)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_fora, False)
            time.sleep(1)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = 300)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.warehouse_data_structure._free_position(address=position_of_item)

            time.sleep(0.1)
            self.warehouse_data_structure.print_warehouse_map()

        except ValueError as e:
            print('[ERRO ao executar a função write_input_register - posicao_alvo]: ', e)
            
        self.server.set_actuator(Inputs.light_button_box_from_storage, False)
        self.server.set_actuator(Inputs.light_have_in_store, False)

        self.is_warehouse_free = True

    
    # ------------ client ------------
    def save_on_client_warehouse(self):
        
        # if self.server.machine_state != "running":
        #     if(self.verbose):
        #         print('\n\n \t\t [LOG client WAREHOUSE] === Impossível executar este evento pois a máquina não está em execução. \n\n')
        #     return

        threading.Thread(target=self._t_save_on_client_warehouse, name="T_save_on_client_warehouse", daemon=True).start()

    def _t_save_on_client_warehouse(self):
        if(self.is_warehouse_free == False):
            return

        if(self.verbose):
            print('\n\n \t\t [LOG client WAREHOUSE] === writing in target position. \n\n')
        
        self.is_warehouse_free = False

        try:
        
            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = self.warehouse_data_structure.client_column_number)
            time.sleep(2)
            print('\t\t', Coils.sensor_move_warehouse)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)
            self.server.set_actuator(Inputs.manejador_fora, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_levantar, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_fora, False)
            time.sleep(1)

            print('momento de mandar para a proxima coluna disponível')
            client_position = self.warehouse_data_structure._find_next_available_client_position(self.config.get_config().order_client)

            if client_position is None:
                print('[ERRO] client está completamente cheio! Impossível armazenar.')
                return
            
            column_free, row_free = client_position

            print(column_free, row_free)

            free_position = column_free + (9 * (row_free - 1))
            print('\t\tposição disponível atualmente: ', free_position)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = free_position)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.server.set_actuator(Inputs.manejador_dentro, True)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_levantar, False)
            time.sleep(2)
            self.server.set_actuator(Inputs.manejador_dentro, False)
            time.sleep(1)

            self.server.write_input_register(address=Holding_Registers.posicao_alvo, value = 300)

            time.sleep(1)
            while(self.server.get_sensor(Coils.sensor_move_warehouse)): time.sleep(0.2)

            self.warehouse_data_structure._occupy_position(column_free, row_free, self.whichProductIs(), f'{column_free}_{row_free}_order')
            time.sleep(0.1)
            self.warehouse_data_structure.print_warehouse_map()

        except ValueError as e:
            print('[ERRO ao executar a função write_input_register - posicao_alvo]: ', e)

        self.is_warehouse_free = True



    # ---------------- Helpers IO ----------------
    def _activate(self, *actuators):
        with self._lock:
            for a in actuators:
                self.server.set_actuator(a, True)

    def _deactivate(self, *actuators):
        with self._lock:
            for a in actuators:
                self.server.set_actuator(a, False)

    # ================= BLUE =================
    def run_blue_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha azul")

        threading.Thread(
            target=self._t_run_blue_line, name="TRUN-BlueLine", daemon=True
        ).start()
    
    def run_esteira_producao_2(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha azul")

        threading.Thread(
            target=self._t_start_prod_line, name="TRUN-ProductionLine", daemon=True
        ).start()

    def stop_blue_line(self):
        if self.verbose:
            print("parando linha azul")

        threading.Thread(
            target=self._t_stop_blue_line, name="TSTOP-BlueLine", daemon=True
        ).start()

    def _t_run_blue_line(self):
        with self._lock:
            if self._blue_running:
                return
            self._blue_running = True
        try:
            self._activate(Inputs.Caixote_Azul_Esteira_1, Inputs.Caixote_Azul_Esteira_2, Inputs.Esteira_Producao_1)
        finally:
            pass

    def _t_start_prod_line(self):
        try:
            self._activate(
                Inputs.Esteira_Producao_2,
            )
        finally:
            with self._lock:
                self._blue_running = False

    # ================= GREEN =================
    def run_green_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha verde")
        threading.Thread(
            target=self._t_run_green_line, name="TRUN-GreenLine", daemon=True
        ).start()

    def stop_green_line(self):
        if self.verbose:
            print("parando linha verde")
        threading.Thread(
            target=self._t_stop_green_line, name="TSTOP-GreenLine", daemon=True
        ).start()

    def _t_run_green_line(self):
        with self._lock:
            if self._green_running:
                return
            self._green_running = True
        try:
            self._activate(
                Inputs.Caixote_Verde_Esteira_1,
                Inputs.Caixote_Verde_Esteira_2,
                Inputs.Caixote_Verde_Esteira_3,
                Inputs.Caixote_Verde_Esteira_4,
            )
        finally:
            pass

    def _t_stop_green_line(self):
        try:
            self._deactivate(
                Inputs.Caixote_Verde_Esteira_1,
                Inputs.Caixote_Verde_Esteira_2,
                Inputs.Caixote_Verde_Esteira_3,
                Inputs.Caixote_Verde_Esteira_4,
            )
        finally:
            with self._lock:
                self._green_running = False

    # ================= EMPTY =================
    def run_empty_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha vazio")
        threading.Thread(
            target=self._t_run_empty_line, name="TRUN-EmptyLine", daemon=True
        ).start()

    def stop_empty_line(self):
        if self.verbose:
            print("parando linha vazio")
        threading.Thread(
            target=self._t_stop_empty_line, name="TSTOP-EmptyLine", daemon=True
        ).start()

    def _t_run_empty_line(self):
        with self._lock:
            if self._empty_running:
                return
            self._empty_running = True
        try:
            self._activate(
                Inputs.Caixote_Vazio_Esteira_1,
                Inputs.Caixote_Vazio_Esteira_2,
                Inputs.Caixote_Vazio_Esteira_3,
                Inputs.Caixote_Vazio_Esteira_4,
            )
        finally:
            pass

    def _t_stop_empty_line(self):
        try:
            self._deactivate(
                Inputs.Caixote_Vazio_Esteira_1,
                Inputs.Caixote_Vazio_Esteira_2,
                Inputs.Caixote_Vazio_Esteira_3,
                Inputs.Caixote_Vazio_Esteira_4,
            )
        finally:
            with self._lock:
                self._empty_running = False

    # ================ Production (all) ================
    def run_production_line(self):
        if self.server.machine_state != "running":
            return
        # if self.verbose:
        #     print("ligando linha produção")
        threading.Thread(
            target=self._t_run_production_line, name="TRUN-ProductionLine", daemon=True
        ).start()

    def stop_production_line(self):
        if self.verbose:
            print("parando linha produção")
        threading.Thread(
            target=self._t_stop_production_line,
            name="TSTOP-ProductionLine",
            daemon=True,
        ).start()

    def _t_run_production_line(self):
        with self._lock:
            if self._production_running:
                return
            self._production_running = True
        try:

            self._activate(Inputs.Esteira_Producao_1, Inputs.Esteira_Producao_2)

        finally:
            pass

    def _t_stop_production_line(self):
        try:
            self._deactivate(Inputs.Esteira_Producao_1)
        finally:
            with self._lock:
                self._production_running = False

    # ========== Prod Line ==========
    def is_production_running(self, color: str) -> bool:
        with self._lock:
            return self._production_running

    # ========== Turntable Unified (ON/OFF + Belt) ==========
    # def set_turntable_async(
    #     self,
    #     turn_on: bool | None,
    #     belt: str = "none",  # "forward" | "backward" | "stop"/"none"
    #     stop_limit: str | None = None,  # "front" | "back" | None (não vigia)
    #     belt_timeout_s: float = 1.0,
    # ):
    #     if self.server.machine_state != "running":
    #         return
    #     threading.Thread(
    #         target=self._t_set_turntable,
    #         args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
    #         name=f"TRUN-Turntable-{turn_on}-{belt}-{stop_limit}",
    #         daemon=True,
    #     ).start()

    def set_turntable_async(
        self,
        turn_on: bool | None,
        belt: str = "none",  # "forward" | "backward" | "stop"/"none"
        stop_limit: str | None = None,  # "front" | "back" | None (não vigia)
        belt_timeout_s: float = 1.0,
    ):
        if self.server.machine_state != "running":
            return

        # ====== GUARDA TT1: só aceitar novo comando quando a operação anterior terminar ======
        # Considera "ocupado" se:
        #   - uma operação anterior marcou busy (turntable1_busy=True), ou
        #   - o watcher da TT1 ainda está ativo (_belt_watching=True).
        # Obs.: Se preferir não BLOQUEAR, você pode apenas "return" quando ocupado.
        wait_deadline = time.time() + 10.0  # timeout de segurança para não travar
        while (
            self.turntable1_busy or getattr(self, "_belt_watching", False)
        ) and time.time() < wait_deadline:
            time.sleep(0.01)

        if self.turntable1_busy or getattr(self, "_belt_watching", False):
            # Ainda ocupado após timeout, não agenda nova operação.
            if self.verbose:
                print(
                    "[TT1][GUARDA] ocupado (busy/watcher ativo); ignorando comando para evitar atropelo."
                )
            return
        # =====================================================================================

        threading.Thread(
            target=self._t_set_turntable,
            args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
            name=f"TRUN-Turntable-{turn_on}-{belt}-{stop_limit}",
            daemon=True,
        ).start()

    def turntable_on(self, belt: str = "none"):
        self.set_turntable_async(True, belt)

    def turntable_off(self, belt: str = "none"):
        self.set_turntable_async(False, belt)

    def turntable_belt_forward(self):
        self.set_turntable_async(turn_on=None, belt="forward")

    def turntable_belt_backward(self):
        self.set_turntable_async(turn_on=None, belt="backward")

    def turntable_belt_stop(self):
        self.set_turntable_async(turn_on=None, belt="stop")

    # ---------------- worker da mesa ----------------
    def _t_set_turntable(
        self,
        turn_on: bool | None,
        belt: str,
        stop_limit: str | None,
        belt_timeout_s: float,
    ):
        self.turntable1_busy = True
        TURN_COIL = Inputs.Turntable1_turn
        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida

        try:
            # --- gira (se pedido) ---
            with self._lock:
                if turn_on is True:
                    self.server.set_actuator(TURN_COIL, True)
                    self._turntable_turn = True
                elif turn_on is False:
                    self.server.set_actuator(TURN_COIL, False)
                    self._turntable_turn = False

            # --- belt interno ---
            belt_to_watch = None
            if belt == "forward":
                self.server.set_actuator(BELT_REV, False)
                self.server.set_actuator(BELT_FWD, True)
                with self._lock:
                    self._turntable_belt = "forward"
                belt_to_watch = "forward"
            elif belt == "backward":
                self.server.set_actuator(BELT_FWD, False)
                self.server.set_actuator(BELT_REV, True)
                with self._lock:
                    self._turntable_belt = "backward"
                belt_to_watch = "backward"
            elif belt in ("stop", "none"):
                self.server.set_actuator(BELT_FWD, False)
                self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                belt_to_watch = None

            # --- watcher: escolhe o LIMITE conforme stop_limit explicitado ---
            if stop_limit is None or belt_to_watch is None:
                self._stop_belt_watcher()
                if self.verbose:
                    print(
                        f"[turntable] turn_on={turn_on} belt={belt} -> turn={getattr(self,'_turntable_turn',None)} belt_state={self._turntable_belt}"
                    )
                return

            if stop_limit.lower() == "front":
                limit_addr = Coils.Turntable1_FrontLimit
            elif stop_limit.lower() == "back":
                limit_addr = Coils.Turntable1_BackLimit
            else:
                if self.verbose:
                    print(
                        f"[turntable] stop_limit inválido: {stop_limit} (esperado 'front' ou 'back'); watcher desativado."
                    )
                self._stop_belt_watcher()
                return

            # inicia watcher com grace + borda + tempo mínimo
            self._start_belt_watcher(
                direction=belt_to_watch, limit_addr=limit_addr, timeout_s=belt_timeout_s
            )
            if self.verbose:
                print(
                    f"[turntable] turn_on={turn_on} belt={belt} stop_limit={stop_limit} -> turn={getattr(self,'_turntable_turn',None)} belt_state={self._turntable_belt}"
                )
        finally:
            self.turntable1_busy = False

    # ---------------- watcher da esteira da mesa ----------------
    def _stop_belt_watcher(self):
        """Solicita parada do watcher atual (se existir) e aguarda um pouco."""
        self._belt_watching = False
        th = self._belt_watch_th
        if th and th.is_alive():
            th.join(timeout=0.2)
        self._belt_watch_th = None

    def _start_belt_watcher(
        self,
        direction: str,
        limit_addr: int,
        timeout_s: float = 3.0,
        grace_s: float = 0.20,
        min_on_s: float = 0.30,
    ):
        # mata watcher anterior
        self._stop_belt_watcher()
        self._belt_watching = True

        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida
        BELT_ADDR = BELT_FWD if direction == "forward" else BELT_REV

        stop_evt = getattr(self.server, "_stop_evt", None)

        def _watch():
            t_on = time.time()
            try:
                # grace: dá tempo do motor iniciar (evita desligar se limite já começar True)
                time.sleep(grace_s)

                # snapshot inicial para exigir BORDA (0->1)
                start_state = bool(self.server.get_sensor(limit_addr))
                deadline = time.time() + timeout_s
                DEBOUNCE_N = 2
                stable = 0

                while time.time() < deadline:
                    if stop_evt and stop_evt.is_set():
                        break
                    if self.server.machine_state != "running":
                        break

                    cur = bool(self.server.get_sensor(limit_addr))
                    if (not start_state) and cur:
                        stable += 1
                    else:
                        stable = 0

                    if stable >= DEBOUNCE_N:
                        break
                    time.sleep(0.02)

                # tempo mínimo ligado antes de cortar
                rem = min_on_s - (time.time() - t_on)
                if rem > 0:
                    time.sleep(rem)

                # corta belt por limite (estável) ou por timeout (fail-safe)
                self.server.set_actuator(BELT_ADDR, False)
                with self._lock:
                    self._turntable_belt = "stop"

                if self.verbose:
                    if stable >= DEBOUNCE_N:
                        print(
                            f"[turntable] limite (edge) atingido ({direction}); esteira interna parada."
                        )
                    else:
                        print(
                            f"[turntable] timeout ({direction}); esteira interna parada por segurança."
                        )
            finally:
                self._belt_watching = False

        self._belt_watch_th = threading.Thread(
            target=_watch, name=f"TWatch-Turntable-{direction}", daemon=True
        )
        self._belt_watch_th.start()

    def _watch_limit_and_stop(self, direction: str, limit_addr: int, timeout_s: float):
        """
        Espera COIL de limite (Factory I/O: sensores são COILS) sem bloquear o event loop.
        Quando o limite aciona, desliga a direção ativa da esteira interna da mesa.
        """
        BELT_FWD = Inputs.Turntable1_Esteira_SaidaEntrada
        BELT_REV = Inputs.Turntable1_Esteira_EntradaSaida
        stop_evt = getattr(self.server, "stop_event", None) or getattr(
            self.server, "_stop_evt", None
        )

        DEBOUNCE_N = 2
        stable = 0
        t0 = time.time()
        print(
            f"[watcher] iniciado: direction={direction}, limit={limit_addr}, timeout={timeout_s}"
        )

        while self._belt_watching:
            # dentro do watcher loop:
            print(
                f"[debug] sensor({limit_addr}) = {self.server.get_sensor(limit_addr)} belt={direction}"
            )

            if stop_evt and stop_evt.is_set():
                break
            if self.server.machine_state != "running":
                break

            if self.server.get_sensor(limit_addr):
                stable += 1
            else:
                stable = 0

            if stable >= DEBOUNCE_N:
                if direction == "forward":
                    self.server.set_actuator(BELT_FWD, False)
                else:
                    self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                if self.verbose:
                    print(
                        f"[turntable] limite estável ({direction}); esteira interna parada."
                    )
                break
            time.sleep(0.25)
            if (time.time() - t0) > timeout_s:
                # FAIL-SAFE: pare a direção ativa mesmo sem limite
                if self.verbose:
                    print(
                        f"[turntable] watcher timeout ({direction}); parando belt por segurança."
                    )
                if direction == "forward":
                    self.server.set_actuator(BELT_FWD, False)
                else:
                    self.server.set_actuator(BELT_REV, False)
                with self._lock:
                    self._turntable_belt = "stop"
                break

            time.sleep(0.02)

        self._belt_watching = False

    # =============== [ADD] API da TT2 (paralela à da TT1) ===============
    def set_turntable2_async(
        self,
        turn_on: bool | None,
        belt: str = "none",  # "forward" | "backward" | "stop"/"none"
        stop_limit: str | None = None,  # "front" | "back" | None
        belt_timeout_s: float = 1.0,
    ):
        if self.server.machine_state != "running":
            return
        threading.Thread(
            target=self._t2_set_turntable,
            args=(turn_on, (belt or "none").lower(), stop_limit, belt_timeout_s),
            name=f"TRUN-TT2-{turn_on}-{belt}-{stop_limit}",
            daemon=True,
        ).start()

    def _t2_set_turntable(
        self,
        turn_on: bool | None,
        belt: str,
        stop_limit: str | None,
        belt_timeout_s: float,
    ):
        # ----- ENDEREÇOS TT2 -----
        TURN_COIL = Inputs.Turntable2_turn

        # Ajuste se você tiver FWD/REV separados na TT2:
        BELT_FWD = (
            Inputs.Discharg_turn
            if hasattr(Inputs, "Turntable2_Esteira_SaidaEntrada")
            else Inputs.Discharg_turn
        )
        BELT_REV = (
            Inputs.Load_turn
            if hasattr(Inputs, "Turntable2_Esteira_EntradaSaida")
            else Inputs.Load_turn
        )

        # --- gira (se pedido) ---
        with self._lock:
            if turn_on is True:
                self.server.set_actuator(TURN_COIL, True)
                self._turntable2_turn = True
            elif turn_on is False:
                self.server.set_actuator(TURN_COIL, False)
                self._turntable2_turn = False

        # --- belt interno ---
        belt_to_watch = None
        if belt == "forward":
            try:
                self.server.set_actuator(BELT_REV, False)
            except Exception:
                pass
            self.server.set_actuator(BELT_FWD, True)
            with self._lock:
                self._turntable2_belt = "forward"
            belt_to_watch = "forward"

        elif belt == "backward":
            try:
                self.server.set_actuator(BELT_FWD, False)
            except Exception:
                pass
            self.server.set_actuator(BELT_REV, True)
            with self._lock:
                self._turntable2_belt = "backward"
            belt_to_watch = "backward"

        elif belt in ("stop", "none"):
            self.server.set_actuator(BELT_FWD, False)
            try:
                self.server.set_actuator(BELT_REV, False)
            except Exception:
                pass
            with self._lock:
                self._turntable2_belt = "stop"
            belt_to_watch = None

        # --- watcher dos limites da TT2 ---
        if stop_limit is None or belt_to_watch is None:
            self._stop_belt_watcher()
            if self.verbose:
                print(
                    f"[tt2] turn_on={turn_on} belt={belt} -> turn={getattr(self,'_turntable2_turn',None)} belt_state={getattr(self,'_turntable2_belt',None)}"
                )
            return

        if stop_limit.lower() == "front":
            limit_addr = Coils.Turntable2_FrontLimit
        elif stop_limit.lower() == "back":
            limit_addr = Coils.Turntable2_BackLimit
        else:
            if self.verbose:
                print(f"[tt2] stop_limit inválido: {stop_limit}")
            self._stop_belt_watcher()
            return

        self._start_belt_watcher(
            direction=belt_to_watch, limit_addr=limit_addr, timeout_s=belt_timeout_s
        )
        if self.verbose:
            print(
                f"[tt2] turn_on={turn_on} belt={belt} stop_limit={stop_limit} -> turn={getattr(self,'_turntable2_turn',None)} belt_state={getattr(self,'_turntable2_belt',None)}"
            )

    # =============== [END ADD] ===============
