import pykrx.stock as stock
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

print("Testing FinanceDataReader:")
df_kospi = fdr.DataReader('KS11', '2023-01-01', '2023-12-31')
print(f"KOSPI shape: {df_kospi.shape}")
print(df_kospi.tail(2))

print("\nTesting PyKRX fundamental:")
# Let's get market fundamental for a test date
df_fund = stock.get_market_fundamental("20230630", market="KOSPI")
print(f"Fundamentals shape: {df_fund.shape}")
print(df_fund.head(2))
