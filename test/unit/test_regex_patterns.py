"""
Tests unitarios para patrones regex
"""

import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import pytest
from detectors.regex_patterns import RegexPatterns


class TestRegexPatterns:
    """Tests para RegexPatterns"""

    @pytest.fixture
    def patterns(self):
        return RegexPatterns()

    def test_find_dni_valid(self, patterns):
        """Test detección de DNI válido"""
        text = "Mi DNI es 12345678Z y vivo en Madrid"
        result = patterns.find_dni(text)
        assert len(result) == 1
        assert result[0] == "12345678Z"

    def test_find_dni_invalid_letter(self, patterns):
        """Test DNI con letra incorrecta"""
        text = "DNI inválido: 12345678A"
        result = patterns.find_dni(text)
        # No debe encontrar porque la letra no es correcta
        assert len(result) == 0

    def test_find_nie_valid(self, patterns):
        """Test detección de NIE válido"""
        text = "Mi NIE es X1234567L"
        result = patterns.find_nie(text)
        assert len(result) == 1

    def test_find_email(self, patterns):
        """Test detección de email"""
        text = "Contacto: usuario@ejemplo.com y admin@test.es"
        result = patterns.find_email(text)
        assert len(result) == 2
        assert "usuario@ejemplo.com" in result

    def test_find_phone(self, patterns):
        """Test detección de teléfonos"""
        text = "Llámame al +34 666123456 o al 912345678"
        result = patterns.find_phone(text)
        assert len(result) >= 1

    def test_find_iban(self, patterns):
        """Test detección de IBAN"""
        text = "Mi cuenta es ES12 1234 1234 1234 1234 1234"
        result = patterns.find_iban(text)
        assert len(result) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
