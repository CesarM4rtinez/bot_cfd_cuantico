# QUANTDEMY - Account Manager para Capital.com
# Gestor de múltiples cuentas de trading

from typing import Dict, List, Optional
from datetime import datetime
from utils.utils import Utils

class AccountManager:
    """
    Gestor centralizado para manejar múltiples cuentas de trading en Capital.com.
    Proporciona una interfaz unificada para operar con varias cuentas simultáneamente.
    """
    
    def __init__(self, capital_connector):
        """
        Inicializa el gestor de cuentas.
        
        Args:
            capital_connector (CapitalConnector): Instancia del conector de Capital.com
        """
        self.connector = capital_connector
        self.active_accounts: Dict[str, dict] = {}
        self.account_stats: Dict[str, dict] = {}
        
        # Cargar información de todas las cuentas autenticadas
        self._load_accounts()
    
    def _load_accounts(self) -> None:
        """
        Carga información de todas las cuentas autenticadas.
        """
        for account_name in self.connector.get_available_accounts():
            try:
                account_info = self.connector.get_account_info(account_name)
                self.active_accounts[account_name] = account_info
                
                # Inicializar estadísticas
                self.account_stats[account_name] = {
                    'total_orders': 0,
                    'successful_orders': 0,
                    'failed_orders': 0,
                    'total_pnl': 0.0,
                    'last_order_time': None
                }
                
                print(f"{Utils.dateprint()} - Cuenta '{account_name}' cargada exitosamente")
                
            except Exception as e:
                print(f"{Utils.dateprint()} - Error cargando cuenta '{account_name}': {str(e)}")
    
    def get_accounts(self) -> List[str]:
        """
        Retorna lista de todas las cuentas activas.
        
        Returns:
            List[str]: Nombres de las cuentas
        """
        return list(self.active_accounts.keys())
    
    def get_account_info(self, account_name: str) -> Dict:
        """
        Obtiene información detallada de una cuenta.
        
        Args:
            account_name (str): Nombre de la cuenta
            
        Returns:
            Dict: Información de la cuenta
        """
        if account_name not in self.active_accounts:
            raise ValueError(f"Cuenta '{account_name}' no encontrada")
        
        return self.active_accounts[account_name]
    
    def get_account_balance(self, account_name: str) -> float:
        """
        Obtiene el balance actual de una cuenta.
        
        Args:
            account_name (str): Nombre de la cuenta
            
        Returns:
            float: Balance de la cuenta
        """
        account_info = self.get_account_info(account_name)
        return account_info.get('balance', 0.0)
    
    def get_account_equity(self, account_name: str) -> float:
        """
        Obtiene el equity actual de una cuenta.
        
        Args:
            account_name (str): Nombre de la cuenta
            
        Returns:
            float: Equity de la cuenta
        """
        account_info = self.get_account_info(account_name)
        return account_info.get('equity', 0.0)
    
    def get_all_account_balances(self) -> Dict[str, float]:
        """
        Obtiene balances de todas las cuentas.
        
        Returns:
            Dict[str, float]: Diccionario con balances por cuenta
        """
        balances = {}
        for account_name in self.get_accounts():
            balances[account_name] = self.get_account_balance(account_name)
        return balances
    
    def get_total_balance(self) -> float:
        """
        Obtiene el balance total de todas las cuentas.
        
        Returns:
            float: Suma de todos los balances
        """
        total = sum(self.get_all_account_balances().values())
        return total
    
    def get_open_positions(self, account_name: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Obtiene posiciones abiertas de una o todas las cuentas.
        
        Args:
            account_name (str, optional): Nombre de la cuenta. Si es None, retorna todas.
            
        Returns:
            Dict[str, List[Dict]]: Diccionario con posiciones por cuenta
        """
        positions = {}
        
        accounts_to_query = [account_name] if account_name else self.get_accounts()
        
        for acc in accounts_to_query:
            try:
                positions[acc] = self.connector.get_open_positions(acc)
            except Exception as e:
                print(f"{Utils.dateprint()} - Error obteniendo posiciones de {acc}: {str(e)}")
                positions[acc] = []
        
        return positions
    
    def get_total_open_positions(self) -> int:
        """
        Obtiene el número total de posiciones abiertas en todas las cuentas.
        
        Returns:
            int: Total de posiciones abiertas
        """
        positions = self.get_open_positions()
        total = sum(len(pos) for pos in positions.values())
        return total
    
    def place_order_on_account(self, account_name: str, epic: str, direction: str, 
                               size: float, order_type: str = "MARKET", 
                               limit_level: float = None, 
                               stop_level: float = None) -> Dict:
        """
        Coloca una orden en una cuenta específica.
        
        Args:
            account_name (str): Nombre de la cuenta
            epic (str): Código del instrumento
            direction (str): Dirección (BUY/SELL)
            size (float): Tamaño de la posición
            order_type (str): Tipo de orden
            limit_level (float): Nivel de límite
            stop_level (float): Nivel de stop
            
        Returns:
            Dict: Resultado de la orden
        """
        if account_name not in self.active_accounts:
            raise ValueError(f"Cuenta '{account_name}' no encontrada")
        
        try:
            result = self.connector.place_order(
                epic=epic,
                direction=direction,
                size=size,
                order_type=order_type,
                limit_level=limit_level,
                stop_level=stop_level,
                account_name=account_name
            )
            
            # Actualizar estadísticas
            self.account_stats[account_name]['total_orders'] += 1
            self.account_stats[account_name]['successful_orders'] += 1
            self.account_stats[account_name]['last_order_time'] = datetime.now()
            
            return result
            
        except Exception as e:
            self.account_stats[account_name]['total_orders'] += 1
            self.account_stats[account_name]['failed_orders'] += 1
            raise
    
    def place_order_on_all_accounts(self, epic: str, direction: str, 
                                   size: float, order_type: str = "MARKET",
                                   limit_level: float = None,
                                   stop_level: float = None) -> Dict[str, Dict]:
        """
        Coloca una orden en todas las cuentas activas.
        
        Args:
            epic (str): Código del instrumento
            direction (str): Dirección (BUY/SELL)
            size (float): Tamaño de la posición
            order_type (str): Tipo de orden
            limit_level (float): Nivel de límite
            stop_level (float): Nivel de stop
            
        Returns:
            Dict[str, Dict]: Resultados de órdenes por cuenta
        """
        results = {}
        
        for account_name in self.get_accounts():
            try:
                results[account_name] = self.place_order_on_account(
                    account_name=account_name,
                    epic=epic,
                    direction=direction,
                    size=size,
                    order_type=order_type,
                    limit_level=limit_level,
                    stop_level=stop_level
                )
                print(f"{Utils.dateprint()} - Orden colocada exitosamente en {account_name}")
            except Exception as e:
                print(f"{Utils.dateprint()} - Error colocando orden en {account_name}: {str(e)}")
                results[account_name] = {"error": str(e)}
        
        return results
    
    def close_position(self, account_name: str, position_id: str) -> Dict:
        """
        Cierra una posición en una cuenta específica.
        
        Args:
            account_name (str): Nombre de la cuenta
            position_id (str): ID de la posición
            
        Returns:
            Dict: Resultado del cierre
        """
        if account_name not in self.active_accounts:
            raise ValueError(f"Cuenta '{account_name}' no encontrada")
        
        return self.connector.close_position(position_id, account_name)
    
    def get_account_statistics(self, account_name: Optional[str] = None) -> Dict:
        """
        Obtiene estadísticas de trading de una o todas las cuentas.
        
        Args:
            account_name (str, optional): Nombre de la cuenta
            
        Returns:
            Dict: Estadísticas de trading
        """
        if account_name:
            if account_name not in self.account_stats:
                raise ValueError(f"Cuenta '{account_name}' no encontrada")
            return self.account_stats[account_name]
        
        return self.account_stats
    
    def print_account_summary(self) -> None:
        """
        Imprime un resumen de todas las cuentas y sus estadísticas.
        """
        print("\n" + "="*60)
        print("RESUMEN DE CUENTAS - CAPITAL.COM")
        print("="*60)
        
        for account_name in self.get_accounts():
            try:
                balance = self.get_account_balance(account_name)
                equity = self.get_account_equity(account_name)
                positions = len(self.connector.get_open_positions(account_name))
                stats = self.account_stats[account_name]
                
                print(f"\nCuenta: {account_name}")
                print(f"  Balance: ${balance:,.2f}")
                print(f"  Equity: ${equity:,.2f}")
                print(f"  Posiciones Abiertas: {positions}")
                print(f"  Órdenes Totales: {stats['total_orders']}")
                print(f"  Órdenes Exitosas: {stats['successful_orders']}")
                print(f"  Órdenes Fallidas: {stats['failed_orders']}")
                
            except Exception as e:
                print(f"\nCuenta: {account_name}")
                print(f"  Error obteniendo información: {str(e)}")
        
        print("\n" + "="*60)
        print(f"Balance Total: ${self.get_total_balance():,.2f}")
        print(f"Posiciones Totales: {self.get_total_open_positions()}")
        print("="*60 + "\n")
