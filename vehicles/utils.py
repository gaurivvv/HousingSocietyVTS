import re

# Common Indian formats after normalization, e.g.
#   MH12AB1234, MH12A1234, DL3CAB1234, MH121234
STANDARD_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$")

# Bharat (BH) series, e.g. 22BH1234AA
BH_PLATE_PATTERN = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")


def normalize_plate(value):
    """
    Convert a plate number to one consistent format:
    uppercase, with spaces, hyphens and other symbols removed.

    Example: "mh 12-ab 1234" -> "MH12AB1234"
    """
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def is_valid_indian_plate(value):
    """
    Check an already-normalized plate against common Indian formats.
    This checks the format only; it does not prove the vehicle exists.
    """
    return bool(STANDARD_PLATE_PATTERN.match(value) or BH_PLATE_PATTERN.match(value))