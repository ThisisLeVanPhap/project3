"""Product catalog parser registry."""

from . import caco, generic, moho, nhaxinh


PARSERS = {
    "generic": generic.parse_product,
    "caco": caco.parse_product,
    "noithatcaco": caco.parse_product,
    "moho": moho.parse_product,
    "nhaxinh": nhaxinh.parse_product,
    "nha-xinh": nhaxinh.parse_product,
}


def get_parser(store):
    """Return a parser function for a store, falling back to generic."""
    key = (store or "generic").strip().lower()
    return PARSERS.get(key, generic.parse_product)
