"""
ISO8583 COSMOS Studio Pro - Complete E2E Validation
====================================================
Features:
1. Send requests using COSMOS Simulator
2. Validate COSMOS response
3. SQL Validation for PPH_TRAN records
4. SQL Validation for PPDSVA records  
5. Call common scenarios from feature files
6. Enhanced Professional UI
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
    "00": {"message": "Approved", "type": "approved", "icon": "✅"},
    "01": {"message": "Refer to Issuer", "type": "declined", "icon": "❌"},
    "05": {"message": "Do Not Honor", "type": "declined", "icon": "❌"},
    "14": {"message": "Invalid Card", "type": "declined", "icon": "❌"},
    "51": {"message": "Insufficient Funds", "type": "declined", "icon": "❌"},
    "54": {"message": "Expired Card", "type": "declined", "icon": "❌"},
    "61": {"message": "Exceeds Limit", "type": "declined", "icon": "❌"},
    "62": {"message": "Restricted Card", "type": "declined", "icon": "❌"},
}

# ============================================================================
# PPH_TRAN SCHEMA
# ============================================================================

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

# ============================================================================
# PPDSVA SCHEMA
# ============================================================================

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
        "tags": ["smoke", "positive"]
    },
    "declined_insufficient_funds": {
        "name": "Declined - Insufficient Funds",
        "description": "Transaction declined due to insufficient funds",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE2": "4111111111111112", "DE4": "999999999999"},
        "expected_response_code": "51",
        "expected_pph_status": "DECLINED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["negative", "decline"]
    },
    "declined_expired_card": {
        "name": "Declined - Expired Card",
        "description": "Transaction declined due to expired card",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE14": "2001"},
        "expected_response_code": "54",
        "expected_pph_status": "DECLINED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["negative", "expired"]
    },
    "high_value_purchase": {
        "name": "High Value Purchase",
        "description": "High value purchase within limits",
        "template": "fwd_visasig_direct_purchase_0100",
        "overrides": {"DE4": "000000500000"},
        "expected_response_code": "00",
        "expected_pph_status": "COMPLETED",
        "expected_ppdsva_fraud": "PASS",
        "tags": ["regression", "high-value"]
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
# DATABASE CLIENT (Mock + Real)
# ============================================================================

class DatabaseClient:
    def __init__(self, host="", port=1521, service="", user="", pwd="", use_mock=True):
        self.use_mock = use_mock
        self.host = host
        self.port = port
        self.service = service
        self.user = user
        self.pwd = pwd
    
    def query_pph_tran(self, rrn: str, stan: str) -> Dict:
        if self.use_mock:
            return self._mock_pph_tran(rrn, stan)
        # Real DB query would go here
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
        
        # COSMOS Response validation
        results["sections"]["cosmos"] = self._validate_cosmos(scenario, cosmos_resp)
        
        # PPH_TRAN validation
        results["sections"]["pph_tran"] = self._validate_pph_tran(scenario, cosmos_resp, pph)
        
        # PPDSVA validation
        results["sections"]["ppdsva"] = self._validate_ppdsva(scenario, cosmos_resp, ppdsva)
        
        # Calculate summary
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
        
        # MTI check
        actual_mti = data.get("mti") or data.get("DMTI")
        checks.append({
            "name": "Response MTI",
            "expected": "0110",
            "actual": actual_mti,
            "status": "PASS" if actual_mti == "0110" else "FAIL"
        })
        
        # Response code
        actual_rc = data.get("DE39") or data.get("responseCode")
        checks.append({
            "name": "Response Code (DE39)",
            "expected": expected_rc,
            "actual": actual_rc,
            "status": "PASS" if actual_rc == expected_rc else "FAIL"
        })
        
        # Auth ID for approved
        if expected_rc == "00":
            auth_id = data.get("DE38")
            checks.append({
                "name": "Auth ID (DE38)",
                "expected": "Present",
                "actual": auth_id or "NULL",
                "status": "PASS" if auth_id else "FAIL"
            })
        
        return {"section_name": "COSMOS Response Validation", "checks": checks}
    
    def _validate_pph_tran(self, scenario: Dict, cosmos_resp: Dict, pph: Dict) -> Dict:
        checks = []
        record = pph.get("record", {})
        
        if not pph.get("success"):
            checks.append({"name": "PPH_TRAN Record", "expected": "Found", "actual": "Not Found", "status": "FAIL"})
            return {"section_name": "PPH_TRAN SQL Validation", "checks": checks}
        
        checks.append({"name": "PPH_TRAN Record", "expected": "Found", "actual": "Found", "status": "PASS"})
        
        # Status check
        expected_status = scenario.get("expected_pph_status", "COMPLETED")
        actual_status = record.get("TXN_STATUS")
        checks.append({
            "name": "Transaction Status",
            "expected": expected_status,
            "actual": actual_status,
            "status": "PASS" if actual_status == expected_status else "FAIL"
        })
        
        # Response code match
        cosmos_rc = cosmos_resp.get("response", {}).get("DE39")
        db_rc = record.get("RESP_CODE")
        checks.append({
            "name": "Response Code Match",
            "expected": cosmos_rc,
            "actual": db_rc,
            "status": "PASS" if db_rc == cosmos_rc else "FAIL"
        })
        
        # RRN match
        req_rrn = cosmos_resp.get("request", {}).get("overrides", {}).get("DE37")
        if req_rrn:
            db_rrn = record.get("RRN")
            checks.append({
                "name": "RRN Match",
                "expected": req_rrn,
                "actual": db_rrn,
                "status": "PASS" if db_rrn == req_rrn else "FAIL"
            })
        
        # STAN match
        req_stan = cosmos_resp.get("request", {}).get("overrides", {}).get("DE11")
        if req_stan:
            db_stan = record.get("STAN")
            checks.append({
                "name": "STAN Match",
                "expected": req_stan,
                "actual": db_stan,
                "status": "PASS" if db_stan == req_stan else "FAIL"
            })
        
        return {"section_name": "PPH_TRAN SQL Validation", "checks": checks}
    
    def _validate_ppdsva(self, scenario: Dict, cosmos_resp: Dict, ppdsva: Dict) -> Dict:
        checks = []
        record = ppdsva.get("record", {})
        
        if not ppdsva.get("success"):
            checks.append({"name": "PPDSVA Record", "expected": "Found", "actual": "Not Found", "status": "WARN"})
            return {"section_name": "PPDSVA SQL Validation", "checks": checks}
        
        checks.append({"name": "PPDSVA Record", "expected": "Found", "actual": "Found", "status": "PASS"})
        
        # Fraud check
        expected_fraud = scenario.get("expected_ppdsva_fraud", "PASS")
        actual_fraud = record.get("FRAUD_CHECK")
        checks.append({
            "name": "Fraud Check",
            "expected": expected_fraud,
            "actual": actual_fraud,
            "status": "PASS" if actual_fraud == expected_fraud else "WARN"
        })
        
        # Host response
        cosmos_rc = cosmos_resp.get("response", {}).get("DE39")
        host_rc = record.get("HOST_RESP_CODE")
        checks.append({
            "name": "Host Response Code",
            "expected": cosmos_rc,
            "actual": host_rc,
            "status": "PASS" if host_rc == cosmos_rc else "WARN"
        })
        
        # Risk score
        risk = record.get("RISK_SCORE", 0)
        checks.append({
            "name": "Risk Score",
            "expected": "< 50",
            "actual": str(risk),
            "status": "PASS" if float(risk) < 50 else "WARN"
        })
        
        # Processing time
        proc_time = record.get("PROCESS_TIME_MS", 0)
        checks.append({
            "name": "Processing Time",
            "expected": "< 3000ms",
            "actual": f"{proc_time}ms",
            "status": "PASS" if int(proc_time) < 3000 else "WARN"
        })
        
        return {"section_name": "PPDSVA SQL Validation", "checks": checks}

# ============================================================================
# KARATE GENERATOR
# ============================================================================

def generate_karate_with_sql(template_name: str, cosmos_url: str, db_config: Dict) -> str:
    template = TEMPLATES.get(template_name)
    if not template:
        return "# Template not found"
    
    return f'''Feature: {template.description} - E2E with SQL Validation

  Background:
    * url '{cosmos_url}'
    * def templateName = '{template_name}'
    * def generateSTAN = function(){{ return Math.floor(Math.random() * 999999).toString().padStart(6, '0') }}
    * def generateRRN = function(){{ return Math.floor(Math.random() * 999999999999).toString().padStart(12, '0') }}
    
    # Database config
    * def dbConfig = {{ host: '{db_config.get("host", "localhost")}', port: {db_config.get("port", 1521)}, service: '{db_config.get("service", "ORCL")}' }}
    
    # SQL Query helpers
    * def queryPphTran = 
    """
    function(rrn, stan) {{
      var DbUtils = Java.type('com.example.DbUtils');
      return DbUtils.query("SELECT * FROM PPH_TRAN WHERE RRN='" + rrn + "' AND STAN='" + stan + "'");
    }}
    """
    
    * def queryPpdsva = 
    """
    function(rrn, stan) {{
      var DbUtils = Java.type('com.example.DbUtils');
      return DbUtils.query("SELECT * FROM PPDSVA WHERE RRN='" + rrn + "' AND STAN='" + stan + "'");
    }}
    """

  # =========================================================================
  # COMMON SCENARIOS - Can be called from other features
  # =========================================================================
  
  @common @reusable
  Scenario: common_send_0100
    * def stan = __arg.stan || generateSTAN()
    * def rrn = __arg.rrn || generateRRN()
    * def overrides = __arg.overrides || {{}}
    * overrides.DE11 = stan
    * overrides.DE37 = rrn
    
    Given path '/template'
    And param id = templateName
    And param type = 'MessageTemplate'
    And request {{ templateId: '#(templateName)', overrides: '#(overrides)' }}
    When method post
    Then status 200
    * def cosmosResponse = response

  @common @reusable @sql
  Scenario: common_validate_pph_tran
    * def rrn = __arg.rrn
    * def stan = __arg.stan
    * def expectedStatus = __arg.expectedStatus || 'COMPLETED'
    
    * def pphRecord = queryPphTran(rrn, stan)
    * match pphRecord != null
    * match pphRecord.TXN_STATUS == expectedStatus
    * match pphRecord.RRN == rrn
    * match pphRecord.STAN == stan

  @common @reusable @sql
  Scenario: common_validate_ppdsva
    * def rrn = __arg.rrn
    * def stan = __arg.stan
    
    * def ppdsvaRecord = queryPpdsva(rrn, stan)
    * match ppdsvaRecord != null
    * match ppdsvaRecord.FRAUD_CHECK == 'PASS'
    * match ppdsvaRecord.RRN == rrn

  # =========================================================================
  # E2E TEST SCENARIOS
  # =========================================================================
  
  @smoke @e2e @sql
  Scenario: E2E Approved Purchase - Validate COSMOS, PPH_TRAN, PPDSVA
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    
    # Step 1: Send to COSMOS
    * def result = call read('this@common_send_0100') {{ stan: '#(stan)', rrn: '#(rrn)' }}
    * match result.cosmosResponse.DE39 == '00'
    * match result.cosmosResponse.DE38 == '#notnull'
    
    # Step 2: Validate PPH_TRAN
    * call read('this@common_validate_pph_tran') {{ rrn: '#(rrn)', stan: '#(stan)', expectedStatus: 'COMPLETED' }}
    
    # Step 3: Validate PPDSVA
    * call read('this@common_validate_ppdsva') {{ rrn: '#(rrn)', stan: '#(stan)' }}

  @negative @e2e @sql
  Scenario: E2E Declined - Insufficient Funds
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    * def overrides = {{ DE2: '4111111111111112', DE4: '999999999999' }}
    
    * def result = call read('this@common_send_0100') {{ stan: '#(stan)', rrn: '#(rrn)', overrides: '#(overrides)' }}
    * match result.cosmosResponse.DE39 == '51'
    
    * call read('this@common_validate_pph_tran') {{ rrn: '#(rrn)', stan: '#(stan)', expectedStatus: 'DECLINED' }}

  @regression @data-driven @sql
  Scenario Outline: E2E Data-Driven with SQL Validation
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    
    Given path '/template'
    And param id = templateName
    And request {{ templateId: '#(templateName)', overrides: {{ DE4: '<amount>', DE11: '#(stan)', DE37: '#(rrn)' }} }}
    When method post
    Then status 200
    And match response.DE39 == '<expectedRC>'
    
    * def pphRecord = queryPphTran(rrn, stan)
    * match pphRecord.TXN_STATUS == '<expectedStatus>'
    
    * def ppdsvaRecord = queryPpdsva(rrn, stan)
    * match ppdsvaRecord.HOST_RESP_CODE == '<expectedRC>'
    
    Examples:
      | amount       | expectedRC | expectedStatus |
      | 000000010000 | 00         | COMPLETED      |
      | 000000100000 | 00         | COMPLETED      |
      | 999999999999 | 51         | DECLINED       |
'''

# ============================================================================
# PYTEST GENERATOR
# ============================================================================

def generate_pytest_with_sql(template_name: str, cosmos_url: str, db_config: Dict) -> str:
    return f'''"""
