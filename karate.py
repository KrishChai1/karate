"""
🥋 AI Karate Test Generator Pro
================================
Beautiful Modern UI Edition
"""

import streamlit as st
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import random

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TransactionTemplate:
    id: str
    name: str
    description: str
    category: str
    card_network: str
    message_type: str
    processing_code: str
    fields: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    icon: str = "💳"
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ResponseCode:
    code: str
    message: str
    category: str
    trigger_field: str = ""
    trigger_value: str = ""

@dataclass 
class SQLTable:
    name: str
    description: str
    columns: Dict[str, Dict[str, str]] = field(default_factory=dict)
    key_columns: List[str] = field(default_factory=list)

# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

class KnowledgeBase:
    def __init__(self):
        self.templates: Dict[str, TransactionTemplate] = {}
        self.response_codes: Dict[str, ResponseCode] = {}
        self.sql_tables: Dict[str, SQLTable] = {}
        self.learned_patterns: Dict[str, Any] = {}
        self._load_defaults()
    
    def _load_defaults(self):
        templates = [
            TransactionTemplate("visa_purchase_0100", "fwd_visasig_direct_purchase_0100", "Visa Signature Purchase", "purchase", "visa", "0100", "000000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "000000", "DE4": "000000000700", "DE11": "{stan}", "DE14": "2512", "DE37": "{rrn}", "DE41": "TERMID01", "DE42": "MERCHANT01"},
                ["visa", "purchase", "signature"], "💳"),
            TransactionTemplate("mastercard_purchase_0100", "fwd_mastercard_purchase_0100", "MasterCard Purchase", "purchase", "mastercard", "0100", "000000",
                {"DMTI": "0100", "DE2": "5500000000000004", "DE3": "000000", "DE4": "000000001000", "DE11": "{stan}", "DE14": "2512", "DE37": "{rrn}", "DE41": "TERMID02"},
                ["mastercard", "purchase"], "💳"),
            TransactionTemplate("visa_atm_0100", "fwd_visa_atm_withdrawal_0100", "Visa ATM Withdrawal", "withdrawal", "visa", "0100", "010000",
                {"DMTI": "0100", "DE2": "4111111111111111", "DE3": "010000", "DE4": "000000005000", "DE11": "{stan}", "DE37": "{rrn}", "DE41": "ATM00001"},
                ["visa", "atm", "withdrawal"], "🏧"),
            TransactionTemplate("visa_refund_0100", "fwd_visa_refund_0100", "Visa Refund", "refund", "visa", "0100", "200000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "200000", "DE4": "000000000500", "DE11": "{stan}", "DE37": "{rrn}", "DE41": "TERMID01"},
                ["visa", "refund"], "↩️"),
            TransactionTemplate("visa_reversal_0400", "fwd_visa_reversal_0400", "Visa Reversal", "reversal", "visa", "0400", "000000",
                {"DMTI": "0400", "DE2": "4144779500060809", "DE3": "000000", "DE4": "000000000700", "DE11": "{stan}", "DE37": "{rrn}", "DE90": "{original}"},
                ["visa", "reversal"], "🔄"),
            TransactionTemplate("visa_balance_0100", "fwd_visa_balance_inquiry_0100", "Visa Balance Inquiry", "balance", "visa", "0100", "310000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "310000", "DE4": "000000000000", "DE11": "{stan}", "DE37": "{rrn}"},
                ["visa", "balance", "inquiry"], "💰"),
        ]
        for t in templates:
            self.templates[t.id] = t
        
        codes = [
            ResponseCode("00", "Approved", "approved"),
            ResponseCode("01", "Refer to Issuer", "declined"),
            ResponseCode("05", "Do Not Honor", "declined", "DE2", "4111111111111114"),
            ResponseCode("14", "Invalid Card", "declined", "DE2", "1234567890123456"),
            ResponseCode("51", "Insufficient Funds", "declined", "DE4", "999999999999"),
            ResponseCode("54", "Expired Card", "declined", "DE14", "2001"),
            ResponseCode("55", "Invalid PIN", "declined"),
            ResponseCode("61", "Exceeds Limit", "declined", "DE4", "500000000000"),
            ResponseCode("62", "Restricted Card", "declined", "DE2", "4111111111111113"),
        ]
        for rc in codes:
            self.response_codes[rc.code] = rc
        
        self.sql_tables["PPH_TRAN"] = SQLTable("PPH_TRAN", "Payment Hub Transaction",
            {"TRAN_ID": {"type": "VARCHAR2(36)", "desc": "UUID"}, "TXN_STATUS": {"type": "VARCHAR2(20)", "desc": "Status"},
             "RESP_CODE": {"type": "VARCHAR2(2)", "desc": "Response"}, "RRN": {"type": "VARCHAR2(12)", "desc": "RRN"},
             "STAN": {"type": "VARCHAR2(6)", "desc": "STAN"}, "TXN_AMT": {"type": "NUMBER", "desc": "Amount"}}, ["RRN", "STAN"])
        
        self.sql_tables["PPDSVA"] = SQLTable("PPDSVA", "Value Added Data",
            {"SVA_ID": {"type": "VARCHAR2(36)", "desc": "UUID"}, "FRAUD_CHECK": {"type": "VARCHAR2(10)", "desc": "Fraud"},
             "RISK_SCORE": {"type": "NUMBER", "desc": "Risk"}, "HOST_RESP_CODE": {"type": "VARCHAR2(4)", "desc": "Host RC"}}, ["RRN", "STAN"])
    
    def add_template(self, t): self.templates[t.id] = t
    def add_response_code(self, rc): self.response_codes[rc.code] = rc
    def add_sql_table(self, tbl): self.sql_tables[tbl.name] = tbl
    
    def export_json(self):
        return json.dumps({"templates": {k: v.to_dict() for k, v in self.templates.items()},
                          "response_codes": {k: asdict(v) for k, v in self.response_codes.items()}}, indent=2)
    
    def import_json(self, data):
        d = json.loads(data)
        for k, v in d.get("templates", {}).items():
            self.templates[k] = TransactionTemplate(**v)
        for k, v in d.get("response_codes", {}).items():
            self.response_codes[k] = ResponseCode(**v)

