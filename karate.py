"""
ISO8583 COSMOS Studio Pro - Modern Professional UI
===================================================
Clean, professional design with light theme
"""

import streamlit as st
import json
import copy
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import random
import string
from enum import Enum

try:
    import requests
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"

RESPONSE_CODES = {
    "00": {"message": "Approved", "type": "approved", "icon": "✅", "color": "#10B981"},
    "01": {"message": "Refer to Issuer", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "05": {"message": "Do Not Honor", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "14": {"message": "Invalid Card", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "51": {"message": "Insufficient Funds", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "54": {"message": "Expired Card", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "61": {"message": "Exceeds Limit", "type": "declined", "icon": "❌", "color": "#EF4444"},
    "62": {"message": "Restricted Card", "type": "declined", "icon": "❌", "color": "#EF4444"},
}

# PPH_TRAN SCHEMA
PPH_TRAN_SCHEMA = {
    "table_name": "PPH_TRAN",
    "description": "Primary Payment Hub Transaction Table",
    "columns": {
        "TRAN_ID": {"type": "VARCHAR2(36)", "desc": "Transaction ID (UUID)"},
        "MSG_TYPE": {"type": "VARCHAR2(4)", "desc": "Message Type (0100, 0110)"},
        "PAN": {"type": "VARCHAR2(19)", "desc": "Primary Account Number (masked)"},
        "PROC_CODE": {"type": "VARCHAR2(6)", "desc": "Processing Code"},
        "TXN_AMT": {"type": "NUMBER(15,2)", "desc": "Transaction Amount"},
        "STAN": {"type": "VARCHAR2(6)", "desc": "System Trace Audit Number"},
        "RRN": {"type": "VARCHAR2(12)", "desc": "Retrieval Reference Number"},
        "AUTH_CODE": {"type": "VARCHAR2(6)", "desc": "Authorization Code"},
        "RESP_CODE": {"type": "VARCHAR2(2)", "desc": "Response Code"},
        "TERM_ID": {"type": "VARCHAR2(8)", "desc": "Terminal ID"},
        "MERCHANT_ID": {"type": "VARCHAR2(15)", "desc": "Merchant ID"},
        "MCC": {"type": "VARCHAR2(4)", "desc": "Merchant Category Code"},
        "TXN_STATUS": {"type": "VARCHAR2(20)", "desc": "Transaction Status"},
        "CREATED_DT": {"type": "TIMESTAMP", "desc": "Record Creation Date"},
        "CARD_TYPE": {"type": "VARCHAR2(20)", "desc": "Card Type (VISA, MC)"},
    }
}

# PPDSVA SCHEMA
PPDSVA_SCHEMA = {
    "table_name": "PPDSVA",
    "description": "Payment Processing Data Store - Value Added",
    "columns": {
        "SVA_ID": {"type": "VARCHAR2(36)", "desc": "SVA Record ID"},
        "TRAN_ID": {"type": "VARCHAR2(36)", "desc": "Related Transaction ID"},
        "RRN": {"type": "VARCHAR2(12)", "desc": "Retrieval Reference Number"},
        "STAN": {"type": "VARCHAR2(6)", "desc": "System Trace Audit Number"},
        "AUTH_CODE": {"type": "VARCHAR2(6)", "desc": "Authorization Code"},
        "NETWORK_ID": {"type": "VARCHAR2(10)", "desc": "Network Identifier"},
        "NETWORK_RESP": {"type": "VARCHAR2(100)", "desc": "Network Response"},
        "RISK_SCORE": {"type": "NUMBER(5,2)", "desc": "Risk Assessment Score"},
        "FRAUD_CHECK": {"type": "VARCHAR2(10)", "desc": "Fraud Check Result"},
        "AVS_RESULT": {"type": "VARCHAR2(2)", "desc": "Address Verification"},
        "CVV_RESULT": {"type": "VARCHAR2(2)", "desc": "CVV Verification"},
        "HOST_RESP_CODE": {"type": "VARCHAR2(4)", "desc": "Host Response Code"},
        "PROCESS_TIME_MS": {"type": "NUMBER(10)", "desc": "Processing Time (ms)"},
        "CREATED_DT": {"type": "TIMESTAMP", "desc": "Record Creation Date"},
    }
}

# ============================================================================
# TEMPLATES
# ============================================================================

@dataclass
class ISO8583Template:
    name: str
    description: str
    fields: Dict[str, str]
    
    def apply_overrides(self, overrides: Dict) -> Dict:
        merged = copy.deepcopy(self.fields)
        merged.update(overrides)
        return merged

TEMPLATES = {
    "fwd_visasig_direct_purchase_0100": ISO8583Template(
        name="fwd_visasig_direct_purchase_0100",
        description="Visa Signature Direct Purchase",
        fields={
            "DMTI": "0100", "DE2": "4144779500060809", "DE3": "000000",
            "DE4": "000000000700", "DE11": "001212", "DE14": "2512",
            "DE18": "3535", "DE22": "900", "DE32": "59000000754",
            "DE35": "4144779500060809D251210112345129",
            "DE37": "024405001212", "DE41": "TERMID01",
            "DE42": "Visa / PLUS", "DE43": "QTP Execution CO COUS",
        }
    ),
    "fwd_mastercard_purchase_0100": ISO8583Template(
        name="fwd_mastercard_purchase_0100",
        description="MasterCard Purchase",
        fields={
            "DMTI": "0100", "DE2": "5500000000000004", "DE3": "000000",
            "DE4": "000000001000", "DE11": "001213", "DE14": "2512",
            "DE18": "5411", "DE22": "051", "DE37": "024405001213",
            "DE41": "TERMID02", "DE42": "MasterCard",
        }
    ),
    "fwd_atm_withdrawal_0100": ISO8583Template(
        name="fwd_atm_withdrawal_0100",
        description="ATM Cash Withdrawal",
        fields={
            "DMTI": "0100", "DE2": "4111111111111111", "DE3": "010000",
            "DE4": "000000005000", "DE11": "001214", "DE14": "2512",
            "DE18": "6011", "DE22": "051", "DE37": "024405001214",
            "DE41": "ATM00001", "DE42": "BANK ATM",
        }
    ),
}

# ============================================================================
# COMMON SCENARIOS
# ============================================================================

COMMON_SCENARIOS = {
    "approved_purchase": {
        "name": "Approved Purchase",
        "description": "Standard approved purchase transaction",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {},
        "expected_response_code": "00",
        "expected_pph_status": "COMPLETED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["smoke", "positive"],
        "icon": "🛒"
    },
    "declined_insufficient_funds": {
        "name": "Declined - Insufficient Funds",
        "description": "Transaction declined due to insufficient funds",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE2": "4111111111111112", "DE4": "999999999999"},
        "expected_response_code": "51",
        "expected_pph_status": "DECLINED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["negative", "decline"],
        "icon": "💳"
    },
    "declined_expired_card": {
        "name": "Declined - Expired Card",
        "description": "Transaction declined due to expired card",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE14": "2001"},
        "expected_response_code": "54",
        "expected_pph_status": "DECLINED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["negative", "expired"],
        "icon": "📅"
    },
    "high_value_purchase": {
        "name": "High Value Purchase",
        "description": "High value purchase within limits",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE4": "000000500000"},
        "expected_response_code": "00",
        "expected_pph_status": "COMPLETED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["regression", "high-value"],
        "icon": "💰"
    },
    "atm_withdrawal": {
        "name": "ATM Cash Withdrawal",
        "description": "ATM cash withdrawal transaction",
        "template": "fwd_atm_withdrawal_0100",
        "overrides": {},
        "expected_response_code": "00",
        "expected_pph_status": "COMPLETED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["atm", "cash"],
        "icon": "🏧"
    },
}

# ============================================================================
# HELPERS
# ============================================================================

def generate_stan(): return str(random.randint(0, 999999)).zfill(6)
def generate_rrn(): return str(random.randint(0, 999999999999)).zfill(12)
def generate_auth_id(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
def generate_uuid(): return ''.join(random.choices(string.hexdigits.lower(), k=32))
def format_amount(amt): return str(int(amt * 100)).zfill(12)
def parse_amount(s): return int(s) / 100 if s.isdigit() else 0
def mask_pan(pan): return pan[:6] + "******" + pan[-4:] if len(pan) >= 12 else pan

# ============================================================================
# DATABASE CLIENT
# ============================================================================

class DatabaseClient:
    def __init__(self, host="", port=1521, service="", user="", pwd="", use_mock=True):
        self.use_mock = use_mock
    
    def query_pph_tran(self, rrn: str, stan: str) -> Dict:
        if self.use_mock:
            return self._mock_pph_tran(rrn, stan)
        return {"success": False, "error": "Real DB not configured"}
    
    def query_ppdsva(self, rrn: str, stan: str) -> Dict:
        if self.use_mock:
            return self._mock_ppdsva(rrn, stan)
        return {"success": False, "error": "Real DB not configured"}
    
    def _mock_pph_tran(self, rrn: str, stan: str) -> Dict:
        return {
            "success": True,
            "record": {
                "TRAN_ID": generate_uuid(),
                "MSG_TYPE": "0100",
                "PAN": "414477******0809",
                "PROC_CODE": "000000",
                "TXN_AMT": 7.00,
                "STAN": stan,
                "RRN": rrn,
                "AUTH_CODE": generate_auth_id(),
                "RESP_CODE": "00",
                "TERM_ID": "TERMID01",
                "MERCHANT_ID": "Visa / PLUS",
                "MCC": "3535",
                "TXN_STATUS": "COMPLETED",
                "CREATED_DT": datetime.now().isoformat(),
                "CARD_TYPE": "VISA",
            }
        }
    
    def _mock_ppdsva(self, rrn: str, stan: str) -> Dict:
        return {
            "success": True,
            "record": {
                "SVA_ID": generate_uuid(),
                "TRAN_ID": generate_uuid(),
                "RRN": rrn,
                "STAN": stan,
                "AUTH_CODE": generate_auth_id(),
                "NETWORK_ID": "VISA",
                "NETWORK_RESP": "Approved",
                "RISK_SCORE": 15.5,
                "FRAUD_CHECK": "PASS",
                "AVS_RESULT": "Y",
                "CVV_RESULT": "M",
                "HOST_RESP_CODE": "00",
                "PROCESS_TIME_MS": 245,
                "CREATED_DT": datetime.now().isoformat(),
            }
        }

# ============================================================================
# COSMOS CLIENT
# ============================================================================

class COSMOSClient:
    def __init__(self, url: str, use_mock: bool = True):
        self.url = url.rstrip('/')
        self.use_mock = use_mock
    
    def send_transaction(self, template_name: str, overrides: Dict) -> Dict:
        if self.use_mock:
            return self._mock_transaction(template_name, overrides)
        
        if not HAS_REQUESTS:
            return {"success": False, "error": "requests library not available"}
        
        try:
            template = TEMPLATES.get(template_name)
            if not template:
                return {"success": False, "error": "Template not found"}
            
            merged = template.apply_overrides(overrides)
            payload = {"templateId": template_name, "overrides": overrides, "message": merged}
            
            response = requests.post(
                f"{self.url}/template?id={template_name}&type=MessageTemplate",
                json=payload, timeout=30, headers={"Content-Type": "application/json"}
            )
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "request": {"template": template_name, "overrides": overrides, "merged": merged},
                "response": response.json() if response.status_code == 200 else {"error": response.text},
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _mock_transaction(self, template_name: str, overrides: Dict) -> Dict:
        template = TEMPLATES.get(template_name)
        if not template:
            return {"success": False, "error": "Template not found"}
        
        merged = template.apply_overrides(overrides)
        stan = overrides.get("DE11", generate_stan())
        rrn = overrides.get("DE37", generate_rrn())
        
        pan = merged.get("DE2", "")
        expiry = merged.get("DE14", "2512")
        amount = merged.get("DE4", "0")
        
        resp_code = "00"
        if "1112" in pan: resp_code = "51"
        elif "1113" in pan: resp_code = "62"
        elif int(expiry[:2]) < 24: resp_code = "54"
        elif int(amount) > 500000000000: resp_code = "61"
        
        return {
            "success": True,
            "status_code": 200,
            "request": {"template": template_name, "overrides": overrides, "merged": merged},
            "response": {
                "mti": "0110",
                "DE11": stan,
                "DE37": rrn,
                "DE38": generate_auth_id() if resp_code == "00" else None,
                "DE39": resp_code,
                "responseMessage": RESPONSE_CODES.get(resp_code, {}).get("message", "Unknown")
            },
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# VALIDATION ENGINE
# ============================================================================

class ValidationEngine:
    def __init__(self, cosmos: COSMOSClient, db: DatabaseClient):
        self.cosmos = cosmos
        self.db = db
    
    def run_full_validation(self, scenario: Dict, cosmos_resp: Dict, pph: Dict, ppdsva: Dict) -> Dict:
        results = {
            "timestamp": datetime.now().isoformat(),
            "scenario": scenario.get("name", "Custom"),
            "overall_status": "PENDING",
            "sections": {}
        }
        
        results["sections"]["cosmos"] = self._validate_cosmos(scenario, cosmos_resp)
        results["sections"]["pph_tran"] = self._validate_pph_tran(scenario, cosmos_resp, pph)
        results["sections"]["ppdsva"] = self._validate_ppdsva(scenario, cosmos_resp, ppdsva)
        
        all_checks = []
        for section in results["sections"].values():
            all_checks.extend(section.get("checks", []))
        
        passed = sum(1 for c in all_checks if c["status"] == "PASS")
        failed = sum(1 for c in all_checks if c["status"] == "FAIL")
        warned = sum(1 for c in all_checks if c["status"] == "WARN")
        
        results["summary"] = {"total": len(all_checks), "passed": passed, "failed": failed, "warnings": warned}
        results["overall_status"] = "FAIL" if failed > 0 else ("WARN" if warned > 0 else "PASS")
        
        return results
    
    def _validate_cosmos(self, scenario: Dict, resp: Dict) -> Dict:
        checks = []
        data = resp.get("response", {})
        expected_rc = scenario.get("expected_response_code", "00")
        
        actual_mti = data.get("mti") or data.get("DMTI")
        checks.append({"name": "Response MTI", "expected": "0110", "actual": actual_mti, "status": "PASS" if actual_mti == "0110" else "FAIL"})
        
        actual_rc = data.get("DE39") or data.get("responseCode")
        checks.append({"name": "Response Code (DE39)", "expected": expected_rc, "actual": actual_rc, "status": "PASS" if actual_rc == expected_rc else "FAIL"})
        
        if expected_rc == "00":
            auth_id = data.get("DE38")
            checks.append({"name": "Auth ID (DE38)", "expected": "Present", "actual": auth_id or "NULL", "status": "PASS" if auth_id else "FAIL"})
        
        return {"section_name": "COSMOS Response", "icon": "🌐", "checks": checks}
    
    def _validate_pph_tran(self, scenario: Dict, cosmos_resp: Dict, pph: Dict) -> Dict:
        checks = []
        record = pph.get("record", {})
        
        if not pph.get("success"):
            checks.append({"name": "PPH_TRAN Record", "expected": "Found", "actual": "Not Found", "status": "FAIL"})
            return {"section_name": "PPH_TRAN Validation", "icon": "🗄️", "checks": checks}
        
        checks.append({"name": "PPH_TRAN Record", "expected": "Found", "actual": "Found", "status": "PASS"})
        
        expected_status = scenario.get("expected_pph_status", "COMPLETED")
        actual_status = record.get("TXN_STATUS")
        checks.append({"name": "Transaction Status", "expected": expected_status, "actual": actual_status, "status": "PASS" if actual_status == expected_status else "FAIL"})
        
        cosmos_rc = cosmos_resp.get("response", {}).get("DE39")
        db_rc = record.get("RESP_CODE")
        checks.append({"name": "Response Code Match", "expected": cosmos_rc, "actual": db_rc, "status": "PASS" if db_rc == cosmos_rc else "FAIL"})
        
        req_rrn = cosmos_resp.get("request", {}).get("overrides", {}).get("DE37")
        if req_rrn:
            db_rrn = record.get("RRN")
            checks.append({"name": "RRN Match", "expected": req_rrn, "actual": db_rrn, "status": "PASS" if db_rrn == req_rrn else "FAIL"})
        
        req_stan = cosmos_resp.get("request", {}).get("overrides", {}).get("DE11")
        if req_stan:
            db_stan = record.get("STAN")
            checks.append({"name": "STAN Match", "expected": req_stan, "actual": db_stan, "status": "PASS" if db_stan == req_stan else "FAIL"})
        
        return {"section_name": "PPH_TRAN Validation", "icon": "🗄️", "checks": checks}
    
    def _validate_ppdsva(self, scenario: Dict, cosmos_resp: Dict, ppdsva: Dict) -> Dict:
        checks = []
        record = ppdsva.get("record", {})
        
        if not ppdsva.get("success"):
            checks.append({"name": "PPDSVA Record", "expected": "Found", "actual": "Not Found", "status": "WARN"})
            return {"section_name": "PPDSVA Validation", "icon": "📊", "checks": checks}
        
        checks.append({"name": "PPDSVA Record", "expected": "Found", "actual": "Found", "status": "PASS"})
        
        expected_fraud = scenario.get("expected_ppdsva_fraud", "PASS")
        actual_fraud = record.get("FRAUD_CHECK")
        checks.append({"name": "Fraud Check", "expected": expected_fraud, "actual": actual_fraud, "status": "PASS" if actual_fraud == expected_fraud else "WARN"})
        
        cosmos_rc = cosmos_resp.get("response", {}).get("DE39")
        host_rc = record.get("HOST_RESP_CODE")
        checks.append({"name": "Host Response Code", "expected": cosmos_rc, "actual": host_rc, "status": "PASS" if host_rc == cosmos_rc else "WARN"})
        
        risk = record.get("RISK_SCORE", 0)
        checks.append({"name": "Risk Score", "expected": "< 50", "actual": str(risk), "status": "PASS" if float(risk) < 50 else "WARN"})
        
        proc_time = record.get("PROCESS_TIME_MS", 0)
        checks.append({"name": "Processing Time", "expected": "< 3000ms", "actual": f"{proc_time}ms", "status": "PASS" if int(proc_time) < 3000 else "WARN"})
        
        return {"section_name": "PPDSVA Validation", "icon": "📊", "checks": checks}

# ============================================================================
# KARATE & PYTEST GENERATORS
# ============================================================================

def generate_karate_with_sql(template_name: str, cosmos_url: str, db_config: Dict) -> str:
    template = TEMPLATES.get(template_name)
    return f'''Feature: {template.description} - E2E with SQL Validation

  Background:
    * url '{cosmos_url}'
    * def templateName = '{template_name}'
    * def generateSTAN = function(){{ return Math.floor(Math.random() * 999999).toString().padStart(6, '0') }}
    * def generateRRN = function(){{ return Math.floor(Math.random() * 999999999999).toString().padStart(12, '0') }}

  @smoke @e2e @sql
  Scenario: E2E Approved with SQL Validation
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    
    Given path '/template'
    And param id = templateName
    And request {{ templateId: '#(templateName)', overrides: {{ DE11: '#(stan)', DE37: '#(rrn)' }} }}
    When method post
    Then status 200
    And match response.DE39 == '00'
    
    # Validate PPH_TRAN
    * def pphRecord = db.query("SELECT * FROM PPH_TRAN WHERE RRN='" + rrn + "'")
    * match pphRecord.TXN_STATUS == 'COMPLETED'
    
    # Validate PPDSVA
    * def ppdsvaRecord = db.query("SELECT * FROM PPDSVA WHERE RRN='" + rrn + "'")
    * match ppdsvaRecord.FRAUD_CHECK == 'PASS'
'''

def generate_pytest_with_sql(template_name: str, cosmos_url: str, db_config: Dict) -> str:
    return f'''"""ISO8583 E2E Tests with SQL - {template_name}"""
import pytest, requests, random

class Config:
    COSMOS_URL = "{cosmos_url}"
    TEMPLATE = "{template_name}"

def generate_stan(): return str(random.randint(0, 999999)).zfill(6)
def generate_rrn(): return str(random.randint(0, 999999999999)).zfill(12)

@pytest.fixture
def api_session():
    s = requests.Session()
    s.headers.update({{"Content-Type": "application/json"}})
    yield s
    s.close()

class TestE2EWithSQL:
    @pytest.mark.smoke
    def test_approved_with_sql(self, api_session):
        stan, rrn = generate_stan(), generate_rrn()
        resp = api_session.post(
            f"{{Config.COSMOS_URL}}/template?id={{Config.TEMPLATE}}",
            json={{"templateId": Config.TEMPLATE, "overrides": {{"DE11": stan, "DE37": rrn}}}}
        ).json()
        assert resp["DE39"] == "00"
        # Add SQL validation here
'''

# ============================================================================
# STREAMLIT UI - MODERN PROFESSIONAL THEME
# ============================================================================

st.set_page_config(
    page_title="ISO8583 COSMOS Studio",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Professional CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --primary: #6366F1;
    --primary-light: #818CF8;
    --primary-dark: #4F46E5;
    --success: #10B981;
    --success-light: #D1FAE5;
    --warning: #F59E0B;
    --warning-light: #FEF3C7;
    --danger: #EF4444;
    --danger-light: #FEE2E2;
    --gray-50: #F9FAFB;
    --gray-100: #F3F4F6;
    --gray-200: #E5E7EB;
    --gray-300: #D1D5DB;
    --gray-400: #9CA3AF;
    --gray-500: #6B7280;
    --gray-600: #4B5563;
    --gray-700: #374151;
    --gray-800: #1F2937;
    --gray-900: #111827;
    --white: #FFFFFF;
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
}

/* Global Styles */
.stApp {
    background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 50%, #F8FAFC 100%);
    font-family: 'Inter', sans-serif;
}

/* Hide Streamlit Branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Main Header */
.main-header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}

.main-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: rgba(255,255,255,0.1);
    border-radius: 50%;
}

.main-header::after {
    content: '';
    position: absolute;
    bottom: -30%;
    left: 10%;
    width: 200px;
    height: 200px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}

.main-title {
    font-family: 'Inter', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--white);
    margin: 0;
    position: relative;
    z-index: 1;
}

.main-subtitle {
    font-size: 1rem;
    color: rgba(255,255,255,0.8);
    margin-top: 0.5rem;
    font-weight: 400;
    position: relative;
    z-index: 1;
}

/* Section Headers */
.section-header {
    font-family: 'Inter', sans-serif;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--gray-800);
    margin: 1.5rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.section-header-icon {
    font-size: 1.5rem;
}

/* Cards */
.card {
    background: var(--white);
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: var(--shadow);
    transition: all 0.2s ease;
}

.card:hover {
    box-shadow: var(--shadow-md);
    border-color: var(--gray-300);
}

.card-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.card-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--primary-light), var(--primary));
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
}

.card-title {
    font-weight: 600;
    color: var(--gray-800);
    font-size: 1rem;
}

.card-subtitle {
    font-size: 0.875rem;
    color: var(--gray-500);
}

/* Status Badges */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}

