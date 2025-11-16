import type { Config } from 'prettier'
import { parsers } from '@prettier/plugin-oxc'

const config: Config = {
  experimentalOperatorPosition: 'end',
  experimentalTernaries: true,
  arrowParens: 'always',
  bracketSameLine: true,
  objectWrap: 'collapse',
  bracketSpacing: true,
  embeddedLanguageFormatting: 'auto',
  htmlSelfClosingStyle: 'vue',
  htmlWhitespaceSensitivity: 'css',
  printWidth: 100,
  proseWrap: 'always',
  quoteProps: 'as-needed',
  rangeStart: 0,
  semi: false,
  singleAttributePerLine: true,
  singleQuote: true,
  tabWidth: 2,
  tabs: false,
  trailingComma: 'all',
  vueIndentScriptAndStyle: false,
  plugins: [ "@prettier/plugin-oxc"],
  overrides: [
    {
      files: ['*.js', '*.ts', '*.vue'],
      options: {
        parsers, // uses @prettier/oxc parser for these files
      },
    },
  ],
}

export default config