# ============================================================================
# ANALYZER & GENERATOR
# ============================================================================

class FeatureAnalyzer:
    def __init__(self, kb):
        self.kb = kb
        self.files = []
        self.patterns = {}
    
    def analyze(self, content, name="file"):
        steps = re.findall(r'^\s*[\*].*$', content, re.MULTILINE)
        scenarios = re.findall(r'Scenario.*?(?=Scenario|$)', content, re.DOTALL)
        for s in steps:
            norm = re.sub(r'["\'][^"\']+["\']', '"{val}"', s.strip())
            self.patterns[norm] = self.patterns.get(norm, 0) + 1
        self.files.append({"name": name, "steps": len(steps), "scenarios": len(scenarios)})
        return {"steps": len(steps), "scenarios": len(scenarios)}

class TestGenerator:
    def __init__(self, kb):
        self.kb = kb
    
    def generate(self, prompt, options=None):
        options = options or {}
        intent = self._parse(prompt)
        intent.update(options)
        template = self._find_template(intent)
        return self._build(intent, template)
    
    def _parse(self, prompt):
        p = prompt.lower()
        intent = {"type": "positive", "txn": "purchase", "network": "visa", "result": "approved", "decline": None, "amount": None, "sql": True, "common": True}
        
        if any(w in p for w in ["negative", "decline", "fail", "reject"]): intent["type"], intent["result"] = "negative", "declined"
        if "e2e" in p or "end-to-end" in p: intent["type"] = "e2e"
        
        for txn, kws in {"withdrawal": ["withdraw", "atm", "cash"], "refund": ["refund", "return"], "reversal": ["reversal", "void"], "balance": ["balance", "inquiry"]}.items():
            if any(k in p for k in kws): intent["txn"] = txn; break
        
        for net, kws in {"mastercard": ["mastercard", "mc"], "amex": ["amex"]}.items():
            if any(k in p for k in kws): intent["network"] = net; break
        
        for code, rc in self.kb.response_codes.items():
            if rc.category == "declined" and rc.message.lower().split()[0] in p:
                intent["decline"], intent["result"] = rc, "declined"; break
        
        m = re.search(r'\$(\d+)', prompt)
        if m: intent["amount"] = str(int(m.group(1)) * 100).zfill(12)
        
        return intent
    
    def _find_template(self, intent):
        best, score = None, -1
        for t in self.kb.templates.values():
            s = (10 if t.category == intent["txn"] else 0) + (5 if t.card_network == intent["network"] else 0)
            if s > score: best, score = t, s
        return best or list(self.kb.templates.values())[0]
    
    def _build(self, intent, template):
        lines = []
        tags = {intent["type"], template.category, template.card_network, "positive" if intent["result"] == "approved" else "negative"}
        if intent.get("sql"): tags.add("sql")
        
        lines.append("@" + " @".join(sorted(tags)))
        lines.append(f"Feature: {template.card_network.title()} {template.category.title()} - {'Approved' if intent['result'] == 'approved' else intent['decline'].message if intent['decline'] else 'Declined'}")
        lines.append("")
        lines.append(f"  # Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"  # Template: {template.name}")
        lines.append("")
        
        # Background
        lines.append("  Background:")
        lines.append("    * url cosmosUrl")
        lines.append(f"    * def templateName = '{template.name}'")
        lines.append("    * def generateSTAN = function(){ return Math.floor(Math.random()*999999).toString().padStart(6,'0') }")
        lines.append("    * def generateRRN = function(){ return Math.floor(Math.random()*999999999999).toString().padStart(12,'0') }")
        
        if intent.get("sql"):
            for tbl in self.kb.sql_tables.values():
                keys = " AND ".join([f"{k}='\" + {k.lower()} + \"'" for k in tbl.key_columns])
                lines.append(f"    * def query{tbl.name.replace('_','')} = function({','.join(k.lower() for k in tbl.key_columns)}){{ return DbUtils.query(\"SELECT * FROM {tbl.name} WHERE {keys}\") }}")
        lines.append("")
        
        # Scenario
        exp_rc = "00" if intent["result"] == "approved" else (intent["decline"].code if intent["decline"] else "05")
        exp_status = "COMPLETED" if exp_rc == "00" else "DECLINED"
        
        overrides = {}
        if intent["decline"] and intent["decline"].trigger_field:
            overrides[intent["decline"].trigger_field] = intent["decline"].trigger_value
        if intent.get("amount"):
            overrides["DE4"] = intent["amount"]
        
        lines.append(f"  @{intent['type']} @{'smoke' if exp_rc == '00' else 'negative'}")
        lines.append(f"  Scenario: {template.category.title()} - {'Approved' if exp_rc == '00' else intent['decline'].message if intent['decline'] else 'Declined'}")
        lines.append("    * def stan = generateSTAN()")
        lines.append("    * def rrn = generateRRN()")
        
        ovr_parts = ["DE11: '#(stan)'", "DE37: '#(rrn)'"] + [f"{k}: '{v}'" for k, v in overrides.items()]
        lines.append(f"    * def overrides = {{ {', '.join(ovr_parts)} }}")
        lines.append("")
        
        if intent.get("common"):
            lines.append("    * def result = call read('common_scenarios.feature@common_send_0100') { templateName: '#(templateName)', overrides: '#(overrides)' }")
            lines.append("    * def response = result.cosmosResponse")
        else:
            lines.append("    Given path '/template'")
            lines.append("    And param id = templateName")
            lines.append("    And request { templateId: '#(templateName)', overrides: '#(overrides)' }")
            lines.append("    When method post")
            lines.append("    Then status 200")
        
        lines.append("")
        lines.append(f"    * match response.DE39 == '{exp_rc}'")
        if exp_rc == "00":
            lines.append("    * match response.DE38 == '#notnull'")
        
        if intent.get("sql"):
            lines.append("")
            lines.append("    # SQL Validation")
            lines.append("    * def pph = queryPPHTRAN(rrn, stan)")
            lines.append(f"    * match pph.TXN_STATUS == '{exp_status}'")
            lines.append("    * def ppdsva = queryPPDSVA(rrn, stan)")
            lines.append("    * match ppdsva.FRAUD_CHECK == 'PASS'")
        
        return '\n'.join(lines)

# ============================================================================
# STREAMLIT UI - BEAUTIFUL MODERN DESIGN
# ============================================================================

st.set_page_config(page_title="AI Karate Generator", page_icon="🥋", layout="wide", initial_sidebar_state="collapsed")

# Beautiful Modern CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --primary: #7C3AED;
    --primary-light: #A78BFA;
    --primary-dark: #5B21B6;
    --secondary: #06B6D4;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
    --bg: #F8FAFC;
    --card: #FFFFFF;
    --text: #1E293B;
    --text-light: #64748B;
    --border: #E2E8F0;
}

