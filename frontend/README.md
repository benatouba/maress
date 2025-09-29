# Vue3 Project - Frontend

## General Workflow
This project uses [pnpm](https://pnpm.io/) as the package manager but any other like `npm` or `yarn` should work as well. Minimal changes might be needed to replicate the exact commands (in particular the use of [Rolldown](https://vite.dev/guide/rolldown) as the bundler).

Make sure your editor is using the correct [Node](https://nodejs.org/en) version, with the one specified in `.nvmrc` or `.node-version` if you are using [nvm](https://github.com/nvm-sh/nvm). 
The project was developed with **Node v24.7**, so using that version is recommended.

From `./frontend/` you can install all the dependencies with:

```console
$ pnpm install
```
Then you can start the development server with:
```console
$ pnpm dev
```
This will start a local development server at `http://localhost:3000` that reloads when it detects code changes.

## Frontend tests
**Note:** There are no tests implemented yet.

The frontend uses [Vitest](https://vitest.dev/) as the testing framework.
To run the frontend tests, use:

```console
$ pnpm test
```

You can also run the tests with a user interface:

```console
$ pnpm test:ui
```

## Deploying the Frontend
The frontend can be built for production with:
```console
$ pnpm build
```

The built files can be previewed locally with:
```console
$ pnpm preview
```

This will create an optimized version of the app in the `dist/` directory.
The contents of the `dist/` directory can be served with any static file server (e.g. [nginx](https://nginx.org/en/) or [Apache2](https://httpd.apache.org/)) or deployed to a hosting service that supports static sites.
