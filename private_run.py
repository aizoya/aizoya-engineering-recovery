"""Local, non-persistent secret entry. Never prints the URI or provider errors."""
import getpass
import os
import runpy
import sys

def main():
    if not sys.stdin.isatty():
        raise ValueError('interactive_terminal_required')
    if not os.environ.get('MONGODB_URI'):
        os.environ['MONGODB_URI']=getpass.getpass('Assigned organizer sandbox URI (hidden): ')
    if not os.environ.get('MONGODB_DATABASE'):
        os.environ['MONGODB_DATABASE']=input('Assigned database name: ').strip()
    if os.environ.get('SANDBOX_CONFIRMED')!='YES':
        if input('Organizer confirmed this host and $0 coverage? Type YES: ').strip()!='YES':
            raise ValueError('sandbox_not_confirmed')
        os.environ['SANDBOX_CONFIRMED']='YES'
    runpy.run_path(os.path.join(os.path.dirname(__file__),'harness.py'),run_name='__main__')

if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('Private setup stopped: '+type(error).__name__,file=sys.stderr)
        sys.exit(1)
