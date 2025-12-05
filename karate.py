"""
ISO8583 Karate Framework Studio - Complete Streamlit Application
=================================================================
"""

import streamlit as st
import json
import copy
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import random
import string
import re

# ============================================================================
# INLINE CONFIGURATION (from config.py)
# ============================================================================

ISO8583_FIELD_DEFINITIONS = {
    "DMTI": {"name": "Message Type Identifier", "length": 4},
    "BMP": {"name": "Bitmap", "length": 32},
    "DE2": {"name": "Primary Account Number", "length": 19},
    "DE3": {"name": "Processing Code", "length": 6},
    "DE4": {"name": "Amount, Transaction", "length": 12},
    "DE7": {"name": "Transmission Date and Time", "length": 10},
    "DE11": {"name": "System Trace Audit Number", "length": 6},
    "DE12": {"name": "Time, Local Transaction", "length": 6},
    "DE13": {"name": "Date, Local Transaction", "length": 4},
    "DE14": {"name": "Date, Expiration", "length": 4},
    "DE18": {"name": "Merchant Type", "length": 4},
    "DE22": {"name": "Point-of-Service Entry Mode", "length": 3},
    "DE32": {"name": "Acquiring Institution ID", "length": 11},
    "DE35": {"name": "Track 2 Data", "length": 37},
    "DE37": {"name": "Retrieval Reference Number", "length": 12},
    "DE38": {"name": "Authorization ID Response", "length": 6},
    "DE39": {"name": "Response Code", "length": 2},
    "DE41": {"name": "Terminal ID", "length": 8},
    "DE42": {"name": "Merchant ID", "length": 15},
    "DE43": {"name": "Merchant Name/Location", "length": 40},
    "DE49": {"name": "Currency Code", "length": 3},
}

RESPONSE_CODES = {
    "00": "Approved", "51": "Insufficient Funds", "54": "Expired Card",
    "14": "Invalid Card Number", "61": "Exceeds Limit", "62": "Restricted Card",
}

@dataclass
class ISO8583Template:
    name: str
    description: str
    mag_type: str
    re_encrypt: bool
    fields: Dict[str, str]
    
    def apply_overrides(self, overrides: Dict[str, str]) -> Dict[str, str]:
        merged = copy.deepcopy(self.fields)
        merged.update(overrides)
        return merged

# Templates based on uploaded image
TEMPLATES = {
    "fwd_visasig_direct_purchase_0100": ISO8583Template(
        name="fwd_visasig_direct_purchase_0100",
        description="Visa Signature Direct Purchase Authorization",
        mag_type="DPSISO0", re_encrypt=False,
        fields={
            "DMTI": "0100", "BMP": "FEFE5401A8E0E06A000000000820002",
            "DE2": "4144779500060809", "DE3": "000000",
            "DE4": "000000000700", "DE7": "0831053924",
            "DE11": "001212", "DE12": "133924", "DE13": "0831",
            "DE14": "2209", "DE18": "3535", "DE22": "900",
            "DE32": "59000000754", "DE35": "4144779500060809D220910112345129",
            "DE37": "024405001212", "DE41": "TERMID01",
            "DE42": "Visa / PLUS", "DE43": "QTP Execution CO COUS",
        }
    ),
    "fwd_mastercard_purchase_0100": ISO8583Template(
        name="fwd_mastercard_purchase_0100",
        description="MasterCard Purchase Authorization",
        mag_type="DPSISO0", re_encrypt=False,
        fields={
            "DMTI": "0100", "DE2": "5500000000000004", "DE3": "000000",
            "DE4": "000000001000", "DE11": "001213", "DE14": "2512",
            "DE18": "5411", "DE22": "051", "DE37": "024405001213",
            "DE41": "TERMID02", "DE42": "MasterCard",
        }
    ),
}

def generate_stan(): return str(random.randint(0, 999999)).zfill(6)
def generate_rrn(): return str(random.randint(0, 999999999999)).zfill(12)
def generate_auth_id(): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
def format_amount(amt): return str(int(amt * 100)).zfill(12)
def mask_pan(pan): return pan[:6] + "****" + pan[-4:] if len(pan) >= 12 else pan