.badge-success {
    background: var(--success-light);
    color: #065F46;
    border: 1px solid #A7F3D0;
}

.badge-danger {
    background: var(--danger-light);
    color: #991B1B;
    border: 1px solid #FECACA;
}

.badge-warning {
    background: var(--warning-light);
    color: #92400E;
    border: 1px solid #FDE68A;
}

.badge-info {
    background: #DBEAFE;
    color: #1E40AF;
    border: 1px solid #BFDBFE;
}

/* Metrics Grid */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}

.metric-card {
    background: var(--white);
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    padding: 1.25rem;
    text-align: center;
    box-shadow: var(--shadow-sm);
}

.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
}

.metric-value.success { color: var(--success); }
.metric-value.danger { color: var(--danger); }
.metric-value.warning { color: var(--warning); }
.metric-value.primary { color: var(--primary); }

.metric-label {
    font-size: 0.75rem;
    color: var(--gray-500);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.5rem;
    font-weight: 500;
}

/* Validation Section */
.validation-section {
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: 10px;
    margin: 1rem 0;
    overflow: hidden;
}

.validation-section-header {
    background: var(--white);
    padding: 0.875rem 1.25rem;
    border-bottom: 1px solid var(--gray-200);
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    color: var(--gray-700);
}

.validation-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid var(--gray-100);
    background: var(--white);
}

