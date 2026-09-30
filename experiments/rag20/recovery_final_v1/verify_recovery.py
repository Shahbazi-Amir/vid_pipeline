"""Read-only validation of CURRENT and active response revisions.
Use incremental_review.py --restore to recover root mirrors after interruption.
"""
import json
from incremental_review import verify_current,validate,source_rows
if __name__=='__main__':
    current,state=verify_current()
    print(json.dumps(validate(state,*source_rows()),ensure_ascii=False,indent=2))
