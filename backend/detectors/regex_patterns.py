"""
Patrones regex para detectar datos personales españoles
"""

import re
from typing import List


class RegexPatterns:
    """Patrones regex para PII español"""

    # DNI español: 8 dígitos + letra (con soporte para puntos y guión)
    # Formatos: 12345678A, 12345678-A, 12.345.678A, 12.345.678-A
    DNI_PATTERN = r'\b(?:\d{8}|\d{1,2}\.\d{3}\.\d{3})-?[A-Z]\b'

    # NIE español: X/Y/Z + 7 dígitos + letra (con soporte para puntos y guión)
    # Formatos: X1234567A, X1234567-A, X1.234.567A, X1.234.567-A
    NIE_PATTERN = r'\b[XYZ](?:\d{7}|\d{1}\.\d{3}\.\d{3})-?[A-Z]\b'

    # Email
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Teléfono español (varios formatos)
    PHONE_PATTERNS = [
        r'\b\+34\s?[6-9][0-9]{8}\b',  # +34 666123456
        r'\b[6-9][0-9]{2}\s?[0-9]{2}\s?[0-9]{2}\s?[0-9]{2}\b',  # 666 12 34 56
        r'\b[6-9][0-9]{8}\b',  # 666123456
    ]

    # IBAN español
    IBAN_PATTERN = r'\bES[0-9]{2}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b'

    # Número de la Seguridad Social
    NSS_PATTERN = r'\b[0-9]{2}\s?[0-9]{10}\b'

    def __init__(self):
        self.dni_regex = re.compile(self.DNI_PATTERN)
        self.nie_regex = re.compile(self.NIE_PATTERN)
        self.email_regex = re.compile(self.EMAIL_PATTERN)
        self.phone_regexes = [re.compile(p) for p in self.PHONE_PATTERNS]
        self.iban_regex = re.compile(self.IBAN_PATTERN)
        self.nss_regex = re.compile(self.NSS_PATTERN)

    def find_dni(self, text: str) -> List[str]:
        """Encuentra DNIs en el texto"""
        matches = self.dni_regex.findall(text)
        # Validar letra del DNI
        return [m for m in matches if self._validate_dni(m)]

    def find_nie(self, text: str) -> List[str]:
        """Encuentra NIEs en el texto"""
        matches = self.nie_regex.findall(text)
        return [m for m in matches if self._validate_nie(m)]

    def find_email(self, text: str) -> List[str]:
        """Encuentra emails en el texto"""
        return self.email_regex.findall(text)

    def find_phone(self, text: str) -> List[str]:
        """Encuentra teléfonos en el texto"""
        matches = []
        for regex in self.phone_regexes:
            matches.extend(regex.findall(text))
        return matches

    def find_iban(self, text: str) -> List[str]:
        """Encuentra IBANs en el texto"""
        return self.iban_regex.findall(text)

    def find_nss(self, text: str) -> List[str]:
        """Encuentra números de Seguridad Social"""
        return self.nss_regex.findall(text)

    @staticmethod
    def _validate_dni(dni: str) -> bool:
        """Valida el dígito de control del DNI"""
        # Normalizar: eliminar puntos y guiones
        normalized = dni.replace('.', '').replace('-', '')

        if len(normalized) != 9:
            return False

        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        try:
            number = int(normalized[:8])
            letter = normalized[8].upper()
            expected_letter = letters[number % 23]
            return letter == expected_letter
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _validate_nie(nie: str) -> bool:
        """Valida el dígito de control del NIE"""
        # Normalizar: eliminar puntos y guiones
        normalized = nie.replace('.', '').replace('-', '')

        if len(normalized) != 9:
            return False

        letters = "TRWAGMYFPDXBNJZSQVHLCKE"
        first_char = normalized[0].upper()

        # Convertir primera letra a número
        replacements = {'X': '0', 'Y': '1', 'Z': '2'}
        if first_char not in replacements:
            return False

        try:
            number_str = replacements[first_char] + normalized[1:8]
            number = int(number_str)
            letter = normalized[8].upper()
            expected_letter = letters[number % 23]
            return letter == expected_letter
        except (ValueError, IndexError):
            return False
