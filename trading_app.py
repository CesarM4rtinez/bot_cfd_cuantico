# QUANTDEMY - Trading con Python y Capital.com: Framework adaptado
# Soporta múltiples cuentas simultáneamente

from capital_connector.capital_connector import CapitalConnector
from data_provider.data_provider import DataProvider
from trading_director.trading_director import TradingDirector
from signal_generator.signal_generator import SignalGenerator
from signal_generator.properties.signal_generator_properties import MACrossoverProps, RSIProps
from position_sizer.position_sizer import PositionSizer
from position_sizer.properties.position_sizer_properties import MinSizingProps, FixedSizingProps, RiskPctSizingProps
from portfolio.portfolio import Portfolio
from risk_manager.risk_manager import RiskManager
from risk_manager.properties.risk_manager_properties import MaxLeverageFactorRiskProps
from order_executor.order_executor import OrderExecutor
from notifications.notifications import NotificationService, TelegramNotificationProperties
from utils.utils import Utils
from queue import Queue
import os
from dotenv import load_dotenv, find_dotenv

def setup_capital_connector():
    """
    Configura y retorna el CapitalConnector.
    
    Returns:
        CapitalConnector: Conector a Capital.com
    """
    print(f"\n{Utils.dateprint()} - INICIALIZANDO CAPITAL.COM CONNECTOR")
    print("="*60)
    
    try:
        # Crear conector de Capital.com (carga automáticamente credenciales del .env)
        connector = CapitalConnector()
        
        # Intentar login para obtener tokens de sesión (no crítico)
        try:
            connector.login()
        except Exception as e:
            print(f"{Utils.dateprint()} - ⚠ Login falló, continuando sin autenticación: {str(e)}")
        
        return connector
        
    except Exception as e:
        print(f"{Utils.dateprint()} - ERROR: {str(e)}")
        raise

