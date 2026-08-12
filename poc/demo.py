from src.schemas import AccessVerifyResponse


def run_happy_path() -> AccessVerifyResponse:
    raise NotImplementedError("Block 3")


def run_risky_path() -> AccessVerifyResponse:
    raise NotImplementedError("Block 3")


if __name__ == "__main__":
    print(run_happy_path())
    print(run_risky_path())