.validation-row:last-child {
    border-bottom: none;
}

.validation-name {
    font-size: 0.875rem;
    color: var(--gray-700);
}

.validation-values {
    display: flex;
    align-items: center;
    gap: 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
}

.validation-expected {
    color: var(--gray-400);
}

.validation-actual {
    color: var(--gray-700);
    font-weight: 500;
}

/* Step Indicator */
.step-indicator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: linear-gradient(135deg, #EEF2FF, #E0E7FF);
    border-radius: 8px;
    margin: 1rem 0;
    border-left: 4px solid var(--primary);
}

.step-number {
    background: var(--primary);
    color: var(--white);
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
    font-weight: 600;
}

.step-text {
    font-weight: 500;
    color: var(--gray-700);
}

/* Scenario Cards */
.scenario-card {
    background: var(--white);
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    padding: 1.25rem;
    margin: 0.75rem 0;
    transition: all 0.2s ease;
    cursor: pointer;
}

.scenario-card:hover {
    border-color: var(--primary-light);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.scenario-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}

.scenario-icon {
    font-size: 1.5rem;
}

.scenario-title {
    font-weight: 600;
    color: var(--gray-800);
}

.scenario-desc {
    font-size: 0.875rem;
    color: var(--gray-500);
    margin-bottom: 0.75rem;
}