# ============================================================================
# PAGE CONFIG & CSS
# ============================================================================

st.set_page_config(page_title="ISO8583 Karate Studio", page_icon="🥋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Orbitron:wght@700;900&display=swap');
.stApp { background: linear-gradient(135deg, #0a0a0f, #161b22); }
.main-title { font-family: 'Orbitron'; font-size: 2.8rem; font-weight: 900;
    background: linear-gradient(90deg, #00fff7, #ff00ff); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 0.5rem; }
.section-header { font-family: 'Orbitron'; font-size: 1.3rem; color: #00fff7;
    border-left: 4px solid #ff00ff; padding-left: 1rem; margin: 1.5rem 0 1rem; }
.panel { background: rgba(15,20,30,0.9); border: 1px solid rgba(0,255,247,0.2);
    border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }
.status-approved { background: rgba(0,255,136,0.15); border: 1px solid #00ff88;
    color: #00ff88; padding: 0.3rem 1rem; border-radius: 4px; font-weight: 600; }
.status-declined { background: rgba(255,0,100,0.15); border: 1px solid #ff0064;
    color: #ff0064; padding: 0.3rem 1rem; border-radius: 4px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# KARATE GENERATOR
# ============================================================================

def generate_karate_feature(template_name, base_url, include_neg=True, include_dd=True):
    tpl = TEMPLATES.get(template_name)
    if not tpl: return "Template not found"
    
    feature = f'''Feature: {tpl.description}
  Template: {template_name}
  
  Background:
    * url '{base_url}'
    * def templateName = '{template_name}'
    * def generateSTAN = function(){{ return Math.floor(Math.random() * 999999).toString().padStart(6, '0') }}
    * def generateRRN = function(){{ return Math.floor(Math.random() * 999999999999).toString().padStart(12, '0') }}
    * configure headers = {{ 'Content-Type': 'application/json' }}
    
  @smoke @authorization @template
  Scenario: Send 0100 using template with no overrides
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    Given path '/api/v1/iso8583/authorize'
    And header X-Template-Name = templateName
    And request {{ "templateName": "#(templateName)", "overrides": {{ "DE11": "#(stan)", "DE37": "#(rrn)" }} }}
    When method post
    Then status 200
    And match response.mti == '0110'
    And match response.responseCode == '00'
    And match response.dataElements.DE38 == '#notnull'
    
  @authorization @template @override
  Scenario: Send 0100 with amount override
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    Given path '/api/v1/iso8583/authorize'
    And request {{ "templateName": "#(templateName)", "overrides": {{ "DE4": "000000025000", "DE11": "#(stan)", "DE37": "#(rrn)" }} }}
    When method post
    Then status 200
    And match response.mti == '0110'
    And match response.responseCode == '00'
'''
    
    if include_neg:
        feature += '''
  @negative @authorization
  Scenario: 0100 with insufficient funds
    * def stan = generateSTAN()
    Given path '/api/v1/iso8583/authorize'
    And request { "templateName": "#(templateName)", "overrides": { "DE2": "4111111111111112", "DE4": "999999999999", "DE11": "#(stan)" } }
    When method post
    Then status 200
    And match response.dataElements.DE39 == '51'
    
  @negative @authorization  
  Scenario: 0100 with expired card
    * def stan = generateSTAN()
    Given path '/api/v1/iso8583/authorize'
    And request { "templateName": "#(templateName)", "overrides": { "DE14": "2001", "DE11": "#(stan)" } }
    When method post
    Then status 200
    And match response.dataElements.DE39 == '54'
'''
    
    if include_dd:
        feature += '''
  @regression @data-driven
  Scenario Outline: 0100 with various amounts
    * def stan = generateSTAN()
    Given path '/api/v1/iso8583/authorize'
    And request { "templateName": "#(templateName)", "overrides": { "DE4": "<amount>", "DE11": "#(stan)" } }
    When method post
    Then status <status>
    And match response.dataElements.DE39 == '<respCode>'
    
    Examples:
      | amount       | status | respCode |
      | 000000010000 | 200    | 00       |
      | 000000100000 | 200    | 00       |
      | 999999999999 | 200    | 51       |
'''
    return feature

# ============================================================================
# PYTEST MIGRATOR
# ============================================================================

def generate_pytest_code(template_name):
    return f'''"""
ISO8583 Tests - Migrated from Karate
Template: {template_name}
"""
import pytest
import requests
import random

class Config:
    BASE_URL = "http://localhost:8080"
    HEADERS = {{"Content-Type": "application/json"}}

def generate_stan(): return str(random.randint(0, 999999)).zfill(6)
def generate_rrn(): return str(random.randint(0, 999999999999)).zfill(12)

@pytest.fixture
def api_session():
    session = requests.Session()
    session.headers.update(Config.HEADERS)
    yield session
    session.close()

class TestISO8583Authorization:
    """Template-based ISO8583 0100 tests"""
    
    ENDPOINT = "/api/v1/iso8583/authorize"
    TEMPLATE = "{template_name}"
    
    def test_send_0100_no_overrides(self, api_session):
        """Equivalent to Karate: Send 0100 using template with no overrides"""
        stan, rrn = generate_stan(), generate_rrn()
        payload = {{"templateName": self.TEMPLATE, "overrides": {{"DE11": stan, "DE37": rrn}}}}
        
        response = api_session.post(f"{{Config.BASE_URL}}{{self.ENDPOINT}}", json=payload)
        
        assert response.status_code == 200
        assert response.json().get("mti") == "0110"
        assert response.json().get("responseCode") == "00"
        assert response.json().get("dataElements", {{}}).get("DE38") is not None
    
    def test_send_0100_with_amount_override(self, api_session):
        """Equivalent to Karate: Send 0100 with amount override"""
        stan = generate_stan()
        payload = {{"templateName": self.TEMPLATE, "overrides": {{"DE4": "000000025000", "DE11": stan}}}}
        
        response = api_session.post(f"{{Config.BASE_URL}}{{self.ENDPOINT}}", json=payload)
        
        assert response.status_code == 200
        assert response.json().get("responseCode") == "00"
    
    @pytest.mark.parametrize("amount,expected_code", [
        ("000000010000", "00"),
        ("000000100000", "00"),
        ("999999999999", "51"),
    ])
    def test_amount_variations(self, api_session, amount, expected_code):
        """Equivalent to Karate Scenario Outline"""
        stan = generate_stan()
        payload = {{"templateName": self.TEMPLATE, "overrides": {{"DE4": amount, "DE11": stan}}}}
        
        response = api_session.post(f"{{Config.BASE_URL}}{{self.ENDPOINT}}", json=payload)
        
        assert response.status_code == 200
        assert response.json().get("dataElements", {{}}).get("DE39") == expected_code

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

# ============================================================================
# TRANSACTION SIMULATOR
# ============================================================================

def simulate_transaction(template_name, overrides):
    template = TEMPLATES.get(template_name)
    if not template: return {"error": "Template not found", "status": 404}
    
    merged = template.apply_overrides(overrides)
    merged["DE11"] = overrides.get("DE11", generate_stan())
    merged["DE37"] = overrides.get("DE37", generate_rrn())
    
    pan, amount, expiry = merged.get("DE2", ""), merged.get("DE4", "0"), merged.get("DE14", "2512")
    
    resp_code = "00"
    if "1112" in pan: resp_code = "51"
    elif int(expiry[:2]) < 24: resp_code = "54"
    elif int(amount) > 500000000000: resp_code = "61"
    elif "INVALID" in pan.upper(): return {"error": "Invalid Card", "errorCode": "14", "status": 400}
    
    response = {
        "mti": "0110", "responseCode": resp_code, "responseMessage": RESPONSE_CODES.get(resp_code, "Unknown"),
        "timestamp": datetime.now().isoformat(),
        "dataElements": {"DE2": mask_pan(pan), "DE11": merged["DE11"], "DE37": merged["DE37"], "DE39": resp_code},
        "status": 200
    }
    if resp_code == "00": response["dataElements"]["DE38"] = generate_auth_id()
    return response

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.markdown('<h1 class="main-title">🥋 ISO8583 Karate Studio</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        base_url = st.text_input("Base URL", "http://localhost:8080")
        st.markdown("### 📋 Templates")
        selected_tpl = st.selectbox("Select Template", list(TEMPLATES.keys()))
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Transaction", "📝 Karate", "🔄 Migration", "📖 Reference"])
    
    with tab1:
        st.markdown('<h2 class="section-header">Send 0100 Transaction</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            tpl = TEMPLATES[selected_tpl]
            st.markdown(f'<div class="panel"><b>{tpl.name}</b><br>{tpl.description}</div>', unsafe_allow_html=True)
            
            with st.expander("📋 Template Fields"):
                st.json(tpl.fields)
            
            st.markdown("#### Overrides")
            ovr_pan = st.text_input("DE2 - PAN", placeholder="Leave empty for template value")
            ovr_amt = st.number_input("DE4 - Amount ($)", min_value=0.0, step=0.01)
            ovr_term = st.text_input("DE41 - Terminal ID", placeholder="Template value")
            
            overrides = {}
            if ovr_pan: overrides["DE2"] = ovr_pan
            if ovr_amt > 0: overrides["DE4"] = format_amount(ovr_amt)
            if ovr_term: overrides["DE41"] = ovr_term
            
            if st.button("🚀 SEND", use_container_width=True):
                result = simulate_transaction(selected_tpl, overrides)
                st.session_state.result = result
        
        with col2:
            st.markdown("#### Result")
            if "result" in st.session_state:
                r = st.session_state.result
                if r.get("status") == 200:
                    rc = r.get("responseCode")
                    status_class = "status-approved" if rc == "00" else "status-declined"
                    status_text = "✓ APPROVED" if rc == "00" else "✗ DECLINED"
                    st.markdown(f'<span class="{status_class}">{status_text}</span>', unsafe_allow_html=True)
                    st.json(r.get("dataElements", {}))
                else:
                    st.error(r.get("error"))
    
    with tab2:
        st.markdown('<h2 class="section-header">Karate Scenarios</h2>', unsafe_allow_html=True)
        
        inc_neg = st.checkbox("Include Negative Tests", True)
        inc_dd = st.checkbox("Include Data-Driven", True)
        
        if st.button("🔧 Generate Karate Feature"):
            feature = generate_karate_feature(selected_tpl, base_url, inc_neg, inc_dd)
            st.code(feature, language="gherkin")
            st.download_button("📥 Download .feature", feature, f"{selected_tpl}.feature")
    
    with tab3:
        st.markdown('<h2 class="section-header">Migration Tool</h2>', unsafe_allow_html=True)
        
        if st.button("🔄 Generate Python pytest"):
            pytest_code = generate_pytest_code(selected_tpl)
            st.code(pytest_code, language="python")
            st.download_button("📥 Download .py", pytest_code, f"test_{selected_tpl}.py")
        
        with st.expander("📊 Assertion Mapping Cheatsheet"):
            st.markdown("""
| Karate | Python |
|--------|--------|
| `match response.field == #notnull` | `assert response.json().get('field') is not None` |
| `match response.field == #string` | `assert isinstance(response.json()['field'], str)` |
| `match response.mti == '0110'` | `assert response.json()['mti'] == '0110'` |
| `status 200` | `assert response.status_code == 200` |
| `match response contains {...}` | `assert 'key' in response.json()` |
            """)
    
    with tab4:
        st.markdown('<h2 class="section-header">ISO8583 Reference</h2>', unsafe_allow_html=True)
        
        st.markdown("### Response Codes")
        for code, msg in RESPONSE_CODES.items():
            st.markdown(f"**{code}**: {msg}")
        
        st.markdown("### Field Definitions")
        for fid, fdef in ISO8583_FIELD_DEFINITIONS.items():
            st.markdown(f"`{fid}` - {fdef['name']}")

if __name__ == "__main__":
    main()