ISO8583 E2E Tests with SQL Validation
Template: {template_name}
"""
import pytest
import requests
import random
import cx_Oracle

class Config:
    COSMOS_URL = "{cosmos_url}"
    DB_HOST = "{db_config.get('host', 'localhost')}"
    DB_PORT = {db_config.get('port', 1521)}
    DB_SERVICE = "{db_config.get('service', 'ORCL')}"
    TEMPLATE = "{template_name}"

def generate_stan(): return str(random.randint(0, 999999)).zfill(6)
def generate_rrn(): return str(random.randint(0, 999999999999)).zfill(12)

class DatabaseUtils:
    @staticmethod
    def query_pph_tran(rrn: str, stan: str):
        dsn = cx_Oracle.makedsn(Config.DB_HOST, Config.DB_PORT, service_name=Config.DB_SERVICE)
        conn = cx_Oracle.connect("user", "pass", dsn)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PPH_TRAN WHERE RRN=:rrn AND STAN=:stan", {{"rrn": rrn, "stan": stan}})
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        conn.close()
        return dict(zip(cols, row)) if row else None
    
    @staticmethod
    def query_ppdsva(rrn: str, stan: str):
        dsn = cx_Oracle.makedsn(Config.DB_HOST, Config.DB_PORT, service_name=Config.DB_SERVICE)
        conn = cx_Oracle.connect("user", "pass", dsn)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PPDSVA WHERE RRN=:rrn AND STAN=:stan", {{"rrn": rrn, "stan": stan}})
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        conn.close()
        return dict(zip(cols, row)) if row else None

@pytest.fixture
def api_session():
    s = requests.Session()
    s.headers.update({{"Content-Type": "application/json"}})
    yield s
    s.close()

class TestE2EWithSQL:
    
    def send_to_cosmos(self, session, overrides):
        payload = {{"templateId": Config.TEMPLATE, "overrides": overrides}}
        r = session.post(f"{{Config.COSMOS_URL}}/template?id={{Config.TEMPLATE}}&type=MessageTemplate", json=payload)
        return r.json() if r.status_code == 200 else None
    
    @pytest.mark.smoke
    @pytest.mark.sql
    def test_e2e_approved_with_sql(self, api_session):
        stan, rrn = generate_stan(), generate_rrn()
        
        # Send to COSMOS
        resp = self.send_to_cosmos(api_session, {{"DE11": stan, "DE37": rrn}})
        assert resp["DE39"] == "00"
        assert resp["DE38"] is not None
        
        # Validate PPH_TRAN
        pph = DatabaseUtils.query_pph_tran(rrn, stan)
        assert pph is not None
        assert pph["TXN_STATUS"] == "COMPLETED"
        assert pph["RESP_CODE"] == "00"
        
        # Validate PPDSVA
        ppdsva = DatabaseUtils.query_ppdsva(rrn, stan)
        assert ppdsva is not None
        assert ppdsva["FRAUD_CHECK"] == "PASS"
    
    @pytest.mark.negative
    @pytest.mark.sql
    @pytest.mark.parametrize("pan,amount,exp_rc,exp_status", [
        ("4111111111111112", "999999999999", "51", "DECLINED"),
    ])
    def test_declined_with_sql(self, api_session, pan, amount, exp_rc, exp_status):
        stan, rrn = generate_stan(), generate_rrn()
        resp = self.send_to_cosmos(api_session, {{"DE2": pan, "DE4": amount, "DE11": stan, "DE37": rrn}})
        assert resp["DE39"] == exp_rc
        
        pph = DatabaseUtils.query_pph_tran(rrn, stan)
        assert pph["TXN_STATUS"] == exp_status
'''

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="ISO8583 COSMOS Studio Pro", page_icon="🥋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Fira+Code:wght@400;600&family=Rajdhani:wght@500;700&display=swap');

:root {
    --cyan: #00fff7; --magenta: #ff00ff; --green: #00ff88;
    --red: #ff3860; --yellow: #ffd700; --bg: #0a0e17;
}

.stApp { background: linear-gradient(135deg, #0a0e17, #111827); }

.main-title {
    font-family: 'Orbitron', sans-serif; font-size: 2.5rem; font-weight: 900;
    background: linear-gradient(90deg, var(--cyan), var(--magenta));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-align: center; margin-bottom: 0.5rem;
}

.subtitle {
    font-family: 'Rajdhani', sans-serif; font-size: 1rem;
    color: #8b949e; text-align: center; letter-spacing: 0.2em;
    text-transform: uppercase; margin-bottom: 2rem;
}

.section-header {
    font-family: 'Orbitron', sans-serif; font-size: 1.2rem; color: var(--cyan);
    border-left: 4px solid var(--magenta); padding-left: 1rem; margin: 1.5rem 0 1rem;
}

.card {
    background: rgba(26, 31, 46, 0.8); border: 1px solid rgba(0, 255, 247, 0.2);
    border-radius: 10px; padding: 1.5rem; margin: 1rem 0;
}

.status-pass { background: rgba(0,255,136,0.15); border: 1px solid var(--green); color: var(--green); padding: 0.2rem 0.6rem; border-radius: 4px; font-family: 'Fira Code'; font-size: 0.8rem; }
.status-fail { background: rgba(255,56,96,0.15); border: 1px solid var(--red); color: var(--red); padding: 0.2rem 0.6rem; border-radius: 4px; font-family: 'Fira Code'; font-size: 0.8rem; }
.status-warn { background: rgba(255,215,0,0.15); border: 1px solid var(--yellow); color: var(--yellow); padding: 0.2rem 0.6rem; border-radius: 4px; font-family: 'Fira Code'; font-size: 0.8rem; }

.metric-box { background: rgba(0,0,0,0.3); border: 1px solid rgba(0,255,247,0.2); border-radius: 8px; padding: 1rem; text-align: center; }
.metric-val { font-family: 'Orbitron'; font-size: 2rem; font-weight: 700; }
.metric-val.green { color: var(--green); }
.metric-val.red { color: var(--red); }
.metric-val.yellow { color: var(--yellow); }
.metric-label { font-family: 'Rajdhani'; font-size: 0.8rem; color: #8b949e; text-transform: uppercase; }

.step-badge { font-family: 'Orbitron'; font-size: 0.85rem; color: var(--magenta); margin: 1rem 0 0.5rem; }

.schema-row { display: grid; grid-template-columns: 140px 120px 1fr; padding: 0.4rem 0.8rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-family: 'Fira Code'; font-size: 0.75rem; }
.schema-col { color: var(--magenta); }
.schema-type { color: var(--yellow); }
.schema-desc { color: #8b949e; }

.tag { background: rgba(0,255,247,0.1); border: 1px solid rgba(0,255,247,0.3); color: var(--cyan); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-family: 'Fira Code'; margin-right: 0.3rem; }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<h1 class="main-title">🥋 ISO8583 COSMOS STUDIO PRO</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">COSMOS • PPH_TRAN • PPDSVA • Common Scenarios • SQL Validation</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        use_mock = st.checkbox("🔧 Mock Mode", value=True)
        
        st.markdown("**COSMOS**")
        cosmos_url = st.text_input("URL", "http://10.160.59.86:8080", disabled=use_mock)
        
        st.markdown("**Database**")
        db_host = st.text_input("Host", "localhost", disabled=use_mock)
        db_port = st.number_input("Port", value=1521, disabled=use_mock)
        db_service = st.text_input("Service", "ORCL", disabled=use_mock)
        
        db_config = {"host": db_host, "port": db_port, "service": db_service}
        
        st.markdown("**Template**")
        selected_template = st.selectbox("Select", list(TEMPLATES.keys()))
    
    # Clients
    cosmos = COSMOSClient(cosmos_url, use_mock)
    db = DatabaseClient(db_host, db_port, db_service, use_mock=use_mock)
    engine = ValidationEngine(cosmos, db)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 E2E Validation", "📋 Common Scenarios", "🗄️ SQL Schema", "📝 Karate", "🐍 Python"])
    
    # TAB 1: E2E VALIDATION
    with tab1:
        st.markdown('<h2 class="section-header">E2E Transaction Validation</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            template = TEMPLATES[selected_template]
            st.markdown(f'<div class="card"><b>{template.name}</b><br><small>{template.description}</small></div>', unsafe_allow_html=True)
            
            with st.expander("📋 Template Fields"):
                st.json(template.fields)
            
            st.markdown("**Overrides**")
            ovr_pan = st.text_input("DE2 - PAN")
            ovr_amt = st.number_input("DE4 - Amount ($)", min_value=0.0, step=0.01)
            ovr_exp = st.text_input("DE14 - Expiry (YYMM)")
            
            st.markdown("**Expected**")
            exp_rc = st.selectbox("Response Code", list(RESPONSE_CODES.keys()), format_func=lambda x: f"{x} - {RESPONSE_CODES[x]['message']}")
            exp_status = st.selectbox("DB Status", ["COMPLETED", "DECLINED", "REJECTED"])
            
            overrides = {}
            if ovr_pan: overrides["DE2"] = ovr_pan
            if ovr_amt > 0: overrides["DE4"] = format_amount(ovr_amt)
            if ovr_exp: overrides["DE14"] = ovr_exp
            
            stan, rrn = generate_stan(), generate_rrn()
            overrides["DE11"] = stan
            overrides["DE37"] = rrn
            
            scenario = {"name": "Custom", "template": selected_template, "overrides": overrides,
                       "expected_response_code": exp_rc, "expected_pph_status": exp_status, "expected_ppdsva_fraud": "PASS"}
            
            st.info(f"STAN: `{stan}` | RRN: `{rrn}`")
            
            run = st.button("🚀 RUN E2E VALIDATION", use_container_width=True)
        
        with col2:
            if run:
                st.markdown('<div class="step-badge">▶ STEP 1: Send to COSMOS</div>', unsafe_allow_html=True)
                cosmos_resp = cosmos.send_transaction(selected_template, overrides)
                st.success("✅ Sent") if cosmos_resp.get("success") else st.error("❌ Failed")
                
                with st.expander("COSMOS Response"):
                    st.json(cosmos_resp.get("response", {}))
                
                st.markdown('<div class="step-badge">▶ STEP 2: Query PPH_TRAN</div>', unsafe_allow_html=True)
                pph = db.query_pph_tran(rrn, stan)
                st.success("✅ Found") if pph.get("success") else st.warning("⚠️ Not found")
                
                with st.expander("PPH_TRAN Record"):
                    st.json(pph.get("record", {}))
                
                st.markdown('<div class="step-badge">▶ STEP 3: Query PPDSVA</div>', unsafe_allow_html=True)
                ppdsva = db.query_ppdsva(rrn, stan)
                st.success("✅ Found") if ppdsva.get("success") else st.warning("⚠️ Not found")
                
                with st.expander("PPDSVA Record"):
                    st.json(ppdsva.get("record", {}))
                
                st.markdown('<div class="step-badge">▶ STEP 4: Validate All</div>', unsafe_allow_html=True)
                results = engine.run_full_validation(scenario, cosmos_resp, pph, ppdsva)
                
                # Summary
                s = results.get("summary", {})
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.markdown(f'<div class="metric-box"><div class="metric-val green">{s.get("passed",0)}</div><div class="metric-label">Passed</div></div>', unsafe_allow_html=True)
                with c2: st.markdown(f'<div class="metric-box"><div class="metric-val red">{s.get("failed",0)}</div><div class="metric-label">Failed</div></div>', unsafe_allow_html=True)
                with c3: st.markdown(f'<div class="metric-box"><div class="metric-val yellow">{s.get("warnings",0)}</div><div class="metric-label">Warnings</div></div>', unsafe_allow_html=True)
                with c4: st.markdown(f'<div class="metric-box"><div class="metric-val">{s.get("total",0)}</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
                
                # Details
                for sec_key, sec_data in results.get("sections", {}).items():
                    st.markdown(f"**{sec_data.get('section_name', sec_key)}**")
                    for chk in sec_data.get("checks", []):
                        status_class = {"PASS": "status-pass", "FAIL": "status-fail", "WARN": "status-warn"}.get(chk["status"], "")
                        st.markdown(f'<span class="{status_class}">{chk["status"]}</span> {chk["name"]}: Expected `{chk["expected"]}` | Actual `{chk["actual"]}`', unsafe_allow_html=True)
                
                if results.get("overall_status") == "PASS":
                    st.balloons()
                    st.success("🎉 ALL VALIDATIONS PASSED!")
                else:
                    st.error("❌ SOME VALIDATIONS FAILED")
    
    # TAB 2: COMMON SCENARIOS
    with tab2:
        st.markdown('<h2 class="section-header">Common Scenarios</h2>', unsafe_allow_html=True)
        
        for key, scn in COMMON_SCENARIOS.items():
            tags_html = "".join([f'<span class="tag">{t}</span>' for t in scn.get("tags", [])])
            st.markdown(f'''
            <div class="card">
                <b>{scn["name"]}</b> {tags_html}<br>
                <small>{scn["description"]}</small><br>
                <small>Expected: RC={scn["expected_response_code"]} | PPH={scn["expected_pph_status"]} | Fraud={scn["expected_ppdsva_fraud"]}</small>
            </div>
            ''', unsafe_allow_html=True)
            
            if st.button(f"▶️ Run {scn['name']}", key=f"run_{key}"):
                stan, rrn = generate_stan(), generate_rrn()
                ovr = scn["overrides"].copy()
                ovr["DE11"] = stan
                ovr["DE37"] = rrn
                
                full_scn = scn.copy()
                full_scn["overrides"] = ovr
                
                with st.spinner("Running..."):
                    cr = cosmos.send_transaction(scn["template"], ovr)
                    pph = db.query_pph_tran(rrn, stan)
                    ppdsva = db.query_ppdsva(rrn, stan)
                    res = engine.run_full_validation(full_scn, cr, pph, ppdsva)
                
                if res.get("overall_status") == "PASS":
                    st.success(f"✅ PASSED - {res['summary']['passed']}/{res['summary']['total']}")
                else:
                    st.error(f"❌ FAILED - {res['summary']['failed']} failures")
    
    # TAB 3: SQL SCHEMA
    with tab3:
        st.markdown('<h2 class="section-header">Database Schema</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### PPH_TRAN")
            for col, info in PPH_TRAN_SCHEMA["columns"].items():
                st.markdown(f'<div class="schema-row"><span class="schema-col">{col}</span><span class="schema-type">{info["type"]}</span><span class="schema-desc">{info["desc"]}</span></div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("### PPDSVA")
            for col, info in PPDSVA_SCHEMA["columns"].items():
                st.markdown(f'<div class="schema-row"><span class="schema-col">{col}</span><span class="schema-type">{info["type"]}</span><span class="schema-desc">{info["desc"]}</span></div>', unsafe_allow_html=True)
        
        st.markdown("### Sample Queries")
        st.code("""
