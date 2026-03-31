from trading_app import setup_capital_connector, setup_epic_mapping
c = setup_capital_connector()
symbols = ['SILVER','GOLD','OIL_BRENT','EURUSD','ETHUSD','BTCUSD','XRPUSD','SOLUSD','DXY','US30','US100','NAS100']
print(setup_epic_mapping(c, symbols))
