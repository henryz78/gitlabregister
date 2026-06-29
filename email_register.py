import sys as _sys
from gitlab_register import email_providers as _email_providers

_sys.modules[__name__] = _email_providers
globals().update(_email_providers.__dict__)
