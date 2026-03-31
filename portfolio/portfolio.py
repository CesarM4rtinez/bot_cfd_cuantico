# QUANTDEMY - Trading con Python y Capital.com: Framework adaptado

from typing import Dict, Optional, List
from utils.utils import Utils

class Portfolio():
    """
    Portfolio manager adaptado para Capital.com.
    Gestiona posiciones abiertas a través del CapitalConnector.
    """

    def __init__(self, capital_connector=None, magic_number: int = None):
        """
        Inicializa el Portfolio.

        Args:
            capital_connector: Instancia del CapitalConnector de Capital.com
            magic_number (int): Número mágico para identificar la estrategia (opcional)
        """
        self.capital_connector = capital_connector
        self.magic = magic_number
        self.positions_cache: List[Dict] = []

    def set_capital_connector(self, capital_connector) -> None:
        """
        Establece el CapitalConnector después de la inicialización.
        
        Args:
            capital_connector: Instancia del CapitalConnector
        """
        self.capital_connector = capital_connector

    def get_open_positions(self, cst: Optional[str] = None, x_token: Optional[str] = None) -> List[Dict]:
        """
        Obtiene las posiciones abiertas.

        Args:
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            List[Dict]: Lista de posiciones abiertas
        """
        if not self.capital_connector:
            raise Exception("CapitalConnector no ha sido configurado")
        
        try:
            positions = self.capital_connector.get_positions(cst=cst, x_token=x_token)
            self.positions_cache = positions
            return positions
        except Exception as e:
            print(f"{Utils.dateprint()} - Error obteniendo posiciones: {str(e)}")
            return []

    def get_strategy_open_positions(self, cst: Optional[str] = None, x_token: Optional[str] = None) -> List[Dict]:
        """
        Obtiene las posiciones abiertas por la estrategia.
        Con Capital.com, retorna todas las posiciones ya que no hay magic number.

        Args:
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            List[Dict]: Posiciones de la estrategia
        """
        # En Capital.com no existe el concepto de "magic number" como en MT5
        # Por lo tanto, simplemente retornamos todas las posiciones
        return self.get_open_positions(cst=cst, x_token=x_token)

    def get_number_of_open_positions_by_symbol(self, symbol: str, 
                                               cst: Optional[str] = None,
                                               x_token: Optional[str] = None) -> Dict[str, int]:
        """
        Obtiene el número de posiciones abiertas por símbolo.

        Args:
            symbol (str): Símbolo a consultar
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            Dict[str, int]: Conteo de posiciones LONG, SHORT y TOTAL
        """
        positions = self.get_open_positions(cst=cst, x_token=x_token)
        
        longs = 0
        shorts = 0
        
        for pos in positions:
            if pos.get('epic') == symbol or pos.get('symbol') == symbol:
                if pos.get('direction') == 'BUY':
                    longs += 1
                else:
                    shorts += 1
        
        return {"LONG": longs, "SHORT": shorts, "TOTAL": longs + shorts}

    def get_number_of_strategy_open_positions_by_symbol(self, symbol: str,
                                                       cst: Optional[str] = None,
                                                       x_token: Optional[str] = None) -> Dict[str, int]:
        """
        Obtiene el número de posiciones abiertas por la estrategia para un símbolo.

        Args:
            symbol (str): Símbolo a consultar
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            Dict[str, int]: Conteo de posiciones LONG, SHORT y TOTAL
        """
        # En Capital.com es equivalente a get_number_of_open_positions_by_symbol
        return self.get_number_of_open_positions_by_symbol(symbol, cst=cst, x_token=x_token)

    def get_total_open_positions_count(self, cst: Optional[str] = None, 
                                       x_token: Optional[str] = None) -> int:
        """
        Obtiene el número total de posiciones abiertas.

        Args:
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            int: Número total de posiciones abiertas
        """
        positions = self.get_open_positions(cst=cst, x_token=x_token)
        return len(positions)

    def get_account_exposure(self, cst: Optional[str] = None, 
                             x_token: Optional[str] = None) -> float:
        """
        Obtiene la exposición total de la cuenta.

        Args:
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            float: Exposición total
        """
        positions = self.get_open_positions(cst=cst, x_token=x_token)
        total_exposure = 0.0
        
        for pos in positions:
            total_exposure += pos.get('dealSize', 0) * pos.get('currentPrice', 0)
        
        return total_exposure

    def close_position(self, position_id: str, cst: Optional[str] = None, 
                      x_token: Optional[str] = None) -> Dict:
        """
        Cierra una posición específica.

        Args:
            position_id (str): ID de la posición a cerrar
            cst (str, optional): Token CST de sesión
            x_token (str, optional): Token X-SECURITY-TOKEN

        Returns:
            Dict: Resultado del cierre
        """
        if not self.capital_connector:
            raise Exception("CapitalConnector no ha sido configurado")
        
        try:
            result = self.capital_connector.close_position(position_id, cst=cst, x_token=x_token)
            print(f"{Utils.dateprint()} - Posición {position_id} cerrada")
            return result
        except Exception as e:
            print(f"{Utils.dateprint()} - Error cerrando posición: {str(e)}")
            raise