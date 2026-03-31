from capital_connector.capital_connector import CapitalConnector
c = CapitalConnector()
print('login', c.login())
for epic in ['GOLD','SILVER','OIL_BRENT','EURUSD','ETHUSD','BTCUSD','XRPUSD','SOLUSD','DXY','US30','US100','NAS100']:
    resp = c.get_prices(epic, resolution='MINUTE', num_points=5)
    print('---', epic, type(resp), resp)
