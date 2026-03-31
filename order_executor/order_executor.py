# QUANTDEMY - Trading con Python y Capital.com: Framework adaptado

from portfolio.portfolio import Portfolio
from events.events import OrderEvent, ExecutionEvent, PlacedPendingOrderEvent, SignalType
from utils.utils import Utils
import pandas as pd
from queue import Queue 
import time
from datetime import datetime
from typing import Optional, Dict

class OrderExecutor():

    def __init__(self, events_queue: Queue, portfolio: Portfolio, 
                 capital_connector=None, account_name: str = None) -> None:
        """
        Inicializa el OrderExecutor.

        Args:
            events_queue (Queue): Cola de eventos
            portfolio (Portfolio): Objeto Portfolio
            capital_connector: Instancia del CapitalConnector de Capital.com
            account_name (str): Nombre de la cuenta (requerido)
        """
        self.events_queue = events_queue
        self.PORTFOLIO = portfolio
        self.capital_connector = capital_connector
        self.account_name = account_name
        self.order_cache: Dict[str, dict] = {}  # Cache de órdenes ejecutadas

    def set_capital_connector(self, capital_connector) -> None:
        """
        Establece el CapitalConnector.
        
        Args:
            capital_connector: Instancia del CapitalConnector
        """
        self.capital_connector = capital_connector

    def execute_order(self, order_event: OrderEvent) -> None:
        """
        Ejecuta una orden.

        Args:
            order_event (OrderEvent): Evento de orden a ejecutar
        """
        if not self.capital_connector:
            raise Exception("CapitalConnector no ha sido configurado")
        if not self.account_name:
            raise Exception("Nombre de cuenta no configurado en OrderExecutor")
        
        # Evaluar tipo de orden
        if order_event.target_order == "MARKET":
            self._execute_market_order(order_event)
        else:
            self._send_pending_order(order_event)

    def _execute_market_order(self, order_event: OrderEvent) -> None:
        """
        Ejecuta una orden a mercado.

        Args:
            order_event (OrderEvent): Evento de orden
        """
        try:
            # Obtener el EPIC del símbolo
            epic = self._get_epic_from_symbol(order_event.symbol)
            
            if not epic:
                print(f"{Utils.dateprint()} - No se pudo obtener EPIC para {order_event.symbol}")
                return
            
            # Preparar parámetros de la orden
            direction = "BUY" if order_event.signal == "BUY" else "SELL"
            
            # Ejecutar la orden
            result = self.capital_connector.place_order(
                epic=epic,
                direction=direction,
                size=order_event.volume,
                stop_loss=order_event.sl if order_event.sl > 0 else None,
                take_profit=order_event.tp if order_event.tp > 0 else None
            )
            
            if result and "dealId" in result:
                print(f"{Utils.dateprint()} - Market Order {direction} para {order_event.symbol} de {order_event.volume} unidades ejecutada - Deal ID: {result.get('dealId')}")
                
                # Crear y enviar execution event
                self._create_and_put_execution_event(result, order_event)
                
            elif result and "error" not in result:
                # Orden ejecutada sin dealId
                print(f"{Utils.dateprint()} - Market Order {direction} para {order_event.symbol} enviada")
                self._create_and_put_execution_event(result, order_event)
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error ejecutando Market Order para {order_event.symbol}: {str(e)}")

    def _send_pending_order(self, order_event: OrderEvent) -> None:
        """
        Coloca una orden pendiente (STOP o LIMIT).

        Args:
            order_event (OrderEvent): Evento de orden
        """
        try:
            epic = self._get_epic_from_symbol(order_event.symbol)
            
            if not epic:
                print(f"{Utils.dateprint()} - No se pudo obtener EPIC para {order_event.symbol}")
                return
            
            direction = "BUY" if order_event.signal == "BUY" else "SELL"
            
            # Capital.com maneja órdenes pendientes con LIMIT y STOP
            order_type = order_event.target_order.upper()  # "LIMIT" o "STOP"
            
            # Para órdenes pendientes, Capital.com no tiene soporte directo
            # Por ahora solo se ejecutan órdenes MARKET
            print(f"{Utils.dateprint()} - Órdenes pendientes ({order_type}) no están soportadas en Capital.com. Solo órdenes MARKET.")
            return
            
            if result and "dealId" in result:
                print(f"{Utils.dateprint()} - Pending Order {direction} {order_type} para {order_event.symbol} de {order_event.volume} unidades colocada en {order_event.target_price}")
                
                # Crear evento de orden pendiente colocada
                self._create_and_put_placed_pending_order_event(order_event)
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error colocando orden pendiente: {str(e)}")

    def close_position(self, account_name: str, position_id: str) -> None:
        """
        Cierra una posición.

        Args:
            account_name (str): Nombre de la cuenta
            position_id (str): ID de la posición a cerrar
        """
        try:
            if not self.account_manager:
                raise Exception("AccountManager no configurado")
            
            result = self.account_manager.close_position(account_name, position_id)
            
            print(f"{Utils.dateprint()} - Posición {position_id} cerrada en {account_name}")
            
        except Exception as e:
            print(f"{Utils.dateprint()} - Error cerrando posición: {str(e)}")

    def close_strategy_long_positions_by_symbol(self, symbol: str, account_name: Optional[str] = None) -> None:
        """
        Cierra todas las posiciones LONG de un símbolo.

        Args:
            symbol (str): Símbolo
            account_name (str, optional): Cuenta específica
        """
        try:
            positions = self.PORTFOLIO.get_open_positions(account_name)
            
            for acc, pos_list in positions.items():
                for pos in pos_list:
                    if pos.get('epic') == symbol and pos.get('direction') == 'BUY':
                        self.close_position(acc, pos.get('positionId'))
                        
        except Exception as e:
            print(f"{Utils.dateprint()} - Error cerrando posiciones LONG: {str(e)}")

    def close_strategy_short_positions_by_symbol(self, symbol: str, account_name: Optional[str] = None) -> None:
        """
        Cierra todas las posiciones SHORT de un símbolo.

        Args:
            symbol (str): Símbolo
            account_name (str, optional): Cuenta específica
        """
        try:
            positions = self.PORTFOLIO.get_open_positions(account_name)
            
            for acc, pos_list in positions.items():
                for pos in pos_list:
                    if pos.get('epic') == symbol and pos.get('direction') == 'SELL':
                        self.close_position(acc, pos.get('positionId'))
                        
        except Exception as e:
            print(f"{Utils.dateprint()} - Error cerrando posiciones SHORT: {str(e)}")

    def _create_and_put_placed_pending_order_event(self, order_event: OrderEvent) -> None:
        """
        Crea un evento de orden pendiente colocada.

        Args:
            order_event (OrderEvent): Evento de orden original
        """
        placed_pending_order_event = PlacedPendingOrderEvent(
            symbol=order_event.symbol,
            signal=order_event.signal,
            target_order=order_event.target_order,
            target_price=order_event.target_price,
            magic_number=order_event.magic_number,
            sl=order_event.sl,
            tp=order_event.tp,
            volume=order_event.volume
        )
        
        self.events_queue.put(placed_pending_order_event)

    def _create_and_put_execution_event(self, order_result: dict, order_event: OrderEvent) -> None:
        """
        Crea un evento de ejecución.

        Args:
            order_result (dict): Resultado de la orden
            order_event (OrderEvent): Evento de orden original
        """
        # Capital.com proporciona el precio de ejecución en el resultado
        fill_price = order_result.get('level', order_result.get('price', 0))
        fill_time = datetime.now()
        
        # Crear evento de ejecución
        execution_event = ExecutionEvent(
            symbol=order_event.symbol,
            signal=order_event.signal,
            fill_price=fill_price,
            fill_time=fill_time,
            volume=order_event.volume
        )
        
        # Colocar evento en la cola
        self.events_queue.put(execution_event)

    def _get_epic_from_symbol(self, symbol: str) -> Optional[str]:
        """
        Obtiene el EPIC de un símbolo.

        Args:
            symbol (str): Símbolo

        Returns:
            Optional[str]: EPIC correspondiente
        """
        # Mapeo básico - puede extenderse según necesidad
        epic_mapping = {
            'EURUSD': 'EURUSD',
            'GBPUSD': 'GBPUSD',
            'USDJPY': 'USDJPY',
            'AUDUSD': 'AUDUSD',
            'USDCAD': 'USDCAD',
            'NZDUSD': 'NZDUSD',
            'USDCHF': 'USDCHF',
            'EURGBP': 'EURGBP',
            'EURJPY': 'EURJPY',
            'GBPJPY': 'GBPJPY',
            'BTCUSD': 'BTCUSD',
            'ETHUSD': 'ETHUSD',
            'XAUUSD': 'GOLD',
            'XAGUSD': 'SILVER',
            'US30': 'US30',
            'US100': 'US100',
            'SILVER': 'SILVER',
            'GOLD': 'GOLD',
            'OIL_BRENT': 'OIL_BRENT',
            'XRPUSD': 'XRPUSD',
            'SOLUSD': 'SOLUSD',
            'DXY': 'DXY',
            'NAS100': 'US100',  # NAS100 usa EPIC US100 en Capital.com
        }
        
        return epic_mapping.get(symbol)
