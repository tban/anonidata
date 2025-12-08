const { FusesPlugin } = require('@electron-forge/plugin-fuses');
const { FuseV1Options, FuseVersion } = require('@electron/fuses');

module.exports = {
  packagerConfig: {
    icon: './build/icon',
    arch: 'x64',
    platform: 'win32',
    asar: {
      unpack: '*.node'
    },
    ignore: [
      /^\/backend/,
      /^\/test/,
      /^\/out/,
      /^\/build/,
      /^\/release/,
      /^\/resources/,
      /\.pyc$/,
      /\.spec$/
    ],
    extraResource: [
      'dist/anonidata-backend.exe'
    ],
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      platforms: ['win32'],
      config: {
        name: 'Anonidata',
        authors: 'AnoniData',
        description: 'Aplicación para anonimización de PDFs'
      }
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['win32']
    }
  ],
  plugins: [
    {
      name: '@electron-forge/plugin-auto-unpack-natives',
      config: {},
    },
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
  publishers: [
    {
      name: '@electron-forge/publisher-github',
      config: {
        repository: {
          owner: 'tban',
          name: 'anonidata',
        },
        prerelease: false,
        draft: true,
      },
    },
  ],
};
