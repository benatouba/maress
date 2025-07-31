# Research Paper Geographic Mapping Application

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
