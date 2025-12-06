const { FusesPlugin } = require('@electron-forge/plugin-fuses');
const { FuseV1Options, FuseVersion } = require('@electron/fuses');

module.exports = {
  packagerConfig: {
    asar: {
      unpack: '*.node' // Solo desempaquetar archivos .node nativos
    },
    ignore: [
      /^\/backend/, // Excluir todo el directorio backend del asar (solo se usa el binario en extraResources)
      /^\/test/, // Excluir carpeta de tests
      /^\/out/, // Excluir builds anteriores
      /^\/build/, // Excluir directorio build (artefactos de compilación)
      /^\/release/, // Excluir directorio release (builds de electron-builder)
      /^\/resources/, // Excluir directorio resources (artefactos de builds)
      /\.pyc$/, // Excluir archivos .pyc
      /\.spec$/ // Excluir archivos .spec
    ],
    extraResource: [
      'backend/dist/anonidata-backend'
    ],
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      config: {},
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin'],
    },
    {
      name: '@electron-forge/maker-deb',
      config: {},
    },
    {
      name: '@electron-forge/maker-rpm',
      config: {},
    },
  ],
  plugins: [
    {
      name: '@electron-forge/plugin-auto-unpack-natives',
      config: {},
    },
    // Fuses are used to enable/disable various Electron functionality
    // at package time, before code signing the application
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};