* { font-family: 'Plus Jakarta Sans', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #F0F4FF 0%, #FAFBFF 50%, #F5F0FF 100%);
}

/* Hide defaults */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Main Header */
.main-header {
    background: linear-gradient(135deg, var(--primary) 0%, #9333EA 50%, var(--secondary) 100%);
    border-radius: 24px;
    padding: 3rem;
    margin: -1rem -1rem 2rem -1rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 40px -12px rgba(124, 58, 237, 0.35);
}

.main-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
    border-radius: 50%;
}

.main-header::after {
    content: '';
    position: absolute;
    bottom: -30%;
    left: -10%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    border-radius: 50%;
}

.main-header h1 {
    font-size: 3rem;
    font-weight: 800;
    color: white;
    margin: 0;
    position: relative;
    z-index: 1;
    letter-spacing: -0.02em;
}

.main-header p {
    color: rgba(255,255,255,0.9);
    font-size: 1.2rem;
    margin-top: 0.75rem;
    position: relative;
    z-index: 1;
    font-weight: 400;
}

/* Cards */
.card {
    background: var(--card);
    border-radius: 20px;
    padding: 1.75rem;
    margin: 1rem 0;
    border: 1px solid var(--border);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    transition: all 0.3s ease;
}

.card:hover {
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
    transform: translateY(-2px);
}

