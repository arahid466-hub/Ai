"""Central registry; adapters must return real runtime state."""
TOOLS={}
def register(name, handler, status=None): TOOLS[name]={'handler':handler,'status':status or (lambda:{'available':True})}
def snapshot():
    out={}
    for name,item in TOOLS.items():
        try: out[name]=item['status']()
        except Exception as e: out[name]={'available':False,'error':str(e)}
    return out