-- PPH_TRAN by RRN/STAN
SELECT * FROM PPH_TRAN WHERE RRN = :rrn AND STAN = :stan;

-- PPDSVA by RRN/STAN  
SELECT * FROM PPDSVA WHERE RRN = :rrn AND STAN = :stan;

-- Join both tables
SELECT t.*, s.FRAUD_CHECK, s.RISK_SCORE
FROM PPH_TRAN t
LEFT JOIN PPDSVA s ON t.TRAN_ID = s.TRAN_ID
WHERE t.RRN = :rrn;
        """, language="sql")
    
    # TAB 4: KARATE
    with tab4:
        st.markdown('<h2 class="section-header">Karate Feature Generator</h2>', unsafe_allow_html=True)
        
        if st.button("🔧 Generate Karate with SQL", use_container_width=True):
            feature = generate_karate_with_sql(selected_template, cosmos_url, db_config)
            st.code(feature, language="gherkin")
            st.download_button("📥 Download .feature", feature, f"{selected_template}_sql.feature")
    
    # TAB 5: PYTHON
    with tab5:
        st.markdown('<h2 class="section-header">Python pytest Generator</h2>', unsafe_allow_html=True)
        
        if st.button("🐍 Generate Python with SQL", use_container_width=True):
            code = generate_pytest_with_sql(selected_template, cosmos_url, db_config)
            st.code(code, language="python")
            st.download_button("📥 Download .py", code, f"test_{selected_template}_sql.py")

if __name__ == "__main__":
    main()