.scenario-tags {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.tag {
    background: var(--gray-100);
    color: var(--gray-600);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}

/* Schema Table */
.schema-table {
    background: var(--white);
    border: 1px solid var(--gray-200);
    border-radius: 10px;
    overflow: hidden;
    margin: 1rem 0;
}

.schema-header {
    background: linear-gradient(135deg, var(--gray-100), var(--gray-50));
    padding: 0.75rem 1rem;
    font-weight: 600;
    color: var(--gray-700);
    border-bottom: 1px solid var(--gray-200);
}

.schema-row {
    display: grid;
    grid-template-columns: 140px 130px 1fr;
    padding: 0.6rem 1rem;
    border-bottom: 1px solid var(--gray-100);
    font-size: 0.8rem;
    align-items: center;
}

.schema-row:last-child {
    border-bottom: none;
}

.schema-col {
    font-family: 'JetBrains Mono', monospace;
    color: var(--primary);
    font-weight: 500;
}

.schema-type {
    font-family: 'JetBrains Mono', monospace;
    color: var(--warning);
    font-size: 0.75rem;
}

.schema-desc {
    color: var(--gray-500);
}

/* Streamlit Overrides */
.stTabs [data-baseweb="tab-list"] {
    background: var(--white);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    border: 1px solid var(--gray-200);
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.875rem;
    color: var(--gray-600);
    background: transparent;
    border-radius: 8px;
    padding: 0.625rem 1.25rem;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
    color: var(--white) !important;
}

.stButton > button {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: var(--white);
    border: none;
    border-radius: 10px;
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    box-shadow: var(--shadow);
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
}

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
    font-family: 'Inter', sans-serif;
    border: 1px solid var(--gray-300) !important;
    border-radius: 8px !important;
    background: var(--white) !important;
}

