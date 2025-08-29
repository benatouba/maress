// eslint.config.mjs
import pluginJs from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettier from 'eslint-config-prettier'
import globals from 'globals'
import typescriptEslint from 'typescript-eslint'

export default [
  {
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
    },
    ignores: ['node_modules', 'dist', '.output', '.nuxt', 'coverage'],
  },
  pluginJs.configs.recommended,
  ...typescriptEslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue', '**/*.js', '**/*.ts'],
    rules: {
      // Vue rules for code quality
      'vue/match-component-import-name': 'error',
      'vue/match-component-file-name': ['error', { extensions: ['vue'], shouldMatchCase: true }],
      'vue/component-definition-name-casing': ['warn', 'PascalCase'],
      'vue/block-tag-newline': [
        'warn',
        { singleline: 'always', multiline: 'always', maxEmptyLines: 0 },
      ],
      'vue/html-self-closing': [
        'error',
        {
          html: { void: 'always', normal: 'never', component: 'always' },
          svg: 'always',
          math: 'always',
        },
      ],
      'vue/require-default-prop': 'off',
      'vue/v-on-event-hyphenation': 0,
      'vue/valid-v-slot': 0,
      'vue/multiline-html-element-content-newline': 1,
      // General JS rules
      'no-console': 'warn',
      'no-debugger': 'warn',
      'no-unused-vars': 'warn',
      'comma-dangle': [2, 'always-multiline'],
      semi: [2, 'never'],
      quotes: [2, 'single'],
      indent: ['warn', 2],
      'space-before-function-paren': 0,
      // Prettier integration
      'prettier/prettier': ['error'],
    },
  },
  prettier,
]
