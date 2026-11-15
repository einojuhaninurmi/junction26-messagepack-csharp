"""Run from zsh: python3 trust-demo/start_claude.py. No credential in shell history."""
import argparse
import getpass
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=2283)
    args=parser.parse_args()
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        parser.error('An interactive terminal is required for hidden key entry; no echo fallback is allowed.')
    try:
        with socket.socket() as probe:probe.bind(('127.0.0.1',args.port))
    except OSError:parser.error(f'Port {args.port} is occupied. Stop the existing demo first (Ctrl-C in its terminal). No key has been requested.')
    print('Direct Anthropic only. Model claude-sonnet-5-5; 8,192 output tokens; 300s deadline; no retries.')
    print('The UI counts tokens and shows cost before one paid generation. No model call is made at startup.')
    key=getpass.getpass('Anthropic API key (hidden): ').strip()
    if not key or any(c.isspace() for c in key):parser.error('A nonempty key without whitespace is required.')
    child_env=dict(os.environ)
    child_env.update(TRUST_REVIEW_PROVIDER='anthropic',TRUST_REVIEW_MODEL='claude-sonnet-5-5',TRUST_REVIEW_TIMEOUT_SECONDS='300',TRUST_REVIEW_API_KEY=key)
    # exec replaces this launcher; the shell environment is never mutated and
    # neither arguments nor any file contain the key. Only the server gets it.
    os.execve(sys.executable,[sys.executable,str(ROOT/'server.py'),'--port',str(args.port)],child_env)

if __name__=='__main__':main()