.stTextInput > div > div > input:focus,
.stSelectbox > div > div:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
}

.stExpander {
    background: var(--white);
    border: 1px solid var(--gray-200);
    border-radius: 10px;
}

/* Success/Error Messages */
.stSuccess {
    background: var(--success-light);
    border: 1px solid #A7F3D0;
    border-radius: 10px;
}

.stError {
    background: var(--danger-light);
    border: 1px solid #FECACA;
    border-radius: 10px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--white);
    border-right: 1px solid var(--gray-200);
}

section[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--gray-800);
    font-weight: 600;
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)

def main():
    # Header
    st.markdown('''
    <div class="main-header">
        <h1 class="main-title">💳 ISO8583 COSMOS Studio</h1>
        <p class="main-subtitle">Complete E2E Transaction Validation • COSMOS Simulator • PPH_TRAN • PPDSVA • SQL Validation</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        use_mock = st.checkbox("🔧 Demo Mode", value=True, help="Use simulated data for testing")
        
        st.markdown("---")
        st.markdown("### 🌐 COSMOS")
        cosmos_url = st.text_input("API URL", "http://10.160.59.86:8080", disabled=use_mock)
        
        st.markdown("---")
        st.markdown("### 🗄️ Database")
        db_host = st.text_input("Host", "localhost", disabled=use_mock)
        db_port = st.number_input("Port", value=1521, disabled=use_mock)
        db_service = st.text_input("Service", "ORCL", disabled=use_mock)
        
        db_config = {"host": db_host, "port": db_port, "service": db_service}
        
        st.markdown("---")
        st.markdown("### 📋 Template")
        selected_template = st.selectbox(
            "Select Template",
            list(TEMPLATES.keys()),
            format_func=lambda x: TEMPLATES[x].description
        )
    
    # Initialize clients
    cosmos = COSMOSClient(cosmos_url, use_mock)
    db = DatabaseClient(db_host, db_port, db_service, use_mock=use_mock)
    engine = ValidationEngine(cosmos, db)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 E2E Validation",
        "📋 Scenarios",
        "🗄️ SQL Schema",
        "📝 Karate",
        "🐍 Python"
    ])
    
    # TAB 1: E2E VALIDATION
    with tab1:
        st.markdown('<div class="section-header"><span class="section-header-icon">🔄</span> E2E Transaction Validation</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            template = TEMPLATES[selected_template]
            
            st.markdown(f'''
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📄</div>
                    <div>
                        <div class="card-title">{template.name}</div>
                        <div class="card-subtitle">{template.description}</div>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            with st.expander("📋 View Template Fields"):
                st.json(template.fields)
            
            st.markdown("#### Field Overrides")
            
            c1, c2 = st.columns(2)
            with c1:
                ovr_pan = st.text_input("DE2 - PAN", placeholder="Use template value")
                ovr_exp = st.text_input("DE14 - Expiry", placeholder="YYMM")
            with c2:
                ovr_amt = st.number_input("DE4 - Amount ($)", min_value=0.0, step=0.01)
                ovr_term = st.text_input("DE41 - Terminal", placeholder="Use template")
            
            st.markdown("#### Expected Results")
            c1, c2 = st.columns(2)
            with c1:
                exp_rc = st.selectbox(
                    "Response Code",
                    list(RESPONSE_CODES.keys()),
                    format_func=lambda x: f"{x} - {RESPONSE_CODES[x]['message']}"
                )
            with c2:
                exp_status = st.selectbox("DB Status", ["COMPLETED", "DECLINED", "REJECTED"])
            
            # Build overrides
            overrides = {}
            if ovr_pan: overrides["DE2"] = ovr_pan
            if ovr_amt > 0: overrides["DE4"] = format_amount(ovr_amt)
            if ovr_exp: overrides["DE14"] = ovr_exp
            if ovr_term: overrides["DE41"] = ovr_term
            
            stan, rrn = generate_stan(), generate_rrn()
            overrides["DE11"] = stan
            overrides["DE37"] = rrn
            
            scenario = {
                "name": "Custom Test",
                "template": selected_template,
                "overrides": overrides,
                "expected_response_code": exp_rc,
                "expected_pph_status": exp_status,
                "expected_ppdsva_fraud": "PASS"
            }
            
            st.markdown(f'''
            <div class="card" style="background: linear-gradient(135deg, #EEF2FF, #E0E7FF);">
                <div style="display: flex; gap: 2rem;">
                    <div>
                        <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase;">STAN</div>
                        <div style="font-family: 'JetBrains Mono'; font-weight: 600; color: #4F46E5;">{stan}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase;">RRN</div>
                        <div style="font-family: 'JetBrains Mono'; font-weight: 600; color: #4F46E5;">{rrn}</div>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            run = st.button("🚀 Run E2E Validation", use_container_width=True)
        
        with col2:
            if run:
                # Step 1
                st.markdown('<div class="step-indicator"><span class="step-number">1</span><span class="step-text">Sending to COSMOS Simulator</span></div>', unsafe_allow_html=True)
                
                with st.spinner(""):
                    cosmos_resp = cosmos.send_transaction(selected_template, overrides)
                
                if cosmos_resp.get("success"):
                    st.success("✅ Transaction sent successfully")
                else:
                    st.error(f"❌ Failed: {cosmos_resp.get('error')}")
                
                with st.expander("View COSMOS Response"):
                    st.json(cosmos_resp.get("response", {}))
                
                # Step 2
                st.markdown('<div class="step-indicator"><span class="step-number">2</span><span class="step-text">Querying PPH_TRAN Table</span></div>', unsafe_allow_html=True)
                
                pph = db.query_pph_tran(rrn, stan)
                if pph.get("success"):
                    st.success("✅ PPH_TRAN record found")
                else:
                    st.warning("⚠️ PPH_TRAN record not found")
                
                with st.expander("View PPH_TRAN Record"):
                    st.json(pph.get("record", {}))
                
                # Step 3
                st.markdown('<div class="step-indicator"><span class="step-number">3</span><span class="step-text">Querying PPDSVA Table</span></div>', unsafe_allow_html=True)
                
                ppdsva = db.query_ppdsva(rrn, stan)
                if ppdsva.get("success"):
                    st.success("✅ PPDSVA record found")
                else:
                    st.warning("⚠️ PPDSVA record not found")
                
                with st.expander("View PPDSVA Record"):
                    st.json(ppdsva.get("record", {}))
                
                # Step 4
                st.markdown('<div class="step-indicator"><span class="step-number">4</span><span class="step-text">Running Validations</span></div>', unsafe_allow_html=True)
                
                results = engine.run_full_validation(scenario, cosmos_resp, pph, ppdsva)
                
                # Metrics
                s = results.get("summary", {})
                st.markdown(f'''
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value success">{s.get("passed", 0)}</div>
                        <div class="metric-label">Passed</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value danger">{s.get("failed", 0)}</div>
                        <div class="metric-label">Failed</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value warning">{s.get("warnings", 0)}</div>
                        <div class="metric-label">Warnings</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value primary">{s.get("total", 0)}</div>
                        <div class="metric-label">Total</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                # Validation Details
                for sec_key, sec_data in results.get("sections", {}).items():
                    section_name = sec_data.get("section_name", sec_key)
                    icon = sec_data.get("icon", "📋")
                    
                    checks_html = ""
                    for chk in sec_data.get("checks", []):
                        status = chk["status"]
                        badge_class = {"PASS": "badge-success", "FAIL": "badge-danger", "WARN": "badge-warning"}.get(status, "badge-info")
                        checks_html += f'''
                        <div class="validation-row">
                            <span class="validation-name">{chk["name"]}</span>
                            <div class="validation-values">
                                <span class="validation-expected">Expected: {chk["expected"]}</span>
                                <span class="validation-actual">Actual: {chk["actual"]}</span>
                                <span class="badge {badge_class}">{status}</span>
                            </div>
                        </div>
                        '''
                    
                    st.markdown(f'''
                    <div class="validation-section">
                        <div class="validation-section-header">{icon} {section_name}</div>
                        {checks_html}
                    </div>
                    ''', unsafe_allow_html=True)
                
                # Overall Result
                if results.get("overall_status") == "PASS":
                    st.balloons()
                    st.success("🎉 All validations passed successfully!")
                elif results.get("overall_status") == "WARN":
                    st.warning("⚠️ Passed with warnings")
                else:
                    st.error("❌ Some validations failed")
    
    # TAB 2: SCENARIOS
    with tab2:
        st.markdown('<div class="section-header"><span class="section-header-icon">📋</span> Common Test Scenarios</div>', unsafe_allow_html=True)
        
        cols = st.columns(2)
        
        for idx, (key, scn) in enumerate(COMMON_SCENARIOS.items()):
            col = cols[idx % 2]
            
            with col:
                tags_html = "".join([f'<span class="tag">{t}</span>' for t in scn.get("tags", [])])
                
                st.markdown(f'''
                <div class="scenario-card">
                    <div class="scenario-header">
                        <span class="scenario-icon">{scn.get("icon", "📄")}</span>
                        <span class="scenario-title">{scn["name"]}</span>
                    </div>
                    <div class="scenario-desc">{scn["description"]}</div>
                    <div class="scenario-tags">{tags_html}</div>
                    <div style="margin-top: 0.75rem; font-size: 0.8rem; color: #6B7280;">
                        Expected: <span class="badge badge-info">RC {scn["expected_response_code"]}</span>
                        <span class="badge badge-info">{scn["expected_pph_status"]}</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                if st.button(f"▶️ Run", key=f"run_{key}", use_container_width=True):
                    stan, rrn = generate_stan(), generate_rrn()
                    ovr = scn["overrides"].copy()
                    ovr["DE11"] = stan
                    ovr["DE37"] = rrn
                    
                    full_scn = scn.copy()
                    full_scn["overrides"] = ovr
                    
                    with st.spinner("Running scenario..."):
                        cr = cosmos.send_transaction(scn["template"], ovr)
                        pph = db.query_pph_tran(rrn, stan)
                        ppdsva = db.query_ppdsva(rrn, stan)
                        res = engine.run_full_validation(full_scn, cr, pph, ppdsva)
                    
                    if res.get("overall_status") == "PASS":
                        st.success(f"✅ Passed - {res['summary']['passed']}/{res['summary']['total']} checks")
                    else:
                        st.error(f"❌ Failed - {res['summary']['failed']} failures")
    
    # TAB 3: SQL SCHEMA
    with tab3:
        st.markdown('<div class="section-header"><span class="section-header-icon">🗄️</span> Database Schema Reference</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### PPH_TRAN Table")
            
            rows_html = ""
            for col_name, info in PPH_TRAN_SCHEMA["columns"].items():
                rows_html += f'''
                <div class="schema-row">
                    <span class="schema-col">{col_name}</span>
                    <span class="schema-type">{info["type"]}</span>
                    <span class="schema-desc">{info["desc"]}</span>
                </div>
                '''
            
            st.markdown(f'''
            <div class="schema-table">
                <div class="schema-header">📋 {PPH_TRAN_SCHEMA["description"]}</div>
                {rows_html}
            </div>
            ''', unsafe_allow_html=True)
        
        with col2:
            st.markdown("### PPDSVA Table")
            
            rows_html = ""
            for col_name, info in PPDSVA_SCHEMA["columns"].items():
                rows_html += f'''
                <div class="schema-row">
                    <span class="schema-col">{col_name}</span>
                    <span class="schema-type">{info["type"]}</span>
                    <span class="schema-desc">{info["desc"]}</span>
                </div>
                '''
            
            st.markdown(f'''
            <div class="schema-table">
                <div class="schema-header">📊 {PPDSVA_SCHEMA["description"]}</div>
                {rows_html}
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown("### Sample SQL Queries")
        st.code("""
-- Query PPH_TRAN by RRN and STAN
SELECT * FROM PPH_TRAN 
WHERE RRN = :rrn AND STAN = :stan
ORDER BY CREATED_DT DESC;

-- Query PPDSVA by RRN and STAN  
SELECT * FROM PPDSVA 
WHERE RRN = :rrn AND STAN = :stan
ORDER BY CREATED_DT DESC;

-- Join PPH_TRAN and PPDSVA
SELECT t.TRAN_ID, t.TXN_AMT, t.TXN_STATUS, t.RESP_CODE,
       s.FRAUD_CHECK, s.RISK_SCORE, s.PROCESS_TIME_MS
FROM PPH_TRAN t
LEFT JOIN PPDSVA s ON t.TRAN_ID = s.TRAN_ID
WHERE t.RRN = :rrn;
        """, language="sql")
    
    # TAB 4: KARATE
    with tab4:
        st.markdown('<div class="section-header"><span class="section-header-icon">📝</span> Karate Feature Generator</div>', unsafe_allow_html=True)
        
        st.markdown("Generate Karate `.feature` files with SQL validation for PPH_TRAN and PPDSVA tables.")
        
        if st.button("🔧 Generate Karate Feature", use_container_width=True):
            feature = generate_karate_with_sql(selected_template, cosmos_url, db_config)
            st.code(feature, language="gherkin")
            st.download_button("📥 Download .feature", feature, f"{selected_template}_sql.feature", mime="text/plain")
    
    # TAB 5: PYTHON
    with tab5:
        st.markdown('<div class="section-header"><span class="section-header-icon">🐍</span> Python pytest Generator</div>', unsafe_allow_html=True)
        
        st.markdown("Generate Python pytest code with SQL validation for PPH_TRAN and PPDSVA tables.")
        
        if st.button("🐍 Generate Python Tests", use_container_width=True):
            code = generate_pytest_with_sql(selected_template, cosmos_url, db_config)
            st.code(code, language="python")
            st.download_button("📥 Download .py", code, f"test_{selected_template}_sql.py", mime="text/x-python")

if __name__ == "__main__":
    main()
