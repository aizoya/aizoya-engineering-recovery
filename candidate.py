"""First honest Codex implementation of the fictional importer contract."""
import json
import re
from decimal import Decimal

def import_transactions(text):
    records=[]
    errors=[]
    seen=set()
    duplicates=0
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip():
            continue
        try:
            row=json.loads(line)
            if not isinstance(row,dict):
                raise ValueError('object required')
            ident=row.get('id')
            amount=row.get('amount')
            if not isinstance(ident,str) or not isinstance(amount,str):
                raise ValueError('strings required')
            ident=ident.strip()
            amount=amount.strip()
            if not ident or len(ident)>80 or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?',amount):
                raise ValueError('invalid fields')
            dollars=Decimal(amount)
            if dollars>Decimal('1000000.00'):
                raise ValueError('amount above limit')
            cents=int(dollars*100)
            if ident in seen:
                duplicates+=1
            else:
                seen.add(ident)
                records.append({'id':ident,'amount_cents':cents})
        except (ValueError,TypeError):
            errors.append(number)
    return {'records':records,'errors':errors,'duplicates':duplicates}
