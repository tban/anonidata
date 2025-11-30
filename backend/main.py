#!/usr/bin/env python3
"""
AnoniData Backend - Main Entry Point
Maneja la comunicación con Electron via stdin/stdout
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any
from loguru import logger

from core.processor import PDFProcessor
from core.config import Settings
from utils.logging_config import setup_logging


def setup_environment():
    """Configurar entorno de ejecución"""
    # Configurar logging
    setup_logging()

    # Verificar dependencias
    try:
        import fitz  # PyMuPDF
        import cv2
        import spacy
        logger.info("Dependencias verificadas correctamente")
    except ImportError as e:
        logger.error(f"Error importando dependencias: {e}")
        sys.exit(1)


def process_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa una solicitud de Electron

    Args:
        request: Diccionario con la solicitud

    Returns:
        Diccionario con el resultado
    """
    action = request.get("action")

    if action == "anonymize":
        files = request.get("files", [])
        settings_dict = request.get("settings", {})

        # Crear configuración
        settings = Settings(**settings_dict)

        # Crear procesador
        processor = PDFProcessor(settings)

        # Procesar archivos
        results = []
        for file_path in files:
            try:
                result = processor.process_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error procesando {file_path}: {e}")
                results.append({
                    "inputFile": file_path,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "success": True,
            "results": results,
        }

    elif action == "health":
        return {
            "success": True,
            "status": "healthy",
            "version": "1.0.0",
        }

    else:
        return {
            "success": False,
            "error": f"Acción desconocida: {action}",
        }


def main():
    """Main loop - lee de stdin y escribe a stdout"""
    setup_environment()

    logger.info("Backend Python iniciado")
    logger.info("Esperando solicitudes...")

    try:
        for line in sys.stdin:
            try:
                # Parsear solicitud
                request = json.loads(line.strip())
                logger.debug(f"Solicitud recibida: {request.get('action')}")

                # Procesar
                response = process_request(request)

                # Enviar respuesta
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON: {e}")
                error_response = {
                    "success": False,
                    "error": f"JSON inválido: {str(e)}",
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

            except Exception as e:
                logger.error(f"Error procesando solicitud: {e}", exc_info=True)
                error_response = {
                    "success": False,
                    "error": str(e),
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("Backend detenido por usuario")
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
