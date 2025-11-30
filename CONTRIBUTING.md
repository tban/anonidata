# Guía de Contribución

¡Gracias por tu interés en contribuir a AnoniData!

## Código de Conducta

- Sé respetuoso y profesional
- Acepta críticas constructivas
- Enfócate en lo que es mejor para la comunidad

## Cómo Contribuir

### Reportar Bugs

Crea un issue en GitHub con:
- Descripción clara del problema
- Pasos para reproducir
- Comportamiento esperado vs actual
- Screenshots si aplica
- Versión de AnoniData
- Sistema operativo

### Proponer Features

Crea un issue con:
- Descripción de la funcionalidad
- Caso de uso
- Beneficio esperado
- Implementación sugerida (opcional)

### Pull Requests

1. Fork el repositorio
2. Crea una rama desde `main`:
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```
3. Realiza tus cambios
4. Asegúrate de:
   - Escribir tests
   - Actualizar documentación
   - Seguir el estilo de código
5. Commit con mensajes descriptivos:
   ```bash
   git commit -m "feat: agregar detección de pasaportes"
   ```
6. Push y crea Pull Request

## Estilo de Código

### TypeScript/JavaScript

```bash
npm run lint
npm run format
```

Seguimos:
- ESLint + Prettier
- TypeScript strict mode
- Functional programming cuando sea posible

### Python

```bash
cd backend
black .
flake8 .
mypy .
```

Seguimos:
- PEP 8
- Type hints
- Docstrings para funciones públicas

## Estructura de Commits

Usamos Conventional Commits:

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Cambios en documentación
- `style:` Formato, no afecta código
- `refactor:` Refactorización
- `test:` Agregar o corregir tests
- `chore:` Mantenimiento

Ejemplo:
```
feat(detector): agregar detección de pasaportes españoles

- Implementar regex para pasaportes
- Agregar validación de número de control
- Tests unitarios incluidos

Closes #123
```

## Testing

### Frontend
```bash
npm test
```

### Backend
```bash
cd backend
source venv/bin/activate
pytest
```

**Cobertura mínima:** 70%

## Desarrollo Local

Ver [docs/INSTALLATION.md](docs/INSTALLATION.md) para setup completo.

### Quick Start
```bash
npm install
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ..
npm run dev
```

## Áreas que Necesitan Ayuda

- 🧪 Tests (especialmente E2E)
- 📖 Documentación y traducciones
- 🎨 UI/UX improvements
- 🤖 Modelos ML para detección de firmas
- 🌍 Soporte para más idiomas/países
- ♿ Accesibilidad

## Licencia

Al contribuir, aceptas que tus contribuciones se licenciarán bajo MIT License.

## Contacto

- Issues: GitHub Issues
- Email: maintainers@anonidata.com (ejemplo)
- Discord: (próximamente)

¡Gracias por contribuir!
