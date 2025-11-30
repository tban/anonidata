"""
Tests unitarios para FileManager
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import pytest
from core.config import Settings
from utils.file_manager import FileManager


class TestFileManager:
    """Tests para FileManager"""

    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def file_manager(self, settings):
        return FileManager(settings)

    def test_generate_output_path(self, file_manager):
        """Test generación de ruta de salida"""
        input_path = Path("/tmp/documento.pdf")
        output_path = file_manager.generate_output_path(input_path)

        assert output_path.parent == input_path.parent
        assert output_path.stem == "documento_anonimizado"
        assert output_path.suffix == ".pdf"

    def test_validate_pdf_invalid_extension(self, file_manager, tmp_path):
        """Test validación de extensión incorrecta"""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        with pytest.raises(ValueError, match="no es un PDF"):
            file_manager.validate_pdf(file_path)

    def test_validate_pdf_not_exists(self, file_manager):
        """Test validación de archivo inexistente"""
        file_path = Path("/tmp/nonexistent.pdf")

        with pytest.raises(ValueError, match="no encontrado"):
            file_manager.validate_pdf(file_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