.card-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.25rem;
}

.card-icon {
    width: 52px;
    height: 52px;
    background: linear-gradient(135deg, var(--primary-light), var(--primary));
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    box-shadow: 0 8px 16px -4px rgba(124, 58, 237, 0.3);
}

.card-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
}

.card-subtitle {
    font-size: 0.875rem;
    color: var(--text-light);
    margin: 0;
}

/* Section Headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 2rem 0 1.25rem;
}

.section-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--primary-light), var(--primary));
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
}

.section-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text);
    margin: 0;
}

/* Prompt Box */
.prompt-container {
    background: linear-gradient(135deg, #FAFAFF 0%, #F5F3FF 100%);
    border: 2px solid var(--primary-light);
    border-radius: 20px;
    padding: 2rem;
    margin: 1.5rem 0;
}

.prompt-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.75rem;
}

/* Example Pills */
.example-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin: 1rem 0;
}

.example-pill {
    background: white;
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 0.625rem 1.25rem;
    font-size: 0.875rem;
    color: var(--text);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.example-pill:hover {
    border-color: var(--primary);
    background: var(--primary);
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 8px 16px -4px rgba(124, 58, 237, 0.3);
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}

.stat-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    border: 1px solid var(--border);
    transition: all 0.3s ease;
}

.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.1);
}

.stat-value {
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
}

.stat-label {
    font-size: 0.8rem;
    color: var(--text-light);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.5rem;
    font-weight: 600;
}

/* Template Cards */
.template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}

.template-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.25rem;
    transition: all 0.3s ease;
    cursor: pointer;
}

.template-card:hover {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}

.template-icon {
    font-size: 2rem;
    margin-bottom: 0.75rem;
}

.template-name {
    font-weight: 700;
    color: var(--text);
    font-size: 1rem;
    margin-bottom: 0.25rem;
}

.template-desc {
    font-size: 0.8rem;
    color: var(--text-light);
    margin-bottom: 0.75rem;
}

.template-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
}

.template-tag {
    background: #F1F5F9;
    color: var(--text-light);
    padding: 0.25rem 0.625rem;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 500;
}

/* Response Code Pills */
.rc-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1rem 0;
}

.rc-pill {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: white;
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
}

.rc-pill.approved { border-left: 4px solid var(--success); }
.rc-pill.declined { border-left: 4px solid var(--danger); }
.rc-pill.error { border-left: 4px solid var(--warning); }

.rc-code {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    color: var(--text);
}

.rc-msg {
    color: var(--text-light);
}

/* Code Output */
.code-container {
    background: #1E1E2E;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
    position: relative;
    overflow: hidden;
}

.code-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

