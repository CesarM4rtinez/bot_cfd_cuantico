# QUANTDEMY - Trading con Python y Capital.com: Framework adaptado

from utils.utils import Utils
import pandas as pd
from typing import Dict, Optional
from datetime import datetime
from events.events import DataEvent
from queue import Queue


class DataProvider():

    def __init__(self, events_queue: Queue, capital_connector=None, 
                 symbol_list: list = None, epic_mapping: Dict[str, str] = None, 
                 timeframe: str = "MINUTE_1"):
        """
        Inicializa el DataProvider.

        Args:
            events_queue (Queue): Cola de eventos
            capital_connector: Instancia del CapitalConnector
            symbol_list (list): Lista de símbolos (nombres amigables)
            epic_mapping (Dict[str, str]): Mapeo de símbolos a EPICs de Capital.com
            timeframe (str): Marco temporal para datos
        """
        self.events_queue = events_queue
        self.connector = capital_connector
        self.symbols: list = symbol_list or []
        self.timeframe: str = timeframe
        
        # Mapeo de símbolos a EPICs de Capital.com
        # Ejemplo: {'EURUSD': 'CS.D.EURUSD.TODAYODL', 'GBPUSD': 'CS.D.GBPUSD.TODAYODL'}
        self.epic_mapping: Dict[str, str] = epic_mapping or self._build_default_epic_mapping()
        
        # Diccionario para guardar el último datetime visto de cada símbolo
        self.last_bar_datetime: Dict[str, datetime] = {symbol: datetime.min for symbol in self.symbols}

    def set_connector(self, capital_connector) -> None:
        """
        Establece el CapitalConnector después de la inicialización.
        
        Args:
            capital_connector: Instancia del CapitalConnector
        """
        self.connector = capital_connector

    def _build_default_epic_mapping(self) -> Dict[str, str]:
        """
        Construye un mapeo default de símbolos a EPICs.
        
        Returns:
            Dict[str, str]: Mapeo de símbolos a EPICs
        """
        # Mapeo default común para pares de divisas
        default_mapping = {
            'EURUSD': 'CS.D.EURUSD.TODAYODL',
            'GBPUSD': 'CS.D.GBPUSD.TODAYODL',
            'USDJPY': 'CS.D.USDJPY.TODAYODL',
            'AUDUSD': 'CS.D.AUDUSD.TODAYODL',
            'USDCAD': 'CS.D.USDCAD.TODAYODL',
            'NZDUSD': 'CS.D.NZDUSD.TODAYODL',
            'USDCHF': 'CS.D.USDCHF.TODAYODL',
        }
        return {k: v for k, v in default_mapping.items() if k in self.symbols}

    def _map_timeframes(self, timeframe: str) -> str:
        """
        Mapea timeframes de string a formato Capital.com.

        Args:
            timeframe (str): Marco temporal

        Returns:
            str: Marco temporal en formato Capital.com
        """
        timeframe_mapping = {
            '1min': 'MINUTE_1',
            '5min': 'MINUTE_5',
            '10min': 'MINUTE_10',
            '15min': 'MINUTE_15',
            '30min': 'MINUTE_30',
            '1h': 'HOUR',
            '4h': 'FOUR_HOUR',
            '1d': 'DAY',
            '1w': 'WEEK',
            '1M': 'MONTH',
        }
        
        return timeframe_mapping.get(timeframe, timeframe)

    def get_latest_closed_bar(self, symbol: str, timeframe: Optional[str] = None) -> pd.Series:
        """
        Obtiene la última vela cerrada para un símbolo.

        Args:
            symbol (str): Símbolo a consultar
            timeframe (str, optional): Marco temporal

        Returns:
            pd.Series: Datos de la última vela
        """
        if not self.connector:
            print(f"{Utils.dateprint()} - CapitalConnector no configurado")
            return pd.Series()
        
        # Usar timeframe default si no se especifica
        tf = self._map_timeframes(timeframe or self.timeframe)
        
        # Obtener el EPIC del símbolo
        epic = self.epic_mapping.get(symbol)
        if not epic:
            print(f"{Utils.dateprint()} - Símbolo {symbol} no tiene EPIC mapeado")
            return pd.Series()
        
        try:
            # Obtener últimas 2 velas (para asegurar que tenemos la cerrada)
            bars_data = self.connector.get_prices(epic, resolution=tf, num_points=2)

            if not bars_data:
                return pd.Series()

            # Capital.com devuelve {"prices": [...]}
            if isinstance(bars_data, dict):
                prices = bars_data.get('prices') or bars_data.get('candles') or []
            elif isinstance(bars_data, list):
                prices = bars_data
            else:
                prices = []

            if not prices:
                return pd.Series()

            latest_bar = prices[-1]  # La última vela

            # Convertir a DataFrame estándar
            bar_series = pd.Series({
                'open': latest_bar.get('openPrice', {}).get('bid', 0),
                'high': latest_bar.get('highPrice', {}).get('bid', 0),
                'low': latest_bar.get('lowPrice', {}).get('bid', 0),
                'close': latest_bar.get('closePrice', {}).get('bid', 0),
                'volume': latest_bar.get('lastTradedVolume', latest_bar.get('volume', 0)),
                'time': pd.to_datetime(latest_bar.get('snapshotTime', datetime.now()))
            })
            
            return bar_series
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error obteniendo datos de {symbol}: {str(e)}")
            return pd.Series()

    def get_latest_closed_bars(self, symbol: str, num_bars: int = 20, 
                               timeframe: Optional[str] = None) -> pd.DataFrame:
        """
        Obtiene múltiples velas cerradas para un símbolo.

        Args:
            symbol (str): Símbolo a consultar
            num_bars (int): Número de velas a obtener
            timeframe (str, optional): Marco temporal

        Returns:
            pd.DataFrame: DataFrame con datos OHLC
        """
        if not self.connector:
            print(f"{Utils.dateprint()} - CapitalConnector no configurado")
            return pd.DataFrame()
        
        tf = self._map_timeframes(timeframe or self.timeframe)
        epic = self.epic_mapping.get(symbol)
        
        if not epic:
            print(f"{Utils.dateprint()} - Símbolo {symbol} no tiene EPIC mapeado")
            return pd.DataFrame()
        
        try:
            bars_data = self.connector.get_prices(epic, resolution=tf, num_points=num_bars)

            if not bars_data:
                return pd.DataFrame()

            # Capital.com devuelve {"prices": [...]}
            if isinstance(bars_data, dict):
                bars = bars_data.get('prices') or bars_data.get('candles') or []
            elif isinstance(bars_data, list):
                bars = bars_data
            else:
                bars = []

            if not bars:
                return pd.DataFrame()

            # Convertir datos a DataFrame
            bars_list = []
            for bar in bars:
                bars_list.append({
                    'time': pd.to_datetime(bar.get('snapshotTime', datetime.now())),
                    'open': bar.get('openPrice', {}).get('bid', 0),
                    'high': bar.get('highPrice', {}).get('bid', 0),
                    'low': bar.get('lowPrice', {}).get('bid', 0),
                    'close': bar.get('closePrice', {}).get('bid', 0),
                    'volume': bar.get('lastTradedVolume', bar.get('volume', 0)),
                    'bid': bar.get('closePrice', {}).get('bid', 0),
                    'ask': bar.get('closePrice', {}).get('ask', 0),
                })
            
            df = pd.DataFrame(bars_list)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error obteniendo velas de {symbol}: {str(e)}")
            return pd.DataFrame()

    def get_latest_tick(self, symbol: str) -> dict:
        """
        Obtiene el último tick para un símbolo.

        Args:
            symbol (str): Símbolo a consultar

        Returns:
            dict: Información del último tick
        """
        try:
            bar = self.get_latest_closed_bar(symbol)
            
            if bar.empty:
                return {}
            
            return {
                'bid': bar.get('bid', bar['close']),
                'ask': bar.get('ask', bar['close']),
                'last': bar['close'],
                'time': bar.get('time', datetime.now())
            }
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error obteniendo tick de {symbol}: {str(e)}")
            return {}
    
    def check_for_new_data(self) -> None:
        """
        Verifica si hay datos nuevos para cada símbolo y añade eventos a la cola.
        """
        for symbol in self.symbols:
            try:
                latest_bar = self.get_latest_closed_bar(symbol)
                
                if latest_bar.empty:
                    continue
                
                bar_time = latest_bar.get('time', datetime.now())
                
                # Si la vela es más nueva que la última vista, agregar evento
                if bar_time > self.last_bar_datetime[symbol]:
                    self.last_bar_datetime[symbol] = bar_time
                    data_event = DataEvent(symbol=symbol, data=latest_bar)
                    self.events_queue.put(data_event)
                    print(f"{Utils.dateprint()} - Nuevo DATA EVENT para {symbol}: Close={latest_bar.get('close', 0)}")
                    
            except Exception as e:
                print(f"{Utils.dateprint()} - Error verificando datos para {symbol}: {str(e)}")
                continue
