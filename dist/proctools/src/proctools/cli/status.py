from typing import NamedTuple


class ExitCode(NamedTuple):
    code: int
    name: str

    def __str__(self):
        return f"{self.code} ({self.name})"


class ExitCodes:
    SUCCESS = ExitCode(0, "success")
    INTERNAL_ERROR = ExitCode(1, "internal error")
    CLI_ERROR = ExitCode(2, "commandline error")

    def __init_subclass__(cls):
        common_codes = {
            n: c for n, c in vars(ExitCodes).items() if not n.startswith("_")
        }
        for name, code in common_codes.items():
            sub_code = getattr(cls, name, None)
            if sub_code != code:
                raise ValueError(
                    f"{cls.__name__}.{name}: common exit codes should not be"
                    " overwritten by subclasses"
                )

    def __new__(cls, *args, **kwargs):
        raise RuntimeError(f"{cls} should not be instantiated")