.code-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.code-dot.red { background: #FF5F57; }
.code-dot.yellow { background: #FEBC2E; }
.code-dot.green { background: #28C840; }

.code-title {
    color: rgba(255,255,255,0.6);
    font-size: 0.8rem;
    margin-left: 0.5rem;
}

/* Form Styling */
.form-section {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
    border: 1px solid var(--border);
}

.form-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.5rem;
    display: block;
}

.form-hint {
    font-size: 0.75rem;
    color: var(--text-light);
    margin-top: 0.25rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 16px;
    padding: 6px;
    gap: 4px;
    border: 1px solid var(--border);
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-light);
    background: transparent;
    border-radius: 12px;
    padding: 0.75rem 1.5rem;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--primary);
    background: rgba(124, 58, 237, 0.05);
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
    color: white !important;
    box-shadow: 0 4px 12px -2px rgba(124, 58, 237, 0.4);
}

/* Buttons */
.stButton > button {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 700;
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
    border: none;
    border-radius: 14px;
    padding: 0.875rem 2rem;
    font-size: 1rem;
    transition: all 0.3s ease;
    box-shadow: 0 8px 16px -4px rgba(124, 58, 237, 0.35);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 24px -4px rgba(124, 58, 237, 0.45);
}

/* Inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    font-family: 'Plus Jakarta Sans', sans-serif;
    border: 2px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
    transition: all 0.2s ease !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.1) !important;
}

/* Expanders */
.streamlit-expanderHeader {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 600;
    background: white;
    border: 1px solid var(--border);
    border-radius: 12px;
}

/* Success/Error */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: 12px;
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* Checkboxes */
.stCheckbox label {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 500;
}

