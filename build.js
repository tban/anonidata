const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ==========================================
// CONFIGURACIÓN GENÉRICA Y DIRECTORIOS
// ==========================================
const PROJECT_ROOT = process.cwd();
// Directorio final donde se guardarán los instaladores listos (puedes inyectar Variables de Entorno en tu CI/CD)
let defaultDestDir = '/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA';
if (process.platform === 'win32') {
    defaultDestDir = path.join(process.env.USERPROFILE || 'C:\\', 'Desktop', 'Anonidata_Release');
}
const FINAL_DEST_DIR = process.env.FINAL_DEST_DIR || defaultDestDir;
// Directorio temporal interno donde electron-builder arroja los .exe
const OUTPUT_DIR = path.join(PROJECT_ROOT, 'release');
// Rutas de archivos a usar
const VERSION_EXTERNAL_FILE = path.join(FINAL_DEST_DIR, 'version.json');
const VERSION_LOCAL_FILE = path.join(PROJECT_ROOT, 'src', 'version_local.json');
const PACKAGE_JSON_PATH = path.join(PROJECT_ROOT, 'package.json');

// ==========================================
// DESCARGAS DE GOOGLE DRIVE (CONFIGURACIÓN)
// ==========================================
const DRIVE_URLS = {
    dmg: 'https://drive.google.com/open?id=12rbNznz9t2wol6HabmirJ6X48BuXMNpa&usp=drive_fs',
    exe: 'https://drive.google.com/open?id=1aE8XuzonmI9Bi50Th7vk9FawOHkthf_4&usp=drive_fs',
    version_json: 'https://drive.google.com/open?id=11wml7BF4ZO17coEiimKNJk_tfIMAvWDq&usp=drive_fs'
};

