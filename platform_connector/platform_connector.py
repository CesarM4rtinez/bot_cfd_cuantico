# QUANTDEMY - https://quantdemy.com - Trading con Python y MetaTrader 5: Crea tu Propio Framework

from utils.utils import Utils
import MetaTrader5 as mt5
import os
from dotenv import load_dotenv, find_dotenv

class PlatformConnector():

    def __init__(self, symbol_list: list):
        """
        Initializes the platform connector object.

        Args:
            symbol_list (list): List of symbols to be added to the MarketWatch.
        """
        
        # Buscamos el archivo .env y cargamos sus valores
        load_dotenv(find_dotenv())

        # Inicialización de la plataforma
        self._initialize_platform()

        # Comprobación del tipo de cuenta
        self._live_account_warning()

        # Imprimimos información de la cuenta
        self._print_account_info()

        # Comprobación del trading algorítmico
        self._check_algo_trading_enabled()

        # Añadimos los símbolos al MarketWatch
        self._add_symbols_to_marketwatch(symbol_list)

    def _initialize_platform(self) -> None:
        """
        Initializes the MT5 platform.

        Raises:
            Exception: If there is any error while initializing the Platform

        Returns:
            None
        """
        import time
        
        # Cargar configuración desde variables de entorno
        mt5_path = os.getenv("MT5_PATH")
        mt5_login = int(os.getenv("MT5_LOGIN"))
        mt5_password = os.getenv("MT5_PASSWORD")
        mt5_server = os.getenv("MT5_SERVER")
        mt5_timeout = int(os.getenv("MT5_TIMEOUT"))
        mt5_portable = eval(os.getenv("MT5_PORTABLE"))
        
        print(f"Intentando inicializar MT5 con path: {mt5_path}")
        print(f"Login: {mt5_login}, Server: {mt5_server}, Timeout: {mt5_timeout}ms")
        
        # Estrategia 1: Intentar conexión con credenciales
        print("\n[Estrategia 1] Conectando con credenciales...")
        if mt5.initialize(
            path=mt5_path,
            login=mt5_login,
            password=mt5_password,
            server=mt5_server,
            timeout=mt5_timeout,
            portable=mt5_portable):
            print(f"{Utils.dateprint()} - ✓ Conectado con credenciales exitosamente!")
            return
        
        error_1 = mt5.last_error()
        print(f"✗ Error con credenciales: {error_1}")
        
        # Estrategia 2: Intentar sin credenciales (reutiliza conexión abierta en MT5)
        print("\n[Estrategia 2] Conectando sin credenciales (reutiliza MT5 abierto)...")
        time.sleep(1)
        
        if mt5.initialize(path=mt5_path, timeout=mt5_timeout):
            print(f"{Utils.dateprint()} - ✓ Conectado reutilizando sesión de MT5!")
            return
        
        error_2 = mt5.last_error()
        print(f"✗ Error sin credenciales: {error_2}")
        
        # Si ambas fallan
        raise Exception(
            f"Falló inicializar MT5 con ambas estrategias:\n"
            f"  1. Con credenciales: {error_1}\n"
            f"  2. Sin credenciales: {error_2}\n"
            f"Asegúrate de:\n"
            f"  - MT5 está abierto y autorizado\n"
            f"  - Credenciales en .env son correctas\n"
            f"  - Trading algorítmico está habilitado en MT5"
        )

    def _live_account_warning(self) -> None:
        """
        Displays a warning message if a real trading account is detected.
        Prompts the user to confirm if they want to continue.
        If the user chooses not to continue, the program is shut down.
        """
        # Recuperamos el objeto de tipo AccountInfo
        account_info = mt5.account_info()
        
        # Comprobar el tipo de cuenta que se ha lanzado
        if account_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO:
            print("Cuenta de tipo DEMO detectada.")
        
        elif account_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL:
            if not input("ALERTA! Cuenta de tipo REAL detectada. Capital en riesgo. ¿Deseas continuar? (y/n): ").lower() == "y":
                mt5.shutdown()
                raise Exception("Usuario ha decidido DETENER el programa.")
        else:
            print("Cuenta de tipo CONCURSO detectada.")

    def _check_algo_trading_enabled(self) -> None:
        """
        Checks if algorithmic trading is enabled.

        Raises:
            Exception: If algorithmic trading is disabled.
        """
        # Vamos a comprobar que el trading algorítmico está activado
        if not mt5.terminal_info().trade_allowed:
            raise Exception("El trading algorítmico está desactivado. Por favor, actívalo MANUALMENTE desde la configuración del terminal MT5.")

    def _add_symbols_to_marketwatch(self, symbols: list) -> None:
        """
        Adds symbols to the MarketWatch if they are not already visible.

        Args:
            symbols (list): List of symbols to be added.

        Returns:
            None
        """
        # 1) Comprobamos si el símbolo ya está visible en el MW
        # 2) Si no lo está, lo añadiremos

        for symbol in symbols:
            if mt5.symbol_info(symbol) is None:
                print(f"{Utils.dateprint()} - No se ha podido añadir el símbolo {symbol} al MarketWatch: {mt5.last_error()}")
                continue
            
            if not mt5.symbol_info(symbol).visible:
                if not mt5.symbol_select(symbol, True):
                    print(f"{Utils.dateprint()} - No se ha podido añadir el símbolo {symbol} al MarketWatch: {mt5.last_error()}")
                else:
                    print(f"{Utils.dateprint()} - Símbolo {symbol} se ha añadido con éxito al MarketWatch!")
            else:
                print(f"{Utils.dateprint()} - El símbolo {symbol} ya estaba en el MarketWatch.")

    def _print_account_info(self) -> None:
        """
        Prints the account information including account ID, trader name, broker, server, leverage, currency, and balance.
        """
        # Recuperar un objeto de tipo AccountInfo
        account_info = mt5.account_info()._asdict()

        print(f"+------------ Información de la cuenta ------------")
        print(f"| - ID de cuenta: {account_info['login']}")
        print(f"| - Nombre trader: {account_info['name']}")
        print(f"| - Broker: {account_info['company']}")
        print(f"| - Servidor: {account_info['server']}")
        print(f"| - Apalancamiento: {account_info['leverage']}")
        print(f"| - Divisa de la cuenta: {account_info['currency']}")
        print(f"| - Balance de la cuenta: {account_info['balance']}")
        print(f"+--------------------------------------------------")
