const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ==========================================
// CONFIGURACIÓN GENÉRICA Y DIRECTORIOS
// ==========================================
const PROJECT_ROOT = process.cwd();
// Directorio final donde se guardarán los instaladores listos (puedes inyectar Variables de Entorno en tu CI/CD)
const FINAL_DEST_DIR = process.env.FINAL_DEST_DIR || '/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA';
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
    dmg: 'https://drive.google.com/open?id=1bxE2vziPKfNEbWwSo0zO6IG_3qz7EwCc&usp=drive_fs',
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
        console.log('   [Ejecutando npm run build...]');
        execSync('npm run build', { stdio: 'inherit' });
        console.log('   -> Compilación técnica finalizada.');

        // 4. LIMPIEZA DE VERSIÓN ANTERIOR
        console.log('\n4. Limpiando versiones pasadas en el directorio destino...');
        const existingFiles = fs.readdirSync(FINAL_DEST_DIR);
        existingFiles.forEach(file => {
            if (file.endsWith('.exe') || file.endsWith('.dmg')) {
                fs.unlinkSync(path.join(FINAL_DEST_DIR, file));
                console.log(`   -> Eliminado antiguo: ${file}`);
            }
        });

        // 5. DESPLIEGUE INTERNO
        console.log('\n5. Trasladando los nuevos binarios a la carpeta de despliegue principal...');
        const macDmgDir = path.join(PROJECT_ROOT, 'src-tauri', 'target', 'release', 'bundle', 'dmg');
        const winNsisDir = path.join(PROJECT_ROOT, 'src-tauri', 'target', 'release', 'bundle', 'nsis');
        
        let targetFiles = [];
        let sourceDir = '';
        
        if (fs.existsSync(macDmgDir)) {
            const files = fs.readdirSync(macDmgDir).filter(f => f.endsWith('.dmg'));
            if (files.length > 0) {
                targetFiles = files;
                sourceDir = macDmgDir;
            }
        }
        
        if (targetFiles.length === 0 && fs.existsSync(winNsisDir)) {
            const files = fs.readdirSync(winNsisDir).filter(f => f.endsWith('.exe'));
            if (files.length > 0) {
                targetFiles = files;
                sourceDir = winNsisDir;
            }
        }

        if (targetFiles.length === 0) {
            throw new Error(`CRÍTICA: No se encontró ningún archivo .exe o .dmg generado en las carpetas de Tauri: \n - ${macDmgDir}\n - ${winNsisDir}`);
        }

        const generatedInstallers = [];
        targetFiles.forEach(fileName => {
            const oldPath = path.join(sourceDir, fileName);

            // Nombre fijo para el ejecutable o dmg
            let finalName = fileName.endsWith('.dmg') ? 'AnoniData.dmg' : 'AnoniData.exe';

            const newPath = path.join(FINAL_DEST_DIR, finalName);

            fs.copyFileSync(oldPath, newPath);
            generatedInstallers.push(finalName);
            console.log(`   -> Extraído y Renombrado a: ${finalName}`);
        });

        // 6. ACTUALIZACIÓN DE METADATOS
        console.log('\n6. Actualizando archivo maestro version.json en el destino...');
        const newMetadata = {
            productName: productName,
            version: appVersion,
            build: nextBuild,
            date: new Date().toISOString(),
            installers: generatedInstallers,
            mainInstallerFilename: generatedInstallers.find(f => f.toLowerCase().includes('setup')) || generatedInstallers[0],
            downloadUrls: {
                "AnoniData.dmg": DRIVE_URLS.dmg,
                "AnoniData.exe": DRIVE_URLS.exe,
                "version.json": DRIVE_URLS.version_json
            }
        };
        fs.writeFileSync(VERSION_EXTERNAL_FILE, JSON.stringify(newMetadata, null, 2));
        console.log(`   -> Metadatos consolidados con éxito.`);

        // 7. LIMPIEZA POST-BUILD
        console.log('\n7. Realizando limpieza post-build del entorno local...');
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
