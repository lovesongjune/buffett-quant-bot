import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

metrics_df = pd.read_csv('d:/lsj/antigravity/data/parsed_metrics.csv', dtype={'Code': str})
universe_df = pd.read_csv('d:/lsj/antigravity/data/universe_top100.csv', dtype={'Code': str})

# Let's inspect Magic Formula picks
df_valid = metrics_df[(metrics_df['Debt_Ratio'] <= 150) & (metrics_df['PER'] > 3)].copy()
df_valid['ROC_Rank'] = (df_valid['ROE_Avg3'] + df_valid['OP_Margin']).rank(ascending=False)
df_valid['EY_Rank'] = (1 / df_valid['PER']).rank(ascending=False)
df_valid['Magic_Rank'] = df_valid['ROC_Rank'] + df_valid['EY_Rank']
magic_top15 = df_valid.sort_values(by='Magic_Rank').head(15)

print("=== 조엘 그린블랫 마법공식 TOP 15 포트폴리오 ===")
print(magic_top15[['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'Debt_Ratio', 'PER', 'PBR', 'Magic_Rank']].to_string(index=False))

# Let's inspect Buffett Quality-Value picks
cond = (
    (metrics_df['ROE_Avg3'] >= 10) & 
    (metrics_df['OP_Margin'] >= 8) & 
    (metrics_df['Debt_Ratio'] <= 120) & 
    (metrics_df['PER'] >= 4) & (metrics_df['PER'] <= 35) & 
    (metrics_df['PBR'] <= 3.5)
)
buffett_cands = metrics_df[cond].copy()
buffett_cands['Score'] = buffett_cands['ROE_Avg3'] / (buffett_cands['PBR'] + 0.1)
buffett_top15 = buffett_cands.sort_values(by='Score', ascending=False).head(15)

print("\n=== 버핏 퀄리티-가치 TOP 15 포트폴리오 ===")
print(buffett_top15[['Code', 'Name', 'ROE_Avg3', 'OP_Margin', 'Debt_Ratio', 'PER', 'PBR', 'Score']].to_string(index=False))