/* Download button */
.stDownloadButton > button {
    background: linear-gradient(135deg, var(--success), #059669) !important;
    box-shadow: 0 8px 16px -4px rgba(16, 185, 129, 0.35) !important;
}

.stDownloadButton > button:hover {
    box-shadow: 0 12px 24px -4px rgba(16, 185, 129, 0.45) !important;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-in {
    animation: fadeIn 0.5s ease forwards;
}
</style>
""", unsafe_allow_html=True)

def main():
    # Session State
    if 'kb' not in st.session_state:
        st.session_state.kb = KnowledgeBase()
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = FeatureAnalyzer(st.session_state.kb)
    if 'generator' not in st.session_state:
        st.session_state.generator = TestGenerator(st.session_state.kb)
    if 'selected_prompt' not in st.session_state:
        st.session_state.selected_prompt = ""
    
    kb = st.session_state.kb
    analyzer = st.session_state.analyzer
    generator = st.session_state.generator
    
    # Header
    st.markdown('''
    <div class="main-header">
        <h1>🥋 AI Karate Generator</h1>
        <p>Train on your tests • Add custom templates • Generate with natural language</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Stats
    st.markdown(f'''
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{len(kb.templates)}</div>
            <div class="stat-label">Templates</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(kb.response_codes)}</div>
            <div class="stat-label">Response Codes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(kb.sql_tables)}</div>
            <div class="stat-label">SQL Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(analyzer.files)}</div>
            <div class="stat-label">Files Learned</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["✨ Generate", "📚 Train", "➕ Add", "📋 View All"])
    
    # ==================== TAB 1: GENERATE ====================
    with tab1:
        st.markdown('''
        <div class="section-header">
            <div class="section-icon">✨</div>
            <h2 class="section-title">Generate from Natural Language</h2>
        </div>
        ''', unsafe_allow_html=True)
        
        # Example prompts
        examples = [
            ("🎯", "E2E approved Visa purchase with SQL"),
            ("❌", "Declined due to insufficient funds"),
            ("🏧", "ATM withdrawal for $500"),
            ("↩️", "Visa refund transaction"),
            ("📊", "Data-driven regression tests"),
            ("💳", "MasterCard purchase test"),
        ]
        
        st.markdown('<div class="prompt-label">Quick Examples</div>', unsafe_allow_html=True)
        
        cols = st.columns(3)
        for i, (icon, text) in enumerate(examples):
            with cols[i % 3]:
                if st.button(f"{icon} {text}", key=f"ex_{i}", use_container_width=True):
                    st.session_state.selected_prompt = text
        
        st.markdown("---")
        
        # Prompt Input
        prompt = st.text_area(
            "Describe the test you want to generate",
            value=st.session_state.selected_prompt,
            height=120,
            placeholder="Example: Write an E2E test for declined Visa purchase due to expired card with SQL validation for PPH_TRAN and PPDSVA tables"
        )
        
        # Options
        col1, col2, col3 = st.columns(3)
        with col1:
            include_sql = st.checkbox("✅ Include SQL Validation", value=True)
        with col2:
            use_common = st.checkbox("🔗 Use Common Scenarios", value=True)
        with col3:
            add_docs = st.checkbox("📝 Add Documentation", value=True)
        
        st.markdown("")
        
        if st.button("🚀 Generate Karate Test", type="primary", use_container_width=True):
            if prompt.strip():
                with st.spinner("✨ Generating your test..."):
                    feature = generator.generate(prompt, {"sql": include_sql, "common": use_common})
                
                st.success("🎉 Test generated successfully!")
                
                st.markdown('''
                <div class="code-container">
                    <div class="code-header">
                        <span class="code-dot red"></span>
                        <span class="code-dot yellow"></span>
                        <span class="code-dot green"></span>
                        <span class="code-title">generated_test.feature</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                st.code(feature, language="gherkin")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📥 Download .feature", feature, "generated_test.feature", use_container_width=True)
                with col2:
                    if st.button("📋 Copy to Clipboard", use_container_width=True):
                        st.toast("Copied to clipboard!")
            else:
                st.warning("Please enter a prompt to generate a test")
    
    # ==================== TAB 2: TRAIN ====================
    with tab2:
        st.markdown('''
        <div class="section-header">
            <div class="section-icon">📚</div>
            <h2 class="section-title">Train on Your Feature Files</h2>
        </div>
        ''', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 📁 Upload Files")
            uploaded = st.file_uploader("Drop your .feature files here", type=["feature", "txt"], accept_multiple_files=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 📝 Or Paste Content")
            pasted = st.text_area("Paste Karate feature content", height=200, placeholder="Feature: Your Test\n  Scenario: ...")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("🧠 Train AI", type="primary", use_container_width=True):
                count = 0
                if uploaded:
                    for f in uploaded:
                        analyzer.analyze(f.read().decode('utf-8'), f.name)
                        count += 1
                if pasted.strip():
                    analyzer.analyze(pasted, "pasted")
                    count += 1
                
                if count > 0:
                    st.success(f"✅ Learned from {count} file(s)!")
                    st.balloons()
                else:
                    st.warning("Please upload or paste content")
        
        with col2:
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 📊 Learned Patterns")
            
            if analyzer.files:
                for f in analyzer.files:
                    st.markdown(f"✅ **{f['name']}** - {f['steps']} steps, {f['scenarios']} scenarios")
                
                if analyzer.patterns:
                    st.markdown("---")
                    st.markdown("**Top Step Patterns:**")
                    for step, count in sorted(analyzer.patterns.items(), key=lambda x: -x[1])[:5]:
                        st.code(f"({count}x) {step[:60]}...")
            else:
                st.info("👆 Upload feature files to start learning patterns")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== TAB 3: ADD ====================
    with tab3:
        st.markdown('''
        <div class="section-header">
            <div class="section-icon">➕</div>
            <h2 class="section-title">Add Custom Templates & Codes</h2>
        </div>
        ''', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 💳 Add Transaction Template")
            
            with st.form("add_template"):
                t_id = st.text_input("Template ID", placeholder="visa_ecom_purchase_0100")
                t_name = st.text_input("Name", placeholder="fwd_visa_ecom_purchase_0100")
                t_desc = st.text_input("Description", placeholder="Visa E-Commerce Purchase")
                
                c1, c2 = st.columns(2)
                with c1:
                    t_cat = st.selectbox("Category", ["purchase", "withdrawal", "refund", "reversal", "balance", "cashback"])
                    t_mti = st.selectbox("MTI", ["0100", "0110", "0200", "0400"])
                with c2:
                    t_net = st.selectbox("Network", ["visa", "mastercard", "amex", "discover"])
                    t_proc = st.text_input("Proc Code", "000000")
                
                t_tags = st.text_input("Tags", "visa, purchase")
                t_fields = st.text_area("Fields (JSON)", '{"DMTI": "0100", "DE2": "4111111111111111"}')
                
                if st.form_submit_button("➕ Add Template", use_container_width=True):
                    if t_id and t_name:
                        try:
                            kb.add_template(TransactionTemplate(
                                t_id, t_name, t_desc, t_cat, t_net, t_mti, t_proc,
                                json.loads(t_fields), [t.strip() for t in t_tags.split(",")]
                            ))
                            st.success(f"✅ Added: {t_name}")
                        except: st.error("Invalid JSON")
                    else: st.warning("Fill required fields")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 🔢 Add Response Code")
            
            with st.form("add_rc"):
                rc_code = st.text_input("Code", placeholder="55")
                rc_msg = st.text_input("Message", placeholder="Invalid PIN")
                rc_cat = st.selectbox("Category", ["approved", "declined", "error"])
                rc_field = st.text_input("Trigger Field", placeholder="DE52")
                rc_val = st.text_input("Trigger Value", placeholder="")
                
                if st.form_submit_button("➕ Add Code", use_container_width=True):
                    if rc_code and rc_msg:
                        kb.add_response_code(ResponseCode(rc_code, rc_msg, rc_cat, rc_field, rc_val))
                        st.success(f"✅ Added: {rc_code}")
                    else: st.warning("Fill required fields")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown("#### 🗄️ Add SQL Table")
            
            with st.form("add_tbl"):
                tbl_name = st.text_input("Table Name", placeholder="CUSTOM_TABLE")
                tbl_desc = st.text_input("Description", placeholder="Custom table")
                tbl_keys = st.text_input("Key Columns", "RRN, STAN")
                
                if st.form_submit_button("➕ Add Table", use_container_width=True):
                    if tbl_name:
                        kb.add_sql_table(SQLTable(tbl_name, tbl_desc, {}, [k.strip() for k in tbl_keys.split(",")]))
                        st.success(f"✅ Added: {tbl_name}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== TAB 4: VIEW ALL ====================
    with tab4:
        st.markdown('''
        <div class="section-header">
            <div class="section-icon">📋</div>
            <h2 class="section-title">Knowledge Base</h2>
        </div>
        ''', unsafe_allow_html=True)
        
        # Templates
        st.markdown("#### 💳 Transaction Templates")
        
        template_html = '<div class="template-grid">'
        for t in kb.templates.values():
            tags_html = ''.join([f'<span class="template-tag">{tag}</span>' for tag in t.tags[:3]])
            template_html += f'''
            <div class="template-card">
                <div class="template-icon">{t.icon}</div>
                <div class="template-name">{t.description}</div>
                <div class="template-desc">{t.name}</div>
                <div class="template-tags">{tags_html}</div>
            </div>
            '''
        template_html += '</div>'
        st.markdown(template_html, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Response Codes
        st.markdown("#### 🔢 Response Codes")
        
        rc_html = '<div class="rc-grid">'
        for rc in kb.response_codes.values():
            rc_html += f'''
            <div class="rc-pill {rc.category}">
                <span class="rc-code">{rc.code}</span>
                <span class="rc-msg">{rc.message}</span>
            </div>
            '''
        rc_html += '</div>'
        st.markdown(rc_html, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # SQL Tables
        st.markdown("#### 🗄️ SQL Tables")
        cols = st.columns(len(kb.sql_tables))
        for i, (name, tbl) in enumerate(kb.sql_tables.items()):
            with cols[i]:
                st.markdown(f'''
                <div class="card">
                    <div class="card-title">{name}</div>
                    <div class="card-subtitle">{tbl.description}</div>
                    <div style="margin-top: 0.75rem; font-size: 0.8rem; color: #64748B;">
                        Keys: {', '.join(tbl.key_columns)}
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Export/Import
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Export Knowledge Base", use_container_width=True):
                st.download_button("⬇️ Download JSON", kb.export_json(), "knowledge_base.json", use_container_width=True)
        with col2:
            uploaded_kb = st.file_uploader("📥 Import Knowledge Base", type=["json"])
            if uploaded_kb:
                if st.button("Import", use_container_width=True):
                    kb.import_json(uploaded_kb.read().decode('utf-8'))
                    st.success("✅ Imported!")
                    st.rerun()

if __name__ == "__main__":
    main()
