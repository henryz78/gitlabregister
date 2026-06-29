import sys as _sys
from gitlab_register import flow as _flow

_module_name = __name__
_sys.modules[_module_name] = _flow
globals().update(_flow.__dict__)

if _module_name == "__main__":
    from gitlab_register.cli import main
    raise SystemExit(main())
