# QUANTDEMY - https://quantdemy.com - Trading con Python y MetaTrader 5: Crea tu Propio Framework

from data_provider.data_provider import DataProvider
from events.events import SignalEvent
from ..interfaces.position_sizer_interface import IPositionSizer
from ..properties.position_sizer_properties import FixedSizingProps

class FixedSizePositionSizer(IPositionSizer):

    def __init__(self, properties: FixedSizingProps):
        """
        Initializes a FixedSizePositionSizer object.

        Args:
            properties (FixedSizingProps): The properties for the position sizer.

        Attributes:
            fixed_volume (float): The fixed volume for position sizing.
        """
        self.fixed_volume = properties.volume

    def size_signal(self, signal_event: SignalEvent, data_provider: DataProvider) -> float:
        """
        Calculate the position size based on a fixed volume.

        Parameters:
        - signal_event (SignalEvent): The signal event triggering the position sizing.
        - data_provider (DataProvider): The data provider used to retrieve market data.

        Returns:
        - float: The position size based on the fixed volume. If the fixed volume is negative, returns 0.0.
        """
        if self.fixed_volume < 0.0:
            return 0.0

        # Ajustes por símbolo para mejorar precisión y evitar SL instantáneo por tamaño muy pequeño
        custom_volumes = {
            'XRPUSD': max(self.fixed_volume, 10.0),
            'SOLUSD': max(self.fixed_volume, 1.0),
            'BTCUSD': max(self.fixed_volume, 0.01),
            'ETHUSD': max(self.fixed_volume, 0.05),
            'US30': max(self.fixed_volume, 0.1),
            'US100': max(self.fixed_volume, 0.1),
            'GOLD': max(self.fixed_volume, 0.01),
            'SILVER': max(self.fixed_volume, 0.1),
            'OIL_BRENT': max(self.fixed_volume, 0.1),
        }

        symbol = signal_event.symbol.upper() if hasattr(signal_event, 'symbol') else None
        if symbol and symbol in custom_volumes:
            return custom_volumes[symbol]

        return self.fixed_volume