# ==========================================================
# 미래에셋증권 Open API 통신 클라이언트 모듈 (REST API)
# ==========================================================
import requests
import json
import os
import time
from datetime import datetime, timedelta
import config

class MiraeAssetAPI:
    def __init__(self, is_mock=config.IS_MOCK, dry_run=config.DRY_RUN):
        self.is_mock = is_mock
        self.dry_run = dry_run
        
        # 미래에셋 REST API 엔드포인트
        if self.is_mock:
            self.base_url = "https://openapivts.miraeasset.com"
        else:
            self.base_url = "https://openapi.miraeasset.com"
            
        self.app_key = config.APP_KEY
        self.app_secret = config.APP_SECRET
        self.account_no = config.ACCOUNT_NO
        self.account_code = config.ACCOUNT_CODE
        
        self.token_file = "d:/lsj/antigravity/token_cache.json"
        self.access_token = None
        self.token_expires_at = None
        
        if not self.dry_run:
            self._load_or_issue_token()
            
    def _load_or_issue_token(self):
        """저장된 토큰을 불러오거나 만료 시 신규 발급합니다."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    expires = datetime.fromisoformat(cache.get('expires_at'))
                    if datetime.now() < expires - timedelta(minutes=10):
                        self.access_token = cache.get('access_token')
                        self.token_expires_at = expires
                        print(f"[API] 캐시된 토큰 로드 완료 (만료 예정: {expires.strftime('%Y-%m-%d %H:%M:%S')})")
                        return
            except Exception as e:
                print(f"[API] 토큰 캐시 로드 실패: {e}")
                
        self._issue_token()

    def _issue_token(self):
        """OAuth 2.0 Access Token 신규 발급"""
        if self.app_key == "YOUR_APP_KEY_HERE":
            print("[주의] config.py에 APP_KEY와 APP_SECRET을 먼저 입력해주세요.")
            return

        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        headers = {"content-type": "application/json"}
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 86400))
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # 토큰 캐시 저장
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "access_token": self.access_token,
                        "expires_at": self.token_expires_at.isoformat()
                    }, f)
                print(f"[API] 신규 토큰 발급 성공 (만료: {self.token_expires_at.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                print(f"[API] 토큰 발급 에러: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[API] 토큰 발급 통신 오류: {e}")

    def _get_headers(self, tr_id):
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P"
        }

    def get_balance(self):
        """
        계좌 잔고 및 보유 종목 현황 조회
        반환값: {
            'total_asset': 총평가금액,
            'cash': 주문가능예수금,
            'holdings': [{'code': 종목코드, 'name': 종목명, 'qty': 수량, 'eval_amt': 평가금액}, ...]
        }
        """
        if self.dry_run:
            print("[DRY-RUN] 모의 잔고 반환 (시뮬레이션 모드: 200만 원)")
            return {
                'total_asset': 2000000, # 200만원 가상 예수금
                'cash': 2000000,
                'holdings': []
            }
            
        tr_id = "VTTC8434R" if self.is_mock else "TTTC8434R"
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        try:
            resp = requests.get(url, headers=self._get_headers(tr_id), params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                output1 = data.get("output1", [])
                output2 = data.get("output2", [{}])[0]
                
                holdings = []
                for item in output1:
                    qty = int(item.get("hldg_qty", 0))
                    if qty > 0:
                        holdings.append({
                            'code': item.get("pdno"),
                            'name': item.get("prdt_name"),
                            'qty': qty,
                            'pchs_amt': int(float(item.get("pchs_amt", 0))),
                            'evlu_amt': int(float(item.get("evlu_amt", 0))),
                            'profit_rate': float(item.get("evlu_pfls_rt", 0.0))
                        })
                
                total_asset = int(float(output2.get("tot_evlu_amt", 0)))
                cash = int(float(output2.get("dnca_tot_amt", 0)))
                return {
                    'total_asset': total_asset,
                    'cash': cash,
                    'holdings': holdings
                }
            else:
                print(f"[API] 잔고 조회 실패: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            print(f"[API] 잔고 조회 오류: {e}")
            return None

    def get_current_price(self, code):
        """개별 종목 현재가 조회"""
        if self.dry_run:
            # DRY-RUN 시 네이버 통합 시세 API 활용
            try:
                url = f"https://m.stock.naver.com/api/stock/{code}/integration"
                r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    dt_info = data.get('dealTrendInfos', [])
                    if dt_info and 'closePrice' in dt_info[0]:
                        return int(dt_info[0]['closePrice'].replace(',', ''))
            except Exception:
                pass
            # Fallback to local cached prices
            try:
                import pandas as pd
                df = pd.read_csv('d:/lsj/antigravity/data/prices_top100.csv', index_col=0)
                if code in df.columns:
                    val = df[code].dropna().iloc[-1]
                    return int(val)
            except Exception:
                pass
            return 50000

        tr_id = "FHKST01010100"
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code
        }
        try:
            resp = requests.get(url, headers=self._get_headers(tr_id), params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return int(data.get("output", {}).get("stck_prpr", 0))
        except Exception as e:
            print(f"[API] 현재가 조회 실패 ({code}): {e}")
        return None

    def send_order(self, code, qty, is_buy=True, order_type="01", price=0):
        """
        주식 주문 실행
        code: 6자리 종목코드
        qty: 주문수량
        is_buy: True(매수), False(매도)
        order_type: "01"(시장가), "00"(지정가)
        """
        order_name = "매수" if is_buy else "매도"
        
        if self.dry_run:
            print(f"  [DRY-RUN 가상주문] {order_name} | 종목코드: {code} | 수량: {qty}주 | 구분: {'시장가' if order_type=='01' else f'지정가 {price}원'}")
            return {"rt_cd": "0", "msg1": "DRY-RUN 정상 처리", "ODNO": "MOCK-12345"}
            
        if is_buy:
            tr_id = "VTTC0802U" if self.is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if self.is_mock else "TTTC0801U"
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        payload = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "PDNO": code,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price if order_type == "00" else 0)
        }
        
        try:
            resp = requests.post(url, headers=self._get_headers(tr_id), json=payload, timeout=10)
            if resp.status_code == 200:
                res_data = resp.json()
                print(f"[주문 완료] {order_name} {code} {qty}주 -> {res_data.get('msg1')}")
                return res_data
            else:
                print(f"[주문 실패] {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            print(f"[주문 전송 오류]: {e}")
            return None
