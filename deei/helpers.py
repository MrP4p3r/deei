import re


__all__ = [
    'camelcase_into_snakecase',
    'snakecase_into_camelcase',
]


_camel_case_word_bound_pattern = re.compile(r'([^A-Z])([A-Z])')


def camelcase_into_snakecase(s: str) -> str:
    return _camel_case_word_bound_pattern.sub(r'\1_\2', s).lower()


def snakecase_into_camelcase(s: str) -> str:
    return s[0] + s.replace('_', ' ').title().replace(' ', '')[1:]