function runWorkflow() {
    let localVersionCreated = false;

    try {
        console.log('=== Iniciando el Orquestador de Compilación para Producción ===\n');

        if (!fs.existsSync(FINAL_DEST_DIR)) {
            fs.mkdirSync(FINAL_DEST_DIR, { recursive: true });
        }

        const packageInfo = JSON.parse(fs.readFileSync(PACKAGE_JSON_PATH, 'utf-8'));
        const appVersion = packageInfo.version;
        const productName = packageInfo.productName || packageInfo.name;

        // 1. GESTIÓN DE VERSIÓN
        console.log('1. Leyendo archivo de metadatos externo...');
        let currentBuild = 0;
        if (fs.existsSync(VERSION_EXTERNAL_FILE)) {
            const meta = JSON.parse(fs.readFileSync(VERSION_EXTERNAL_FILE, 'utf-8'));
            currentBuild = meta.build || 0;
        }
        const nextBuild = currentBuild + 1;
        console.log(`   -> Build anterior: ${currentBuild} | Próximo Build: ${nextBuild}`);

        // 2. INYECCIÓN TEMPORAL
        console.log('\n2. Inyectando el número de build temporalmente en el código base...');
        const localVersionData = {
            version: appVersion,
            build: nextBuild,
            date: new Date().toISOString(),
            environment: 'production'
        };

        // Garantizamos que src exista (generalmente es así)
        const srcDir = path.join(PROJECT_ROOT, 'src');
        if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

        fs.writeFileSync(VERSION_LOCAL_FILE, JSON.stringify(localVersionData, null, 2));
        localVersionCreated = true;
        console.log(`   -> Generado temporalmente en: src/version_local.json`);

        // 3. COMPILACIÓN / EMPAQUETADO
        console.log('\n3. Iniciando el proceso de empaquetado del ecosistema (Vite + Rust/Tauri + Backend)...');
        
        if (process.platform === 'win32') {
            console.log('   [Ejecutando PyInstaller para Windows...]');
            // Ejecutar pyinstaller directamente
            execSync('pyinstaller --clean anonidata-backend.spec', { stdio: 'inherit' });
            
            // Copiar al directorio binaries con el nombre esperado por Tauri
            const fs = require('fs');
            const path = require('path');
            const sourceExe = path.join(__dirname, 'dist', 'anonidata-backend.exe');
            const binariesDir = path.join(__dirname, 'src-tauri', 'binaries');
            if (!fs.existsSync(binariesDir)) {
                fs.mkdirSync(binariesDir, { recursive: true });
            }
            const targetExe = path.join(binariesDir, 'anonidata-backend-x86_64-pc-windows-msvc.exe');
            console.log(`   [Copiando backend a ${targetExe}...]`);
            fs.copyFileSync(sourceExe, targetExe);
        } else {
            console.log('   [Ejecutando npm run build:backend...]');
            execSync('npm run build:backend', { stdio: 'inherit' });
        }

        console.log('   [Ejecutando npm run build...]');
        const buildCmd = process.platform === 'darwin' 
            ? 'npm run build -- --target universal-apple-darwin' 
            : 'npm run build -- --target x86_64-pc-windows-msvc';
        execSync(buildCmd, { stdio: 'inherit' });
        console.log('   -> Compilación técnica finalizada.');

        // 4. LIMPIEZA DE VERSIÓN ANTERIOR
        console.log('\n4. Preparando directorio destino (sobrescribiendo en lugar de borrar para mantener el ID de Google Drive)...');
        // Eliminamos el borrado explícito (fs.unlinkSync) para que Google Drive detecte 
        // una nueva versión del mismo archivo en lugar de un archivo nuevo con un ID distinto.

        // 5. TRASLADO DEL INSTALADOR FINAL
        console.log('\n5. Trasladando los nuevos binarios a la carpeta de despliegue principal...');
        const possiblePaths = process.platform === 'darwin'
            ? [
                path.join(__dirname, 'src-tauri', 'target', 'universal-apple-darwin', 'release', 'bundle', 'dmg'),
                path.join(__dirname, 'src-tauri', 'target', 'release', 'bundle', 'dmg')
            ]
            : [
                path.join(__dirname, 'src-tauri', 'target', 'x86_64-pc-windows-msvc', 'release', 'bundle', 'nsis'),
                path.join(__dirname, 'src-tauri', 'target', 'release', 'bundle', 'nsis')
            ];

        let targetFiles = [];
        let sourceDir = '';
        
        for (const p of possiblePaths) {
            if (fs.existsSync(p)) {
                const files = fs.readdirSync(p).filter(f => f.endsWith('.dmg') || f.endsWith('.exe'));
                if (files.length > 0) {
                    targetFiles = files;
                    sourceDir = p;
                    break;
                }
            }
        }

        if (targetFiles.length === 0) {
            throw new Error(`CRÍTICA: No se encontró ningún archivo .exe o .dmg generado en las siguientes carpetas:\n` + possiblePaths.map(p => ` - ${p}`).join('\n'));
        }

        const generatedInstallers = [];
        targetFiles.forEach(fileName => {
            const oldPath = path.join(sourceDir, fileName);

            // Nombre fijo para el ejecutable o dmg
            let finalName = fileName.endsWith('.dmg') ? 'Anonidata.dmg' : 'Anonidata.exe';

            const newPath = path.join(FINAL_DEST_DIR, finalName);

            fs.copyFileSync(oldPath, newPath);
            generatedInstallers.push(finalName);
            console.log(`   -> Extraído y Renombrado a: ${finalName}`);
        });

        // 6. ACTUALIZACIÓN DE METADATOS
        console.log('\n6. Actualizando archivo maestro version.json en el destino...');
        
        // Conservar otros instaladores ya existentes en el directorio de destino
        const installersList = [...generatedInstallers];
        const allDriveFiles = fs.readdirSync(FINAL_DEST_DIR);
        allDriveFiles.forEach(file => {
            if ((file.endsWith('.exe') || file.endsWith('.dmg')) && !installersList.includes(file)) {
                installersList.push(file);
            }
        });

        const newMetadata = {
            productName: productName,
            version: appVersion,
            build: nextBuild,
            date: new Date().toISOString(),
            platforms: {
                "mac": {
                    "filename": "Anonidata.dmg",
                    "url": DRIVE_URLS.dmg
                },
                "windows": {
                    "filename": "Anonidata.exe",
                    "url": DRIVE_URLS.exe
                }
            }
        };
        fs.writeFileSync(VERSION_EXTERNAL_FILE, JSON.stringify(newMetadata, null, 2));

        // Despliegue a GitHub Pages si se provee la ruta
        const githubPagesDir = process.env.GITHUB_PAGES_DIR;
        if (githubPagesDir && fs.existsSync(githubPagesDir)) {
            console.log('\n   -> Copiando version.json al repositorio de GitHub Pages y haciendo push...');
            const githubJsonPath = path.join(githubPagesDir, 'ANONIDATA', 'version.json');
            // Crear subcarpeta ANONIDATA si no existe
            if (!fs.existsSync(path.dirname(githubJsonPath))) {
                fs.mkdirSync(path.dirname(githubJsonPath), { recursive: true });
            }
            fs.writeFileSync(githubJsonPath, JSON.stringify(newMetadata, null, 2));
            try {
                execSync(`cd "${githubPagesDir}" && git add . && git commit -m "Update AnoniData version to ${appVersion} Build ${nextBuild}" && git push`, { stdio: 'inherit' });
                console.log('   -> Push a GitHub Pages exitoso.');
            } catch (gitErr) {
                console.error('   [!] Error al hacer push a GitHub Pages:', gitErr.message);
            }
        } else {
            console.log('\n   [!] No se ha definido GITHUB_PAGES_DIR. Por favor copia version.json a tu repo manualmente.');
        }

        // 7. DESPLIEGUE DE LOGO Y README EN EL DESTINO
        console.log('\n7. Copiando logo y generando README.md en el destino...');
        
        // Copiar logo
        const logoSrc = path.join(PROJECT_ROOT, 'public', 'logo.png');
        const logoDst = path.join(FINAL_DEST_DIR, 'logo.png');
        if (fs.existsSync(logoSrc)) {
            fs.copyFileSync(logoSrc, logoDst);
            console.log('   -> Logo copiado a la carpeta de destino.');
        } else {
            console.warn('   [!] Advertencia: No se encontró el logo original en public/logo.png');
        }

        // Generar README.md
        const readmeDst = path.join(FINAL_DEST_DIR, 'README.md');
        const readmeContent = `# AnoniData

AnoniData es una herramienta de escritorio diseñada para eliminar de forma irreversible datos de carácter personal (PII) en documentos PDF. No se toca el PDF original, generando un nuevo PDF anonimizado en la misma carpeta del documento. Todo el procesamiento se realiza de manera 100% local en tu ordenador, garantizando el cumplimiento  del RGPD (Reglamento General de Protección de Datos) y el principio de 'Zero Data Retention'

## 🚀 Últimas Novedades

- **Migración a Tauri v2**: Transición desde Electron a Tauri v2 para un rendimiento optimizado, menor consumo de memoria y tamaño de instalador reducido, además de un aislamiento de seguridad mejorado en el proceso IPC.
- **Implementación de Dark Mode**: Interfaz adaptativa con soporte completo para modo oscuro y diseño renovado de iconos, ofreciendo una experiencia visual premium y moderna.
- **Detección Visual Integrada (OCR)**: Mejoras significativas en el backend de Python para la detección y redacción de firmas manuscritas y códigos QR dentro de los documentos.
- **Publicación Directa en Google Drive**: Automatización de la compilación y copia del instalador ejecutable y sus metadatos a la unidad pública de Google Drive para simplificar la distribución.

## 🛠️ Características Técnicas de Desarrollo

El desarrollo de AnoniData se basa en una arquitectura híbrida de alto rendimiento:

### Arquitectura y Frameworks
- **Tauri v2 (Rust)**: Actúa como el contenedor de escritorio seguro, gestionando la ventana nativa y la comunicación IPC (Inter-Process Communication) securizada con el backend.
- **Frontend (React 18 + TypeScript)**: Interfaz de usuario interactiva y fluida construida sobre React con TypeScript y estilizada con TailwindCSS.
- **Backend (Python 3.11+)**: Ejecutado localmente como un binario sidecar compilado con PyInstaller, encargado del procesamiento pesado de PDF y análisis de datos.

### Procesamiento de PDFs y Lenguaje Natural (NLP)
- **PyMuPDF**: Manipulación y redacción nativa e irreversible de PDFs (eliminación del contenido subyacente y metadatos).
- **spaCy (Modelo en español: es_core_news_lg)**: Procesamiento de Lenguaje Natural para identificar entidades nombradas (nombres de personas, localizaciones, etc.).
- **Tesseract OCR / EasyOCR**: Reconocimiento óptico de caracteres para extraer texto de imágenes integradas y PDFs no digitalizados.
- **OpenCV & PyZbar**: Procesamiento de imagen para la detección de firmas manuscritas y códigos de barras/QR.

### Seguridad y Privacidad
- **Ejecución 100% local**: No requiere conexión a internet para funcionar, ni realiza peticiones externas.
- **Zero Data Retention**: No se almacenan copias temporales de los documentos analizados de forma persistente.
- **Logs Sanitizados**: El sistema de logs local oculta y reemplaza cualquier dato personal detectado antes de escribir en disco.
`;
        fs.writeFileSync(readmeDst, readmeContent, 'utf-8');
        console.log('   -> Archivo README.md generado con éxito.');

        // 8. LIMPIEZA POST-BUILD
        console.log('\n8. Realizando limpieza post-build del entorno local...');
        fs.unlinkSync(VERSION_LOCAL_FILE);
        localVersionCreated = false;
        console.log('   -> Inyección temporal local revertida ✔');

        console.log('\n================================================================');
        console.log(`🚀 DESPLIEGUE FINALIZADO EXISTOSAMENTE: V${appVersion} Build #${nextBuild}`);
        console.log('================================================================\n');

    } catch (error) {
        console.error('\n[!] 🚨 OCURRIÓ UN ERROR CRÍTICO EN EL ORQUESTADOR:');
        console.error(error.message || error);

        // 8. MANEJO DE ERRORES EXTREMO (ABORTO LIMPIO)
        if (localVersionCreated && fs.existsSync(VERSION_LOCAL_FILE)) {
            console.log('   -> Abortando... limpiando residuos de versión temporal...');
            fs.unlinkSync(VERSION_LOCAL_FILE);
        }
        process.exit(1);
    }
}

runWorkflow();
