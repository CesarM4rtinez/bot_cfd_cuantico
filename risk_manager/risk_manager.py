# QUANTDEMY - https://quantdemy.com - Trading con Python y MetaTrader 5: Crea tu Propio Framework

from .interfaces.risk_manager_interface import IRiskManager
from .properties.risk_manager_properties import BaseRiskProps, MaxLeverageFactorRiskProps
from .risk_managers.max_leverage_factor_risk_manager import MaxLeverageFactorRiskManager
from data_provider.data_provider import DataProvider
from portfolio.portfolio import Portfolio
from events.events import SizingEvent, OrderEvent
from utils.utils import Utils
from queue import Queue

class RiskManager(IRiskManager):
    
    def __init__(self, events_queue: Queue, data_provider: DataProvider, portfolio: Portfolio, risk_properties: BaseRiskProps):
        """
        Initializes a RiskManager object.

        Args:
            events_queue (Queue): The queue for receiving events.
            data_provider (DataProvider): The data provider for retrieving market data.
            portfolio (Portfolio): The portfolio object for managing positions and balances.
            risk_properties (BaseRiskProps): The risk properties object for configuring risk management.

        Returns:
            None
        """
        self.events_queue = events_queue
        self.DATA_PROVIDER = data_provider
        self.PORTFOLIO = portfolio
        self.capital_connector = getattr(self.PORTFOLIO, 'capital_connector', None)
        
        # Información de símbolos para Capital.com
        self.contract_sizes = {
            'EURUSD': 100000,
            'GBPUSD': 100000,
            'USDJPY': 100000,
            'AUDUSD': 100000,
            'USDCAD': 100000,
            'NZDUSD': 100000,
            'USDCHF': 100000,
            'EURGBP': 100000,
            'EURJPY': 100000,
            'GBPJPY': 100000,
            'BTCUSD': 1,
            'ETHUSD': 1,
            'XAUUSD': 100,
            'XAGUSD': 5000,
            'US30': 1,
            'US100': 1,
            'SILVER': 5000,
            'GOLD': 100,
            'OIL_BRENT': 1000,
            'XRPUSD': 1,
            'SOLUSD': 1,
            'DXY': 1,
            'NAS100': 1,  # alias a US100
        }
        
        self.profit_currencies = {
            'EURUSD': 'USD',
            'GBPUSD': 'USD',
            'USDJPY': 'JPY',
            'AUDUSD': 'USD',
            'USDCAD': 'CAD',
            'NZDUSD': 'USD',
            'USDCHF': 'CHF',
            'EURGBP': 'GBP',
            'EURJPY': 'JPY',
            'GBPJPY': 'JPY',
            'BTCUSD': 'USD',
            'ETHUSD': 'USD',
            'XAUUSD': 'USD',
            'XAGUSD': 'USD',
            'US30': 'USD',
            'US100': 'USD',
            'SILVER': 'USD',
            'GOLD': 'USD',
            'OIL_BRENT': 'USD',
            'XRPUSD': 'USD',
            'SOLUSD': 'USD',
            'DXY': 'USD',
            'NAS100': 'USD',  # alias a US100
        }
        
        self.account_currency = 'USD'  # Asumimos cuenta en USD
        
        # Constantes para tipos de orden
        self.ORDER_TYPE_BUY = 0
        self.ORDER_TYPE_SELL = 1
        
        self.risk_management_method = self._get_risk_management_method(risk_properties)
    
    def _get_risk_management_method(self, risk_props: BaseRiskProps) -> IRiskManager:
        """
        Returns the appropriate risk management method based on the given risk properties.

        Args:
            risk_props (BaseRiskProps): The risk properties object.

        Returns:
            IRiskManager: An instance of the appropriate risk manager.

        Raises:
            Exception: If the risk management method is unknown.
        """
        if isinstance(risk_props, MaxLeverageFactorRiskProps):
            return MaxLeverageFactorRiskManager(risk_props, self.capital_connector)
        else:
            raise Exception(f"ERROR: Método de Risk Mgmt desconocido: {risk_props}")

    def _compute_current_value_of_positions_in_account_currency(self) -> float:
        """
        Computes the current value of positions in the account currency.

        Returns:
            float: The total value of the positions in the account currency.
        """

        # Recopilamos las posiciones abiertas por nuestra estrategia
        current_positions = self.PORTFOLIO.get_strategy_open_positions()

        # Vamos a calcular el valor de las posiciones abiertas
        total_value = 0.0
        for position in current_positions:
            # Las posiciones de Capital.com vienen como diccionarios
            symbol = position.get('epic') or position.get('symbol', '')
            volume = position.get('size', position.get('volume', 0))
            position_type = 0 if position.get('direction') == 'BUY' else 1  # 0=BUY, 1=SELL
            
            if symbol:
                total_value += self._compute_value_of_position_in_account_currency(symbol, volume, position_type)
        
        return total_value

    def _compute_value_of_position_in_account_currency(self, symbol: str, volume: float, position_type: int) -> float:
        """
        Computes the value of a position in the account currency.

        Args:
            symbol (str): The symbol of the position.
            volume (float): The volume of the position.
            position_type (int): The type of the position.

        Returns:
            float: The value of the position in the account currency.
        """
        contract_size = self.contract_sizes.get(symbol, 1)
        profit_currency = self.profit_currencies.get(symbol, 'USD')

        # Unidades operadas en las unidades del symbol
        traded_units = volume * contract_size

        # Valor de las unidades operadas en la divisa cotizada del símbolo
        latest_tick = self.DATA_PROVIDER.get_latest_tick(symbol)
        if not latest_tick:
            return 0.0
        price = latest_tick.get('bid', 0)
        value_traded_in_profit_ccy = traded_units * price

        # Valor de las unidades operadas en la divisa de nuestra cuenta
        value_traded_in_account_ccy = Utils.convert_currency_amount_to_another_currency(value_traded_in_profit_ccy, profit_currency, self.account_currency)

        if position_type == 1:  # SELL (asume ORDER_TYPE_SELL = 1)
            return -value_traded_in_account_ccy
        else:
            return value_traded_in_account_ccy

    def _create_and_put_order_event(self, sizing_event: SizingEvent, volume: float) -> None:
        """
        Creates an OrderEvent based on the given SizingEvent and volume, and puts it into the events queue.

        Args:
            sizing_event (SizingEvent): The sizing event to create the order event from.
            volume (float): The volume for the order event.

        Returns:
            None
        """
        # Creamos el Order event a partir del sizing event y el volume
        order_event = OrderEvent(symbol=sizing_event.symbol,
                                    signal=sizing_event.signal,
                                    target_order=sizing_event.target_order,
                                    target_price=sizing_event.target_price,
                                    magic_number=sizing_event.magic_number,
                                    sl=sizing_event.sl,
                                    tp=sizing_event.tp,
                                    volume=volume)

        # Colocamos el order event a la cola de eventos
        self.events_queue.put(order_event)
    
    def assess_order(self, sizing_event: SizingEvent) -> None:
        """
        Assess the order based on the risk management method and create an order event if the new volume is greater than 0.

        Args:
            sizing_event (SizingEvent): The sizing event containing information about the order.

        Returns:
            None
        """
        
        # Obtenemos el valor de todas las posiciones abiertas por la estrategia en la divisa de la cuenta
        current_position_value = self._compute_current_value_of_positions_in_account_currency()

        # Obtenemos el valor que tendría la nueva posición, también en la divisa de la cuenta
        position_type = self.ORDER_TYPE_BUY if sizing_event.signal == "BUY" else self.ORDER_TYPE_SELL
        new_position_value = self._compute_value_of_position_in_account_currency(sizing_event.symbol, sizing_event.volume, position_type)
        
        # Obtenemos el nuevo volumen de la operacion que queremos ejecutar después de pasar por el risk manager
        new_volume = self.risk_management_method.assess_order(sizing_event, current_position_value, new_position_value)

        # Evaluamos el nuevo volumen
        if new_volume > 0.0:
            # colocar el order event a la cola de eventos
            self._create_and_put_order_event(sizing_event, new_volume)