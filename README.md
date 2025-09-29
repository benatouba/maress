# Incubator Template

Welcome to the [NFDI4Earth](https://www.nfdi4earth.de/) community!

This template is designed to assist you in adhering to the FAIR principles and showcasing your project within the NFDI4Earth community.

## Getting Started

**Step 1**: Get acess to the RWTH-AACHEN GitLab! Use a browser to access https://git.rwth-aachen.de and login either via the DFN AAI Single Sign-On if your institution supports this, or authenticate via Github (if you don't have DFN Login and no Github accound, please create an account under https://github.com/ and use this one). After you have initially logged in once into the RWTH Aachen Gitlab, send an email with your account name and the name of your Pilot to nfdi4earth-incubators@tu-dresden.de. You will then be granted access rights to the Gitlab project for your Pilot.

**Step 2**:
Adapt the meta files, specifically the _nfdi4earth-meta.yaml_ and the _CITATION.cff_, to ensure the findability of your project. _nfdi4earth-meta.yaml_ is used to collect all metadata on your research project itself and the produced outcomes. _CITATION.cff_ is used to collect metadata on one specific software and make it citable. You can either use this Gitlab project to host your software source code or if you are committing to an existing, external code repository please make sure there is a _CITATION.cff_ and add the link to the _nfdi4earth-meta.yaml_. You can make the changes using the WEB-IDE or by [cloning](https://docs.gitlab.com/ee/tutorials/make_first_git_commit/) this repository.

**Step 3**:
Update the _README.md_ and _lhb-article.md_ files.
Initially, both files will be identical, but they may diverge as your project progresses. The content of the _lhb-article.md_ will be highligthed through the [Living Handbook (LHB)](https://nfdi4earth.pages.rwth-aachen.de/livinghandbook/livinghandbook/#N4E_Pilots/). Begin by addressing the TODO items in the _lhb-article.md_, copying your proposal text to both files, and adapting links and headings using [Markdown syntax](https://www.markdownguide.org/basic-syntax/). Later, the Living Handbook Article should providen an easy-to-understand overview of the project and your results. In contrast, the _README.md_ may also be part of your final project report and for software projects, the _README.md_ should highlight how to install and use the software.

## References

Checkout the [GitLab repositories](https://git.rwth-aachen.de/nfdi4earth/pilotsincubatorlab) and [LHB articles](https://nfdi4earth.pages.rwth-aachen.de/livinghandbook/livinghandbook/) of other (already completed) NFDI4Earth projects to get a sense of how to design your the README and article. Utilize the feature to evaluate repositories that serve as sources of inspiration.

## Funding

This work has been funded by the German Research Foundation (NFDI4Earth,
DFG project no. 460036893, https://www.nfdi4earth.de/).

# MaRESS - Mapping Research in Earth System Sciences

A modern web application for mapping research papers geographically using Vue.js 3, FastAPI, and PostgreSQL with PostGIS. This tool integrates with Zotero for paper management and uses advanced NLP to extract geographic information from academic papers.

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
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
alembic upgrade head
uvicorn app.main:app --reload
```

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
