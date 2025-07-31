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

# MaRESS

A modern web application for mapping research papers geographically using Vue.js 3, FastAPI, and PostgreSQL with PostGIS. This tool integrates with Zotero for paper management and uses advanced NLP to extract geographic information from academic papers.

## Features

- **Interactive Geographic Mapping**: Visualize research papers on an interactive map
- **Zotero Integration**: Seamless import from Zotero libraries
- **NLP Processing**: Automated extraction of geographic entities from paper content
- **Advanced Search**: Filter papers by location, topic, author, and date
- **Collaborative Features**: Share maps and collections with other researchers
- **Export Capabilities**: Export maps and data in various formats

## Technology Stack

### Frontend
- Vue.js 3 with Composition API
- Leaflet.js for interactive maps
- Pinia for state management
- Vue Router for navigation
- Vite for development and building

### Backend
- FastAPI for high-performance API
- SQLAlchemy with GeoAlchemy2 for database ORM
- PostgreSQL with PostGIS for geospatial data
- Celery for background task processing
- Redis for caching and task queue

### NLP & Processing
- spaCy for named entity recognition
- LangChain for document processing
- Pyzotero for Zotero API integration
- OpenAI API for advanced text analysis

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd research-paper-mapper
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Start with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

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
