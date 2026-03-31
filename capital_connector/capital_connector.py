# Capital.com API Client - Simple & Direct
# Basado en requests directo sin abstracciones innecesarias

import requests
import os
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Optional, List
from utils.utils import Utils

class CapitalConnector:
    """
    Cliente simple para Capital.com API.
    Interfaz directa con endpoints de Capital.com.
    """
    
    BASE_URL = "https://api-capital.backend-capital.com"
    
    def __init__(self):
        """Inicializa el conector cargando API_KEY del .env"""
        load_dotenv(find_dotenv())
        self.api_key = os.getenv("CAPITAL_API_KEY", "")
        
        if not self.api_key:
            raise Exception("CAPITAL_API_KEY no encontrada en .env")
        
        # Tokens de sesión (se obtienen con login)
        self.cst_token = None
        self.x_security_token = None
        
        print(f"{Utils.dateprint()} - Capital.com Connector inicializado")
    
    def _get_headers(self, cst: Optional[str] = None, x_token: Optional[str] = None) -> Dict:
        """
        Construye headers para las peticiones.
        
        Args:
            cst: Token CST de sesión (opcional, usa token almacenado si no se proporciona)
            x_token: Token X-SECURITY-TOKEN (opcional, usa token almacenado si no se proporciona)
            
        Returns:
            Dict con headers para request
        """
        headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Usar tokens proporcionados o los almacenados
        cst = cst or self.cst_token
        x_token = x_token or self.x_security_token
        
        if cst:
            headers["CST"] = cst
        if x_token:
            headers["X-SECURITY-TOKEN"] = x_token
        
        return headers
    
    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Realiza login en Capital.com y obtiene tokens de sesión.
        
        Args:
            email: Email de la cuenta (opcional, usa .env si no se proporciona)
            password: Contraseña (opcional, usa .env si no se proporciona)
            
        Returns:
            bool: True si login exitoso
        """
        # Usar credenciales del .env si no se proporcionan
        email = email or os.getenv("CAPITAL_API_USER")
        password = password or os.getenv("CAPITAL_API_PASSWORD")
        
        if not email or not password:
            raise Exception("Credenciales no encontradas. Configura CAPITAL_API_USER y CAPITAL_API_PASSWORD en .env")
        
        # Login con endpoint  /session (formato usado por training_bot)
        session_url = f"{self.BASE_URL}/api/v1/session"
        payload = {
            "identifier": email,
            "password": password
        }
        headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            print(f"{Utils.dateprint()} - Intentando login ({email}) con /session...")
            response = requests.post(session_url, json=payload, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error HTTP {response.status_code}")
                print(f"Respuesta: {response.text}")
                print(f"{Utils.dateprint()} - ⚠ Login falló, continuando sin tokens")
                return False

            self.cst_token = response.headers.get("CST")
            self.x_security_token = response.headers.get("X-SECURITY-TOKEN")

            print(f"{Utils.dateprint()} - Tokens obtenidos: CST={bool(self.cst_token)}, X-TOKEN={bool(self.x_security_token)}")

            if self.cst_token and self.x_security_token:
                print(f"{Utils.dateprint()} - Login exitoso en Capital.com")
                return True
            else:
                print(f"{Utils.dateprint()} - ⚠ Login ejecutado pero no devolvió CST/X-TOKEN")
                return False

        except Exception as e:
            print(f"{Utils.dateprint()} - Excepcion login: {repr(e)}")
            print(f"{Utils.dateprint()} - Continuando sin tokens")
            return False
    
    def place_order(self, epic: str, direction: str = "BUY", size: float = 1.0,
                   stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                   cst: Optional[str] = None, x_token: Optional[str] = None) -> Dict:
        """
        Abre una nueva posición.
        
        Args:
            epic: Código del instrumento (ej: 'CS.D.EURUSD.TODAYODL')
            direction: 'BUY' o 'SELL'
            size: Tamaño de la posición
            stop_loss: Nivel de stop loss (opcional)
            take_profit: Nivel de take profit (opcional)
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            
        Returns:
            Dict con resultado de la orden
        """
        url = f"{self.BASE_URL}/api/v1/positions"
        
        payload = {
            "epic": epic,
            "direction": direction.upper(),
            "size": size,
            "orderType": "MARKET"
        }
        
        if stop_loss:
            payload["stopLevel"] = stop_loss
        if take_profit:
            payload["limitLevel"] = take_profit
        
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error abriendo posición {epic}: {response.status_code} - {response.text}")
                return {}
            
            data = response.json()
            
            # Normalizar dealReference a dealId
            if isinstance(data, dict) and 'dealReference' in data and 'dealId' not in data:
                data['dealId'] = data['dealReference']
            
            print(f"{Utils.dateprint()} - Orden {direction} para {epic} de {size} unidades - Deal: {data.get('dealId', 'N/A')}")
            return data
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al abrir posición {epic}: {str(e)}")
            return {}
    
    def close_position(self, deal_id: str, cst: Optional[str] = None, 
                      x_token: Optional[str] = None) -> Dict:
        """
        Cierra una posición abierta usando su dealId.
        
        Args:
            deal_id: ID del deal a cerrar
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            
        Returns:
            Dict con resultado del cierre
        """
        url = f"{self.BASE_URL}/api/v1/positions/{deal_id}"
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.delete(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error cerrando posición {deal_id}: {response.status_code} - {response.text}")
                return {}
            
            print(f"{Utils.dateprint()} - Posición {deal_id} cerrada exitosamente")
            return response.json() if response.content else {"status": "closed"}
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al cerrar posición {deal_id}: {str(e)}")
            return {}
    
    def get_account_balance(self, cst: Optional[str] = None, x_token: Optional[str] = None,
                           account_name: Optional[str] = None) -> Optional[float]:
        """
        Consulta el saldo/disponible de la cuenta.
        
        Devuelve el `available` si está disponible, en caso contrario `balance`.
        
        Args:
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            account_name: Nombre de cuenta específica (opcional)
            
        Returns:
            Float con el balance, o None si error
        """
        url = f"{self.BASE_URL}/api/v1/accounts"
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error consultando balance: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Estructura esperada: {"accounts":[{...,"balance":{"balance":X,"available":Y},...}]}
            if isinstance(data, dict) and "accounts" in data and isinstance(data["accounts"], list):
                chosen = None
                
                # Buscar por nombre si se especifica
                if account_name:
                    for acct in data["accounts"]:
                        if acct.get("accountName") == account_name:
                            chosen = acct
                            break
                
                # Si no se eligió, buscar la marca como preferida
                if chosen is None:
                    for acct in data["accounts"]:
                        if acct.get("preferred"):
                            chosen = acct
                            break
                
                # Última opción: primera de la lista
                if chosen is None and data["accounts"]:
                    chosen = data["accounts"][0]
                
                if chosen:
                    bal = chosen.get("balance", {})
                    # Preferir disponible sobre balance
                    if isinstance(bal, dict):
                        available = bal.get("available")
                        if available is not None:
                            return float(available)
                        return float(bal.get("balance", 0))
                    return float(bal)
            
            # Casos triviales: lista plana
            if isinstance(data, list) and data:
                item = data[0]
                if isinstance(item, dict):
                    for key in ("equity", "balance", "cash", "available"):
                        if key in item:
                            return float(item[key])
            
            # Búsqueda directa en dict
            if isinstance(data, dict):
                for key in ("equity", "balance", "cash", "available"):
                    if key in data:
                        return float(data[key])
            
            return None
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al consultar balance: {str(e)}")
            return None
    
    def get_prices(self, epic: str, resolution: str = "MINUTE", num_points: int = 100,
                  cst: Optional[str] = None, x_token: Optional[str] = None) -> Dict:
        """
        Obtiene datos OHLC de un instrumento.
        
        Args:
            epic: Código del instrumento
            resolution: Timeframe (MINUTE, HOUR, DAY, etc.)
            num_points: Número de velas a obtener
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            
        Returns:
            Dict con datos de precios
        """
        url = f"{self.BASE_URL}/api/v1/prices/{epic}?resolution={resolution}&max={num_points}"
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error obteniendo precios {epic}: {response.status_code} - {response.text}")
                return {}
            
            return response.json()
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al obtener precios {epic}: {str(e)}")
            return {}
    
    def get_positions(self, cst: Optional[str] = None, x_token: Optional[str] = None) -> List[Dict]:
        """
        Obtiene las posiciones abiertas.
        
        Args:
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            
        Returns:
            Lista de posiciones abiertas
        """
        url = f"{self.BASE_URL}/api/v1/positions"
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error obteniendo posiciones: {response.status_code}")
                return []
            
            data = response.json()
            return data.get("positions", []) if isinstance(data, dict) else data
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al obtener posiciones: {str(e)}")
            return []
    
    def search_instruments(self, query: str, cst: Optional[str] = None, 
                          x_token: Optional[str] = None) -> List[Dict]:
        """
        Busca instrumentos por término.
        
        Args:
            query: Término de búsqueda
            cst: Token CST (opcional)
            x_token: Token X-SECURITY-TOKEN (opcional)
            
        Returns:
            Lista de instrumentos encontrados
        """
        url = f"{self.BASE_URL}/api/v1/markets?searchTerm={query}"
        headers = self._get_headers(cst, x_token)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"{Utils.dateprint()} - Error buscando \"{query}\": {response.status_code}")
                return []
            
            data = response.json()
            return data.get("markets", []) if isinstance(data, dict) else data
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Excepción al buscar \"{query}\": {str(e)}")
            return []
        return account_name in self.sessions