def setup_epic_mapping(connector=None, symbols=None):
    """
    Configura el mapeo de símbolos a EPICs de Capital.com.
    
    Args:
        connector: CapitalConnector para busquedas dinámicas
        symbols: Lista de símbolos para mapear
    
    Returns:
        Dict[str, str]: Mapeo de símbolos a EPICs
    """
    default_mapping = {
        'EURUSD': 'EURUSD',
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

    # Usar solo los símbolos deseados
    if symbols:
        mapping = {sym: default_mapping.get(sym) for sym in symbols if sym in default_mapping}
    else:
        mapping = default_mapping.copy()

    # Para símbolos faltantes, intentar buscar Epic usando API
    if connector and symbols:
        for sym in symbols:
            if mapping.get(sym):
                continue
            candidates = connector.search_instruments(sym)
            if candidates:
                # Quitar el caso donde epic no existe
                found = None
                for market in candidates:
                    epic = market.get('epic')
                    if epic and sym.upper() in epic.upper():
                        found = epic
                        break
                if not found:
                    found = candidates[0].get('epic')
                if found:
                    mapping[sym] = found

    return mapping

if __name__ == "__main__":

    print("\n")
    print("╔" + "="*60 + "╗")
    print("║" + " "*12 + "QUANTDEMY TRADING FRAMEWORK" + " "*21 + "║")
    print("║" + " "*18 + "Capital.com - Una Cuenta" + " "*17 + "║")
    print("╚" + "="*60 + "╝\n")

    # Cargar variables de entorno
    load_dotenv(find_dotenv())

    # ========================================
    # CONFIGURACIÓN DE LA ESTRATEGIA
    # ========================================
    
    # Definición de variables necesarias para la estrategia
    symbols = ['SILVER', 'GOLD', 'OIL_BRENT', 'EURUSD', 'ETHUSD', 'BTCUSD', 'XRPUSD', 'SOLUSD', 'DXY', 'US30', 'US100', 'NAS100']
    timeframe = 'MINUTE_5'  # MINUTE_1, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, DAY
    magic_number = 12345
    
    # Inicializar conector
    CONNECTOR = setup_capital_connector()
    
    # Nombre de cuenta (OBLIGATORIO)
    account_name = os.getenv("CAPITAL_ACCOUNT_NAME") # Nombre de cuenta a operar, debe coincidir exactamente con el configurado en Capital.com. Ejemplo: "Cuenta Principal", "Cuenta Demo 1", etc.
    if not account_name:
        raise ValueError("\n❌ ERROR: CAPITAL_ACCOUNT_NAME no configurado en .env. Por favor, agrega tu nombre de cuenta.")
    print(f"{Utils.dateprint()} - Operando en cuenta: {account_name}\n")

    # Mapeo de símbolos a EPICs
    epic_mapping = setup_epic_mapping(connector=CONNECTOR, symbols=symbols)
    
    print(f"{Utils.dateprint()} - Símbolos a operar: {', '.join(symbols)}")
    print(f"{Utils.dateprint()} - Marco temporal: {timeframe}")
    print(f"{Utils.dateprint()} - Número mágico: {magic_number}\n")

    # ========================================
    # CREAR COLA DE EVENTOS
    # ========================================
    
    # Creación de la cola de eventos principal
    events_queue = Queue()
    
    # ========================================
    # INICIALIZAR MÓDULOS DEL FRAMEWORK
    # ========================================
    
    print(f"\n{Utils.dateprint()} - Inicializando módulos del framework...")
    
    # DATA PROVIDER - Adaptado para Capital.com
    DATA_PROVIDER = DataProvider(
        events_queue=events_queue,
        capital_connector=CONNECTOR,
        symbol_list=symbols,
        epic_mapping=epic_mapping,
        timeframe=timeframe
    )
    
    # PORTFOLIO - Adaptado para Capital.com
    PORTFOLIO = Portfolio(
        capital_connector=CONNECTOR,
        magic_number=magic_number
    )
    
    # ORDER EXECUTOR - Una única cuenta
    ORDER_EXECUTOR = OrderExecutor(
        events_queue=events_queue,
        portfolio=PORTFOLIO,
        capital_connector=CONNECTOR,
        account_name=account_name
    )

    # SIGNAL GENERATOR
    rsi_props = RSIProps(
        timeframe=timeframe,
        rsi_period=5,
        rsi_upper=70.0,
        rsi_lower=30.0,
        sl_points=50,
        tp_points=100
    )
    
    SIGNAL_GENERATOR = SignalGenerator(
        events_queue=events_queue,
        data_provider=DATA_PROVIDER,
        portfolio=PORTFOLIO,
        order_executor=ORDER_EXECUTOR,
        signal_properties=rsi_props
    )
    
    # POSITION SIZER
    # Capital.com requiere mínimos de volumen diferentes por instrumento
    # Usando 1 como volumen base (cada instrumento tiene su mínimo)
    POSITION_SIZER = PositionSizer(
        events_queue=events_queue,
        data_provider=DATA_PROVIDER,
        sizing_properties=FixedSizingProps(volume=5.0)
    )

    # RISK MANAGER
    RISK_MANAGER = RiskManager(
        events_queue=events_queue,
        data_provider=DATA_PROVIDER,
        portfolio=PORTFOLIO,
        risk_properties=MaxLeverageFactorRiskProps(max_leverage_factor=5)
    )
    
    # NOTIFICATION SERVICE
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    
    NOTIFICATIONS = NotificationService(
        properties=TelegramNotificationProperties(
            token=telegram_token,
            chat_id=telegram_chat,
        ) if telegram_token and telegram_chat else None
    )

    # ========================================
    # CREAR Y EJECUTAR TRADING DIRECTOR
    # ========================================
    
    print(f"{Utils.dateprint()} - Módulos inicializados correctamente\n")
    print(f"{Utils.dateprint()} - Iniciando estrategia de trading...")
    print("="*60 + "\n")
    
    # Creación del trading director
    TRADING_DIRECTOR = TradingDirector(
        events_queue=events_queue,
        data_provider=DATA_PROVIDER,
        signal_generator=SIGNAL_GENERATOR,
        position_sizer=POSITION_SIZER,
        risk_manager=RISK_MANAGER,
        order_executor=ORDER_EXECUTOR,
        notification_service=NOTIFICATIONS
    )
    
    # Ejecutar estrategia
    try:
        TRADING_DIRECTOR.execute()
    except KeyboardInterrupt:
        print(f"\n{Utils.dateprint()} - Bot detenido por el usuario")
    except Exception as e:
        print(f"\n{Utils.dateprint()} - Error en la estrategia: {str(e)}")
        raise
    finally:
        print(f"{Utils.dateprint()} - Estrategia finalizada")