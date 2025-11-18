## References

Checkout the [GitLab repositories](https://git.rwth-aachen.de/nfdi4earth/pilotsincubatorlab) and [LHB articles](https://nfdi4earth.pages.rwth-aachen.de/livinghandbook/livinghandbook/) of other (already completed) NFDI4Earth projects to get a sense of how to design your the README and article. Utilize the feature to evaluate repositories that serve as sources of inspiration.

# MaRESS - Mapping Research in Earth System Sciences

A modern web application for mapping research papers geographically using Vue.js 3, FastAPI, and PostgreSQL with PostGIS. This tool integrates with Zotero for paper management and uses advanced NLP to extract geographic information from academic papers.

## Funding

This work has been funded by the German Research Foundation (NFDI4Earth,
DFG project no. 460036893, https://www.nfdi4earth.de/).

## Features

- **Interactive Geographic Mapping**: Visualize research papers on an interactive map
- **Zotero Integration**: Seamless import from Zotero libraries
- **NLP Processing**: Automated extraction of geographic entities from paper content
- **Advanced Search**: Filter papers by location, topic, author, and date
- **Export Capabilities**: Export maps and data in various formats

## Technology Stack

### Frontend
- [Vue.js 3](https://vuejs.org/) with Composition API
- [OpenLayers](https://openlayers.org/) for interactive maps
- [Pinia](https://pinia.vuejs.org/) for state management
- [Vue Router](https://router.vuejs.org/) for navigation
- [Vite](https://vite.dev/) for development and building
- [Vuetify](https://vuetifyjs.com/en/) for UI components
- [Cytoscape.js](https://js.cytoscape.org/) for network/graph visualisation

### Backend
- [FastAPI](https://fastapi.tiangolo.com/) for high-performance API
- [SQLAlchemy](https://www.sqlalchemy.org/) (with [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/en/latest/index.html) for database ORM (Not yet implemented))
- [SQLModel](https://sqlmodel.tiangolo.com/) for (easier) data modelling - Note: SQLModel is built on top of SQLAlchemy
- [PostgreSQL](https://www.postgresql.org/) (with [PostGIS](https://postgis.net/) for geospatial data (not yet implemented))
- [Celery](https://github.com/celery/celery) for background task processing
- [Redis](https://redis.io/) for caching and task queue

### NLP & Processing
- [spacy-layout](https://spacy.io/universe/project/spacy-layout) for document processing
- [spaCy](https://spacy.io/) for named entity recognition and other NLP tasks
- [Pyzotero](https://github.com/urschrei/pyzotero) for Zotero API integration
- OpenAI API for advanced text analysis (Not yet implemented)

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://gitlab.klima.tu-berlin.de/klima/maress.git
   cd maress
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3a. **Start with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

3b. **Or set up manually** with `uv` for the backend and `pnpm` for the frontend:

   - Backend:
     ```bash
     cd backend
     uv sync
     bash scripts/prestart.sh # Warning: This will reset the database!
     uv run fastapi run --reload
     ```

     and in another terminal, start a [Redis](https://redis.io/) instance and then the [Celery](https://github.com/celery/celery) worker(s).
     [Redis](https://redis.io/) can most easily be started with Docker:

     ```bash
     docker run -d -p 6379:6379 redis
     ```

     This will load the Redis server in a Docker container and map the default port `6379` to your localhost.
     In case you you have `redis` installed locally (and it uses the default port `6379`), you can also start it with:

     ```bash
     redis-server
     ```

     Then, start the Celery worker(s):

     ```bash
     cd backend
     uv run celery -A app.celery_app worker --loglevel=info --concurrency=2
     ```

     start `mailhog` for email during development (refer to [backend/README.md](backend/README.md) for installation details):

     ```bash
     mailhog
     ```

   - Frontend:
     ```bash
     cd frontend
     pnpm install
     pnpm run dev
     ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - [MailHog UI](http://localhost:8025): http://localhost:8025

   [MailHog](https://github.com/mailhog/MailHog) connects to the SMTP server at `localhost:1025` by default.
   Your [Celery](https://github.com/celery/celery) worker should be processing long tasks in the background.

## Development Setup

### Backend Setup
Set up the backend similarly to the quick start instructions above.
Please refer to the [backend/README.md](backend/README.md) for detailed backend setup instructions.

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## API Documentation

The FastAPI backend automatically generates OpenAPI documentation:
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
