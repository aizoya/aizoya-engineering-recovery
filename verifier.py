"""Independent verifier for a single, bounded fictional engineering task."""
import ast
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_CODE = 16000
ALLOWED_IMPORTS = {"json", "decimal", "re"}

def validate_source(code):
    if len(code.encode()) > MAX_CODE:
        raise ValueError("candidate_too_large")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [x.name.split('.')[0] for x in node.names] if isinstance(node, ast.Import) else [node.module]
            if any(x not in ALLOWED_IMPORTS for x in names):
                raise ValueError("import_not_allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError("private_attribute_not_allowed")
        if isinstance(node, ast.Name) and (node.id.startswith('__') or node.id in {"open", "eval", "exec", "compile", "getattr", "setattr", "globals", "locals", "vars", "input", "breakpoint"}):
            raise ValueError("unsafe_name")
    return tree

def cases():
    def row(i, a):
        return json.dumps({"id": i, "amount": a})
    checks = [
        ("empty", "\n", {"records": [], "errors": [], "duplicates": 0}),
        ("exact_cents", row("a", "0.29")+'\n'+row("b", "999999.99"), {"records": [{"id":"a","amount_cents":29},{"id":"b","amount_cents":99999999}],"errors":[],"duplicates":0}),
        ("duplicate_normalization", row(" a ", "1.00")+'\n'+row("a", "9.99"), {"records":[{"id":"a","amount_cents":100}],"errors":[],"duplicates":1}),
        ("invalid_duplicate", row("a", "1")+'\n'+row("a", "oops"), {"records":[{"id":"a","amount_cents":100}],"errors":[2],"duplicates":0}),
        ("malformed_and_blank", '\n{broken\n'+row("b", " 2.50 ")+'\n', {"records":[{"id":"b","amount_cents":250}],"errors":[2],"duplicates":0}),
        ("invalid_amounts", '\n'.join(row(str(i), a) for i,a in enumerate(["1e2","NaN","Infinity","-1","+1","1.001",True,1.25,"1000000.01",".5","1."])), {"records":[],"errors":list(range(1,12)),"duplicates":0}),
        ("invalid_records", '{}\n[]\nnull\n'+row("", "1")+'\n'+row("x"*81,"1"), {"records":[],"errors":[1,2,3,4,5],"duplicates":0}),
        ("limit", row("top", "1000000.00"), {"records":[{"id":"top","amount_cents":100000000}],"errors":[],"duplicates":0}),
        ("unicode_inside_json_string", json.dumps({"id":"café\u2028order","amount":"1.20"},ensure_ascii=False), {"records":[{"id":"café\u2028order","amount_cents":120}],"errors":[],"duplicates":0}),
    ]
    rng = random.Random(20261011)
    amounts = [rng.randrange(100000001) for _ in range(100)]
    text='\n'.join(row('order-'+str(i), f'{a//100}.{a%100:02d}') for i,a in enumerate(amounts))
    expected={"records":[{"id":'order-'+str(i),"amount_cents":a} for i,a in enumerate(amounts)],"errors":[],"duplicates":0}
    checks.append(("generated_exact_money", text, expected))
    return checks

RUNNER = '''import json, sys
try:
 import resource
 resource.setrlimit(resource.RLIMIT_AS, (134217728,134217728))
 resource.setrlimit(resource.RLIMIT_CPU, (2,2))
 resource.setrlimit(resource.RLIMIT_FSIZE, (1048576,1048576))
except ImportError:
 pass
from candidate import import_transactions
payload=json.load(sys.stdin)
print(json.dumps([import_transactions(text) for text in payload], allow_nan=False))
'''

def verify(code):
    started=time.monotonic()
    digest=hashlib.sha256(code.encode()).hexdigest()
    verifier_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        validate_source(code)
    except (SyntaxError, ValueError):
        return {"candidate_hash":digest,"verifier_hash":verifier_hash,"passed":False,"checks":[],"failure":"candidate_validation_rejected","elapsed_ms":round((time.monotonic()-started)*1000)}
    tests=cases()
    with tempfile.TemporaryDirectory(prefix='aizoya-verify-') as folder:
        Path(folder,'candidate.py').write_text(code)
        Path(folder,'runner.py').write_text(RUNNER)
        # Credentials and inherited environment are never passed to candidate code.
        try:
            result=subprocess.run([sys.executable,'-S','runner.py'],cwd=folder,env={"PATH":os.defpath},input=json.dumps([x[1] for x in tests]),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=4)
            observed=json.loads(result.stdout) if result.returncode==0 and len(result.stdout)<1048576 else None
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            observed=None
    if not isinstance(observed,list) or len(observed)!=len(tests):
        return {"candidate_hash":digest,"verifier_hash":verifier_hash,"passed":False,"checks":[],"failure":"execution_or_output_failed","elapsed_ms":round((time.monotonic()-started)*1000)}
    checks=[{"name":n,"passed":type(actual)==dict and json.dumps(actual,sort_keys=True)==json.dumps(expected,sort_keys=True),"expected":expected,"observed":actual} for (n,_,expected),actual in zip(tests,observed)]
    # Never persist arbitrary output: retain only bounded fixture results.
    if len(json.dumps(checks))>50000:
        checks=[]
    return {"candidate_hash":digest,"verifier_hash":verifier_hash,"passed":bool(checks) and all(x['passed'] for x in checks),"checks":checks,"failure":None,"elapsed_ms":round((time.monotonic()-started)*1000)}
